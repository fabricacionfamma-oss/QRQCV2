import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import urllib.parse
import io
import math

# ==========================================
# 1. CONFIGURACIÓN INICIAL Y CSS
# ==========================================
st.set_page_config(page_title="Tablero QRQC", layout="centered")

st.markdown("""
    <style>
        .block-container { 
            padding-top: 1.5rem !important; 
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        header {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

url_ingresos = "https://docs.google.com/spreadsheets/d/1xw4aqqpf6pWDa9LQSmS3ztLiF82n-ZQ0NqY3QRVTTFg/edit"
url_form = "https://docs.google.com/forms/d/e/1FAIpQLSe9AHzNLjUkg3tdfbsUopdc8_YldXLk4YbGXYaeNKyWA198vQ/viewform"

# ==========================================
# 2. CONEXIÓN Y LÓGICA DE DATOS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df_raw = conn.read(spreadsheet=url_ingresos, ttl=300)

if df_raw.empty:
    st.warning("No hay datos registrados en el sistema.")
    st.stop()

# Copia y limpieza inicial
df = df_raw.copy()
df.columns = df.columns.str.strip()

# Mapeo ABSOLUTO de todas las columnas de tu Excel
mapeo = {
    'Marca temporal': 'FECHA_INICIO', 
    'AREA': 'ÁREA_PRINCIPAL',
    'CATEGORIA': 'CATEGORIA',
    'QUE AREA ENCUENTRA EL PROBLEMA?': 'AREA_ENCUENTRA',
    'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE',
    'QUE TIPO DE EFECTO TIENE LA FALLA?': 'TIPO_EFECTO', 
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'MOTIVO DE LA CARGA': 'ESTADO'
}
df = df.rename(columns=mapeo)

# --- TRUCO PARA ACTUALIZACIONES Y FECHAS CORRECTAS ---
if 'N° DE TICKET' in df.columns:
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df = df[df['N° DE TICKET'] != 'nan']
    
    if 'FECHA_INICIO' in df.columns:
        df['FECHA_INICIO'] = pd.to_datetime(df['FECHA_INICIO'], errors='coerce', dayfirst=True)
    else:
        df['FECHA_INICIO'] = pd.NaT

    if 'FECHA DE CIERRE' in df.columns:
        df['FECHA DE CIERRE'] = pd.to_datetime(df['FECHA DE CIERRE'], errors='coerce', dayfirst=True)
    else:
        df['FECHA DE CIERRE'] = pd.NaT

    primeras_fechas_inicio = df.groupby('N° DE TICKET')['FECHA_INICIO'].min()
    df = df.drop_duplicates(subset=['N° DE TICKET'], keep='last').copy()
    df['FECHA_INICIO'] = df['N° DE TICKET'].map(primeras_fechas_inicio)

# --- FUNCIÓN GENERADORA DE LINKS ---
def generar_link_actualizacion(row):
    def clean(val): 
        limpio = str(val).strip() if pd.notna(val) else ""
        return urllib.parse.quote(limpio) if limpio.lower() != 'nan' else ""

    ticket = clean(row.get('N° DE TICKET'))
    area_p = clean(row.get('ÁREA_PRINCIPAL'))
    cat    = clean(row.get('CATEGORIA'))
    area_e = clean(row.get('AREA_ENCUENTRA'))
    resp   = clean(row.get('RESPONSABLE'))
    efecto = clean(row.get('TIPO_EFECTO')) 
    desc   = clean(row.get('PROBLEMA'))
    estado = clean(row.get('ESTADO'))
    
    fecha_val = row.get('FECHA DE CIERRE')
    fecha_str = fecha_val.strftime("%Y-%m-%d") if pd.notna(fecha_val) else ""

    params = {
        "entry.809586642": ticket,       
        "entry.1541179458": area_p,      
        "entry.456805649": cat,          
        "entry.1851030336": area_e,      
        "entry.1946844485": resp,        
        "entry.1049723160": efecto,      
        "entry.552314530": desc,         
        "entry.705803950": estado,       
        "entry.536779116": fecha_str     
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{url_form}?usp=pp_url&{query_string}"

if not df.empty:
    df['ACCIÓN'] = df.apply(generar_link_actualizacion, axis=1)

if 'ESTADO' in df.columns:
    es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)
    df_activos = df[~es_cerrado].copy()
    df_cerrados = df[es_cerrado].copy()
else:
    df_activos = df.copy()
    df_cerrados = pd.DataFrame(columns=df.columns)

# INVERSIÓN DEL ORDEN DE LOS DATOS (Los más recientes primero)
df_activos = df_activos.iloc[::-1]
df_cerrados = df_cerrados.iloc[::-1]

# ==========================================
# 3. GENERADOR DE PDF Y EXCEL
# ==========================================
def generar_pdf(dataframe):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Listado de Fallos Activos", ln=True, align='C')
    pdf.ln(5)
    
    # Configuración de FPDF adaptada a las nuevas columnas
    col_widths = [18, 25, 27, 25, 20, 20, 110, 32] # Total = 277 mm
    headers = ['TICKET', 'PLANTA', 'RESPONSABLE', 'CATEGORIA', 'INICIO', 'CIERRE', 'DESCRIPCION', 'AFECTA']
    line_height = 5
    
    # Encabezados
    pdf.set_font("Arial", 'B', 8)
    pdf.set_fill_color(217, 217, 217)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, align='C', fill=True)
    pdf.ln()

    # Variables
    pdf.set_font("Arial", '', 8)
    hoy = pd.Timestamp.today(tz='America/Argentina/Cordoba').date()

    for _, row in dataframe.iterrows():
        # Extracción y limpieza
        tkt = str(row.get('N° DE TICKET', '')).encode('latin-1', 'replace').decode('latin-1')
        planta = str(row.get('ÁREA_PRINCIPAL', '')).encode('latin-1', 'replace').decode('latin-1')
        resp = str(row.get('RESPONSABLE', '')).encode('latin-1', 'replace').decode('latin-1')
        cat = str(row.get('CATEGORIA', '')).encode('latin-1', 'replace').decode('latin-1')
        
        f_ini = row.get('FECHA_INICIO')
        ini = f_ini.strftime("%d/%m/%Y") if pd.notna(f_ini) and isinstance(f_ini, pd.Timestamp) else ""
        
        f_cie = row.get('FECHA DE CIERRE')
        cie = f_cie.strftime("%d/%m/%Y") if pd.notna(f_cie) and isinstance(f_cie, pd.Timestamp) else ""
        
        desc = str(row.get('PROBLEMA', '')).encode('latin-1', 'replace').decode('latin-1')
        afecta = str(row.get('TIPO_EFECTO', '')).encode('latin-1', 'replace').decode('latin-1')
        
        data_row = [tkt, planta, resp, cat, ini, cie, desc, afecta]
        
        # 1. Calcular altura necesaria para la fila (Centrado Vertical)
        max_lines = 1
        for i, text in enumerate(data_row):
            text_width = pdf.get_string_width(text)
            lines = math.ceil(text_width / (col_widths[i] - 2)) + text.count('\n')
            if lines > max_lines:
                max_lines = lines
                
        row_height = (max_lines * line_height) + 2 # Margen interior
        
        # Salto de página preventivo si no entra la fila
        if pdf.get_y() + row_height > 190: # Limite inferior hoja A4 apaisada
            pdf.add_page()
            pdf.set_font("Arial", 'B', 8)
            pdf.set_fill_color(217, 217, 217)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, h, border=1, align='C', fill=True)
            pdf.ln()
            pdf.set_font("Arial", '', 8)
            
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # 2. Imprimir celdas
        for i, text in enumerate(data_row):
            # Calcular Y para centrado vertical
            text_width = pdf.get_string_width(text)
            lines = math.ceil(text_width / (col_widths[i] - 2)) + text.count('\n')
            text_height = lines * line_height
            y_offset = (row_height - text_height) / 2
            
            # Reset posición para pintar fondo y bordes
            pdf.set_xy(x_start, y_start)
            
            # Lógica de color de celda CIERRE
            if headers[i] == 'CIERRE' and cie != "":
                if pd.notna(f_cie) and isinstance(f_cie, pd.Timestamp) and f_cie.date() < hoy:
                    pdf.set_fill_color(255, 199, 206)
                    pdf.set_text_color(156, 0, 6)
                    pdf.rect(x_start, y_start, col_widths[i], row_height, 'DF')
                else:
                    pdf.set_fill_color(198, 239, 206)
                    pdf.set_text_color(0, 97, 0)
                    pdf.rect(x_start, y_start, col_widths[i], row_height, 'DF')
            else:
                pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(0, 0, 0)
                pdf.rect(x_start, y_start, col_widths[i], row_height, 'D')
                
            # Escribir el texto multilínea y centrado vertical/horizontal
            pdf.set_xy(x_start, y_start + y_offset)
            pdf.multi_cell(col_widths[i], line_height, text, border=0, align='C')
            
            x_start += col_widths[i]
            
        pdf.set_y(y_start + row_height)
        pdf.set_text_color(0, 0, 0) # resetear colores al negro
        
    return pdf.output(dest='S').encode('latin-1')


def generar_excel(dataframe):
    # Agregamos TICKET y PLANTA a las columnas requeridas
    cols_necesarias = ['N° DE TICKET', 'ÁREA_PRINCIPAL', 'RESPONSABLE', 'CATEGORIA', 'FECHA_INICIO', 'FECHA DE CIERRE', 'PROBLEMA', 'TIPO_EFECTO']
    for col in cols_necesarias:
        if col not in dataframe.columns:
            dataframe[col] = "Sin dato"

    df_export = dataframe[cols_necesarias].copy()
    # Renombramos las columnas para la salida del Excel
    df_export.columns = ['TICKET', 'PLANTA', 'RESPONSABLE', 'CATEGORIA', 'INICIO', 'CIERRE', 'DESCRIPCION', 'AFECTA']
    
    hoy = pd.Timestamp.today(tz='America/Argentina/Cordoba').date()
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df_export.to_excel(writer, index=False, sheet_name='Pendientes')
    
    workbook = writer.book
    worksheet = writer.sheets['Pendientes']
    
    header_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#D9D9D9', 'align': 'center', 'valign': 'vcenter'})
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
    red_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
    green_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
    cell_format = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center'})
    
    for col_num, value in enumerate(df_export.columns.values):
        worksheet.write(0, col_num, value, header_format)
        
    # Anchos de columna ajustados
    worksheet.set_column('A:B', 15)  # Ticket, Planta
    worksheet.set_column('C:D', 20)  # Responsable, Categoria
    worksheet.set_column('E:F', 15)  # Inicio, Cierre
    worksheet.set_column('G:G', 60)  # Descripcion
    worksheet.set_column('H:H', 25)  # Afecta
    
    for row_num in range(len(df_export)):
        for col_num in range(len(df_export.columns)):
            col_name = df_export.columns[col_num]
            val = df_export.iloc[row_num, col_num]
            
            if pd.isna(val) or val == "" or val == "Sin dato":
                worksheet.write(row_num + 1, col_num, str(val) if val == "Sin dato" else "", cell_format)
            elif col_name == 'CIERRE':
                if isinstance(val, pd.Timestamp) and val.date() < hoy:
                    worksheet.write_datetime(row_num + 1, col_num, val, red_format)
                elif isinstance(val, pd.Timestamp):
                    worksheet.write_datetime(row_num + 1, col_num, val, green_format)
                else:
                    worksheet.write(row_num + 1, col_num, str(val), cell_format)
            elif col_name == 'INICIO':
                if isinstance(val, pd.Timestamp):
                    worksheet.write_datetime(row_num + 1, col_num, val, date_format)
                else:
                    worksheet.write(row_num + 1, col_num, str(val), cell_format)
            else:
                worksheet.write(row_num + 1, col_num, str(val), cell_format)
                
    writer.close()
    return output.getvalue()


# ==========================================
# 4. INTERFAZ VISUAL
# ==========================================
st.title("🏭 Tablero QRQC")
st.link_button("➕ INGRESAR NUEVO TICKET", url_form, use_container_width=True, type="primary")

if st.button("🔄 Actualizar App", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.divider()

# --- NUEVA LÓGICA DE FILTROS ---
with st.expander("🔍 Buscador y Filtros", expanded=True):
    busqueda = st.text_input("Buscar en la descripción del problema:")
    
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        areas_list = sorted(df['ÁREA_PRINCIPAL'].dropna().astype(str).unique().tolist()) if 'ÁREA_PRINCIPAL' in df.columns else []
        f_area = st.selectbox("📍 Planta:", ["Todas"] + areas_list)
        
        resp_list = sorted(df['RESPONSABLE'].dropna().astype(str).unique().tolist()) if 'RESPONSABLE' in df.columns else []
        f_responsable = st.selectbox("👤 Responsable:", ["Todos"] + resp_list)

    with col_filtro2:
        detecto_list = sorted(df['AREA_ENCUENTRA'].dropna().astype(str).unique().tolist()) if 'AREA_ENCUENTRA' in df.columns else []
        f_detecto = st.selectbox("🔍 Área que detectó:", ["Todas"] + detecto_list)
        
        if 'TIPO_EFECTO' in df.columns:
            efectos_list = sorted(df['TIPO_EFECTO'].dropna().astype(str).unique().tolist())
        else:
            efectos_list = []
        f_efecto = st.selectbox("⚠️ Tipo de Efecto:", ["Todos"] + efectos_list)

# --- APLICACIÓN DE LOS FILTROS ---
if busqueda and not df_activos.empty:
    df_activos = df_activos[df_activos['PROBLEMA'].str.contains(busqueda, case=False, na=False)]
if f_area != "Todas" and not df_activos.empty:
    df_activos = df_activos[df_activos['ÁREA_PRINCIPAL'] == f_area]
if f_responsable != "Todos" and not df_activos.empty:
    df_activos = df_activos[df_activos['RESPONSABLE'] == f_responsable]
if f_detecto != "Todas" and not df_activos.empty:
    df_activos = df_activos[df_activos['AREA_ENCUENTRA'] == f_detecto]
if f_efecto != "Todos" and not df_activos.empty:
    df_activos = df_activos[df_activos['TIPO_EFECTO'] == f_efecto]


# ==========================================
# 5. TARJETAS ACTIVAS
# ==========================================
st.subheader(f"📋 Pendientes ({len(df_activos)})")
hoy = pd.Timestamp.today(tz='America/Argentina/Cordoba').date()

if not df_activos.empty:
    for _, row in df_activos.iterrows():
        with st.container(border=True):
            
            f_inicio = row.get('FECHA_INICIO')
            txt_inicio = f_inicio.strftime("%d/%m/%Y") if pd.notna(f_inicio) and isinstance(f_inicio, pd.Timestamp) else "Sin dato"

            f_cierre = row.get('FECHA DE CIERRE')
            if pd.notna(f_cierre) and isinstance(f_cierre, pd.Timestamp):
                f_str = f_cierre.strftime("%d/%m/%Y")
                color = "green" if f_cierre.date() >= hoy else "red"
                txt_cierre = f":{color}[**📅 Cierre: {f_str}**]"
            else:
                txt_cierre = "**📅 Cierre:** Sin asignar"

            st.markdown(f"**Ticket:** {row.get('N° DE TICKET', 'N/A')} | **📅 Inicio:** {txt_inicio} | {txt_cierre}")
            st.markdown(f"**📂 Categoría:** {row.get('CATEGORIA', 'N/A')} | **⚠️ Efecto:** {row.get('TIPO_EFECTO', 'N/A')}")
            st.markdown(f"**📍 Área:** {row.get('ÁREA_PRINCIPAL', 'N/A')}")
            st.markdown(f"**🔍 Detectó:** {row.get('AREA_ENCUENTRA', 'N/A')} | **👤 Responsable:** {row.get('RESPONSABLE', 'N/A')}")
            st.markdown(f"**📌 Estado:** {row.get('ESTADO', 'N/A')}")
            
            st.error(f"**Descripción:**\n{row.get('PROBLEMA', 'N/A')}")
            
            if 'ACCIÓN' in row and pd.notna(row['ACCIÓN']):
                st.link_button("🔄 Actualizar / Editar Ticket", row['ACCIÓN'], use_container_width=True)

    st.divider()
    
    col_btn_pdf, col_btn_excel = st.columns(2)
    
    with col_btn_pdf:
        pdf_bytes = generar_pdf(df_activos)
        st.download_button("📄 Descargar PDF", pdf_bytes, "Reporte_Fallos.pdf", "application/pdf", use_container_width=True)
        
    with col_btn_excel:
        excel_bytes = generar_excel(df_activos)
        st.download_button("📊 Descargar Excel", excel_bytes, "Reporte_Pendientes.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

else:
    st.success("✅ Sin problemas pendientes o sin resultados para tu filtro.")

# ==========================================
# 6. HISTORIAL CERRADOS
# ==========================================
with st.expander("✅ VER HISTORIAL CERRADOS"):
    if df_cerrados.empty:
        st.write("No hay tickets cerrados.")
    else:
        for _, row in df_cerrados.iterrows():
            with st.container(border=True):
                f_ini_c = row.get('FECHA_INICIO')
                txt_ini_c = f_ini_c.strftime("%d/%m/%Y") if pd.notna(f_ini_c) and isinstance(f_ini_c, pd.Timestamp) else "Sin dato"
                
                st.markdown(f"**Ticket {row.get('N° DE TICKET', 'N/A')}** | 📅 Inicio: {txt_ini_c} | {row.get('CATEGORIA', 'N/A')} | Efecto: {row.get('TIPO_EFECTO', 'N/A')}")
                st.success(f"**Resuelto:**\n{row.get('PROBLEMA', 'N/A')}")
