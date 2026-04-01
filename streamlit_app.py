import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import urllib.parse
import io  

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
    'QUE TIPO DE EFECTO TIENE EL PROBLEMA?': 'TIPO_EFECTO', 
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'MOTIVO DE LA CARGA': 'ESTADO'
}
df = df.rename(columns=mapeo)

# --- TRUCO PARA ACTUALIZACIONES Y FECHAS CORRECTAS ---
if 'N° DE TICKET' in df.columns:
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df = df[df['N° DE TICKET'] != 'nan']
    
    # Parsear fechas ANTES de agrupar para evitar errores
    if 'FECHA_INICIO' in df.columns:
        df['FECHA_INICIO'] = pd.to_datetime(df['FECHA_INICIO'], errors='coerce', dayfirst=True)
    else:
        df['FECHA_INICIO'] = pd.NaT

    if 'FECHA DE CIERRE' in df.columns:
        df['FECHA DE CIERRE'] = pd.to_datetime(df['FECHA DE CIERRE'], errors='coerce', dayfirst=True)
    else:
        df['FECHA DE CIERRE'] = pd.NaT

    # 1. Rescatamos la PRIMERA fecha de ingreso de cada ticket
    primeras_fechas_inicio = df.groupby('N° DE TICKET')['FECHA_INICIO'].min()
    
    # 2. Nos quedamos con el ÚLTIMO registro (para que traiga el cierre, estado actual, etc.)
    df = df.drop_duplicates(subset=['N° DE TICKET'], keep='last').copy()
    
    # 3. Le reasignamos la fecha original (la primera) a la columna FECHA_INICIO
    df['FECHA_INICIO'] = df['N° DE TICKET'].map(primeras_fechas_inicio)

# --- FUNCIÓN GENERADORA DE LINKS (PRE-LLENADO TOTAL) ---
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

    # IDs Definitivos confirmados
    params = {
        "entry.809586642": ticket,       # N° de Ticket
        "entry.1541179458": area_p,      # ÁREA
        "entry.456805649": cat,          # CATEGORÍA
        "entry.1851030336": area_e,      # QUE ÁREA ENCUENTRA
        "entry.1946844485": resp,        # QUE ÁREA ES RESPONSABLE
        "entry.1049723160": efecto,      # TIPO DE EFECTO
        "entry.552314530": desc,         # DESCRIPCIÓN
        "entry.705803950": estado,       # MOTIVO (ESTADO)
        "entry.536779116": fecha_str     # FECHA CIERRE
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{url_form}?usp=pp_url&{query_string}"

df['ACCIÓN'] = df.apply(generar_link_actualizacion, axis=1)

# Separar activos de cerrados
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)
df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

# ==========================================
# 3. GENERADOR DE PDF Y EXCEL
# ==========================================
def generar_pdf(dataframe):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Listado de Fallos Activos", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 8, "Ticket", 1)
    pdf.cell(40, 8, "Area", 1)
    pdf.cell(40, 8, "Categoria", 1)
    pdf.cell(40, 8, "Responsable", 1)
    pdf.cell(110, 8, "Problema", 1, 1)
    
    pdf.set_font("Arial", '', 9)
    for _, row in dataframe.iterrows():
        prob = str(row.get('PROBLEMA', ''))[:80].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(20, 8, str(row.get('N° DE TICKET', '-')), 1)
        pdf.cell(40, 8, str(row.get('ÁREA_PRINCIPAL', ''))[:20], 1)
        pdf.cell(40, 8, str(row.get('CATEGORIA', ''))[:20], 1)
        pdf.cell(40, 8, str(row.get('RESPONSABLE', ''))[:20], 1)
        pdf.cell(110, 8, prob, 1, 1)
    return pdf.output(dest='S').encode('latin-1')

def generar_excel(dataframe):
    # Usamos 'TIPO_EFECTO' para la columna "A QUIEN AFECTA"
    df_export = dataframe[['RESPONSABLE', 'CATEGORIA', 'FECHA_INICIO', 'FECHA DE CIERRE', 'PROBLEMA', 'TIPO_EFECTO']].copy()
    df_export.columns = ['RESPONSABLE', 'CATEGORIA', 'INICIO', 'CIERRE', 'DESCRIPCION', 'A QUIEN AFECTA']
    
    hoy = pd.Timestamp.today(tz='America/Argentina/Cordoba').date()
    
    output = io.BytesIO()
    # Usamos el engine xlsxwriter para inyectar colores y formato de celda
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df_export.to_excel(writer, index=False, sheet_name='Pendientes')
    
    workbook = writer.book
    worksheet = writer.sheets['Pendientes']
    
    # Definimos los estilos (colores de las celdas, bordes, alineaciones)
    header_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#D9D9D9', 'align': 'center'})
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center'})
    red_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center'})
    green_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center'})
    cell_format = workbook.add_format({'border': 1})
    
    # Escribimos los encabezados con estilo
    for col_num, value in enumerate(df_export.columns.values):
        worksheet.write(0, col_num, value, header_format)
        
    # Ajustamos el ancho de las columnas
    worksheet.set_column('A:B', 20)
    worksheet.set_column('C:D', 15)
    worksheet.set_column('E:E', 60)
    worksheet.set_column('F:F', 25)
    
    # Evaluamos fila por fila para inyectar las fechas y colores correspondientes
    for row_num in range(len(df_export)):
        for col_num in range(len(df_export.columns)):
            col_name = df_export.columns[col_num]
            val = df_export.iloc[row_num, col_num]
            
            # Validamos celdas vacías
            if pd.isna(val) or val == "":
                worksheet.write(row_num + 1, col_num, "", cell_format)
            # Aplicamos los colores rojo/verde para la columna CIERRE
            elif col_name == 'CIERRE':
                if val.date() < hoy:
                    worksheet.write_datetime(row_num + 1, col_num, val, red_format)
                else:
                    worksheet.write_datetime(row_num + 1, col_num, val, green_format)
            # Aplicamos formato de fecha normal a la columna INICIO
            elif col_name == 'INICIO':
                worksheet.write_datetime(row_num + 1, col_num, val, date_format)
            # Para el resto, aplicamos formato normal
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
        areas_list = sorted(df['ÁREA_PRINCIPAL'].dropna().astype(str).unique().tolist())
        f_area = st.selectbox("📍 Planta:", ["Todas"] + areas_list)
        
        resp_list = sorted(df['RESPONSABLE'].dropna().astype(str).unique().tolist())
        f_responsable = st.selectbox("👤 Responsable:", ["Todos"] + resp_list)

    with col_filtro2:
        detecto_list = sorted(df['AREA_ENCUENTRA'].dropna().astype(str).unique().tolist())
        f_detecto = st.selectbox("🔍 Área que detectó:", ["Todas"] + detecto_list)
        
        if 'TIPO_EFECTO' in df.columns:
            efectos_list = sorted(df['TIPO_EFECTO'].dropna().astype(str).unique().tolist())
        else:
            efectos_list = []
        f_efecto = st.selectbox("⚠️ Tipo de Efecto:", ["Todos"] + efectos_list)

# --- APLICACIÓN DE LOS FILTROS ---
if busqueda:
    df_activos = df_activos[df_activos['PROBLEMA'].str.contains(busqueda, case=False, na=False)]
if f_area != "Todas":
    df_activos = df_activos[df_activos['ÁREA_PRINCIPAL'] == f_area]
if f_responsable != "Todos":
    df_activos = df_activos[df_activos['RESPONSABLE'] == f_responsable]
if f_detecto != "Todas":
    df_activos = df_activos[df_activos['AREA_ENCUENTRA'] == f_detecto]
if f_efecto != "Todos":
    df_activos = df_activos[df_activos['TIPO_EFECTO'] == f_efecto]


# ==========================================
# 5. TARJETAS ACTIVAS
# ==========================================
st.subheader(f"📋 Pendientes ({len(df_activos)})")
hoy = pd.Timestamp.today(tz='America/Argentina/Cordoba').date()

if not df_activos.empty:
    for _, row in df_activos.iterrows():
        with st.container(border=True):
            
            # Formatear Fecha de Inicio (la original)
            f_inicio = row.get('FECHA_INICIO')
            txt_inicio = f_inicio.strftime("%d/%m/%Y") if pd.notna(f_inicio) else "Sin dato"

            # Formatear Fecha de Cierre (la última registrada) y aplicar colores en UI
            f_cierre = row.get('FECHA DE CIERRE')
            if pd.notna(f_cierre):
                f_str = f_cierre.strftime("%d/%m/%Y")
                color = "green" if f_cierre.date() >= hoy else "red"
                txt_cierre = f":{color}[**📅 Cierre: {f_str}**]"
            else:
                txt_cierre = "**📅 Cierre:** Sin asignar"

            st.markdown(f"**Ticket:** {row['N° DE TICKET']} | **📅 Inicio:** {txt_inicio} | {txt_cierre}")
            st.markdown(f"**📂 Categoría:** {row.get('CATEGORIA', 'N/A')} | **⚠️ Efecto:** {row.get('TIPO_EFECTO', 'N/A')}")
            st.markdown(f"**📍 Área:** {row['ÁREA_PRINCIPAL']}")
            st.markdown(f"**🔍 Detectó:** {row['AREA_ENCUENTRA']} | **👤 Responsable:** {row['RESPONSABLE']}")
            st.markdown(f"**📌 Estado:** {row['ESTADO']}")
            
            st.error(f"**Descripción:**\n{row['PROBLEMA']}")
            
            st.link_button("🔄 Actualizar / Editar Ticket", row['ACCIÓN'], use_container_width=True)

    st.divider()
    
    # --- BOTONES DE DESCARGA EN COLUMNAS ---
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
                # También muestra la fecha inicio correcta en el historial
                f_ini_c = row.get('FECHA_INICIO')
                txt_ini_c = f_ini_c.strftime("%d/%m/%Y") if pd.notna(f_ini_c) else "Sin dato"
                
                st.markdown(f"**Ticket {row['N° DE TICKET']}** | 📅 Inicio: {txt_ini_c} | {row.get('CATEGORIA', 'N/A')} | Efecto: {row.get('TIPO_EFECTO', 'N/A')}")
                st.success(f"**Resuelto:**\n{row['PROBLEMA']}")
