import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import urllib.parse

# ==========================================
# 1. CONFIGURACIÓN INICIAL Y CSS MÓVIL
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

# --- TRUCO PARA ACTUALIZACIONES (MANTENER SOLO EL ÚLTIMO) ---
if 'N° DE TICKET' in df.columns:
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False).str.strip()
    # Eliminamos filas sin ticket (opcional, por seguridad)
    df = df[df['N° DE TICKET'] != 'nan']
    # Eliminamos duplicados basándonos en el Ticket, dejando solo la versión más reciente
    df = df.drop_duplicates(subset=['N° DE TICKET'], keep='last')

# Mapeo de nombres para que el código sea más fácil de leer
mapeo = {
    'AREA': 'ÁREA_PRINCIPAL',
    'QUE AREA ENCUENTRA EL PROBLEMA?': 'AREA_ENCUENTRA',
    'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE',
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'MOTIVO DE LA CARGA': 'ESTADO'
}
df = df.rename(columns=mapeo)

# Parseo de Fecha de Cierre
if 'FECHA DE CIERRE' in df.columns:
    df['FECHA DE CIERRE'] = pd.to_datetime(df['FECHA DE CIERRE'], errors='coerce', dayfirst=True)
else:
    df['FECHA DE CIERRE'] = pd.NaT

# --- FUNCIÓN GENERADORA DE LINKS CON TODOS LOS CAMPOS ---
def generar_link_actualizacion(row):
    # Función interna para codificar textos de forma segura para URLs
    def clean(val): 
        return urllib.parse.quote(str(val)) if pd.notna(val) and str(val).lower() != 'nan' else ""

    ticket = clean(row.get('N° DE TICKET'))
    area_p = clean(row.get('ÁREA_PRINCIPAL'))
    area_e = clean(row.get('AREA_ENCUENTRA'))
    resp   = clean(row.get('RESPONSABLE'))
    desc   = clean(row.get('PROBLEMA'))
    estado = clean(row.get('ESTADO'))
    
    # Fecha en formato YYYY-MM-DD para el formulario
    fecha_val = row.get('FECHA DE CIERRE')
    fecha_str = fecha_val.strftime("%Y-%m-%d") if pd.notna(fecha_val) else ""

    # IDs extraídos de tu enlace de Forms:
    params = {
        "entry.809586642": ticket,     # N° de Ticket
        "entry.1541179458": area_p,    # ÁREA
        "entry.1851030336": area_e,    # QUE ÁREA ENCUENTRA EL PROBLEMA
        "entry.1946844485": resp,      # QUE ÁREA ES RESPONSABLE
        "entry.552314530": desc,       # DESCRIPCIÓN DE FALLA
        "entry.705803950": estado,     # MOTIVO DE LA CARGA (ESTADO)
        "entry.536779116": fecha_str   # FECHA DE CIERRE
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{url_form}?usp=pp_url&{query_string}"

# Crear la columna con el link dinámico
df['ACCIÓN'] = df.apply(generar_link_actualizacion, axis=1)

# Completar columnas faltantes con N/A por seguridad visual
columnas_visibles = ['ÁREA_PRINCIPAL', 'AREA_ENCUENTRA', 'RESPONSABLE', 'PROBLEMA', 'ESTADO', 'ACCIÓN']
for col in columnas_visibles:
    if col not in df.columns:
        df[col] = "N/A"

# Separar activos de cerrados para la vista
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)
df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

# ==========================================
# 3. GENERADOR DE PDF
# ==========================================
def generar_pdf(dataframe):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Listado de Fallos / Problemas Activos", ln=True, align='C')
    pdf.ln(5)
    
    # Encabezados de tabla
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 8, "Ticket", 1)
    pdf.cell(40, 8, "Area", 1)
    pdf.cell(40, 8, "Responsable", 1)
    pdf.cell(30, 8, "Estado", 1)
    pdf.cell(140, 8, "Problema", 1, 1)
    
    # Contenido de tabla
    pdf.set_font("Arial", '', 9)
    for _, row in dataframe.iterrows():
        prob = str(row.get('PROBLEMA', ''))[:100].encode('latin-1', 'replace').decode('latin-1')
        ticket_val = str(row.get('N° DE TICKET', '-'))
        area_val = str(row.get('ÁREA_PRINCIPAL', ''))[:20]
        resp_val = str(row.get('RESPONSABLE', ''))[:20]
        estado_val = str(row.get('ESTADO', ''))
        
        pdf.cell(20, 8, ticket_val, 1)
        pdf.cell(40, 8, area_val, 1)
        pdf.cell(40, 8, resp_val, 1)
        pdf.cell(30, 8, estado_val, 1)
        pdf.cell(140, 8, prob, 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. INTERFAZ VISUAL: ENCABEZADO Y FILTROS
# ==========================================
st.title("🏭 Tablero QRQC")
st.link_button("➕ INGRESAR NUEVO TICKET", url_form, use_container_width=True, type="primary")

if st.button("🔄 Actualizar App", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.divider()

# Buscador y Filtros
with st.expander("🔍 Buscador y Filtros"):
    busqueda = st.text_input("Buscar por palabra en la falla:")
    areas_list = sorted(df['ÁREA_PRINCIPAL'].dropna().unique().tolist())
    f_area = st.selectbox("📍 Filtrar por Área:", ["Todas"] + areas_list)

if busqueda:
    df_activos = df_activos[df_activos['PROBLEMA'].str.contains(busqueda, case=False, na=False)]
if f_area != "Todas":
    df_activos = df_activos[df_activos['ÁREA_PRINCIPAL'] == f_area]

# ==========================================
# 5. TARJETAS DE PROBLEMAS ACTIVOS
# ==========================================
st.subheader(f"📋 Pendientes ({len(df_activos)})")

# Obtenemos la fecha actual ajustada a la zona horaria de Argentina
hoy = pd.Timestamp.today(tz='America/Argentina/Cordoba').date()

if not df_activos.empty:
    for _, row in df_activos.iterrows():
        with st.container(border=True):
            # Semáforo de fecha
            f_cierre = row['FECHA DE CIERRE']
            if pd.notna(f_cierre):
                f_str = f_cierre.strftime("%d/%m/%Y")
                color = "green" if f_cierre.date() >= hoy else "red"
                txt_fecha = f"**:{color}[📅 Cierre: {f_str}]**"
            else:
                txt_fecha = "**📅 Cierre:** Sin asignar"

            st.markdown(f"**Ticket:** {row['N° DE TICKET']} | {txt_fecha}")
            st.markdown(f"**📍 Área:** {row['ÁREA_PRINCIPAL']}")
            st.markdown(f"**🔍 Detectó:** {row['AREA_ENCUENTRA']} | **👤 Responsable:** {row['RESPONSABLE']}")
            st.markdown(f"**📌 Estado:** {row['ESTADO']}")
            
            st.error(f"**Descripción del Problema:**\n{row['PROBLEMA']}")
            
            st.link_button("🔄 Actualizar / Editar Ticket", row['ACCIÓN'], use_container_width=True)

    # --- BOTÓN DE DESCARGA PDF ---
    st.divider()
    pdf_bytes = generar_pdf(df_activos)
    st.download_button(
        label="📄 Descargar Listado en PDF",
        data=pdf_bytes,
        file_name="Reporte_Fallos_Activos.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="secondary"
    )
else:
    st.success("✅ No se encontraron problemas activos con los filtros aplicados.")

st.divider()

# ==========================================
# 6. HISTORIAL DE CERRADOS
# ==========================================
with st.expander("✅ VER HISTORIAL CERRADOS"):
    if df_cerrados.empty:
        st.write("No hay tickets cerrados aún.")
    else:
        st.caption(f"Mostrando {len(df_cerrados)} problemas cerrados.")
        for _, row in df_cerrados.iterrows():
            with st.container(border=True):
                st.markdown(f"**Ticket {row['N° DE TICKET']}** | **📍 Área:** {row['ÁREA_PRINCIPAL']}")
                st.markdown(f"**📌 Motivo de la Carga:** {row['ESTADO']}")
                st.success(f"**Problema Resuelto:**\n{row['PROBLEMA']}")
