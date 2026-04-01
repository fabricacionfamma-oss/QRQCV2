import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import urllib.parse

# ==========================================
# 1. CONFIGURACIÓN INICIAL Y CSS
# ==========================================
st.set_page_config(page_title="Tablero QRQC", layout="centered")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem !important; }
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
    st.warning("No hay datos registrados.")
    st.stop()

# Limpieza inicial
df = df_raw.copy()
df.columns = df.columns.str.strip()

# --- TRUCO PARA ACTUALIZACIONES ---
# 1. Aseguramos que el N° de Ticket sea tratado como texto limpio
if 'N° DE TICKET' in df.columns:
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False).str.strip()
    # 2. IMPORTANTÍSIMO: Eliminamos duplicados quedándonos solo con la ÚLTIMA fila de cada ticket
    # Esto hace que si actualizas el ticket "5", solo veas la última versión enviada.
    df = df.drop_duplicates(subset=['N° DE TICKET'], keep='last')

# Mapeo de nombres para la interfaz
mapeo = {
    'AREA': 'ÁREA',
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE',
    'MOTIVO DE LA CARGA': 'ESTADO'
}
df = df.rename(columns=mapeo)

# Parseo de Fecha de Cierre
if 'FECHA DE CIERRE' in df.columns:
    df['FECHA DE CIERRE'] = pd.to_datetime(df['FECHA DE CIERRE'], errors='coerce', dayfirst=True)
else:
    df['FECHA DE CIERRE'] = pd.NaT

# --- FUNCIÓN GENERADORA DE LINKS CON TUS IDs REALES ---
def generar_link_actualizacion(row):
    # Extraemos y codificamos los valores actuales
    ticket = urllib.parse.quote(str(row.get('N° DE TICKET', '')))
    area = urllib.parse.quote(str(row.get('ÁREA', '')))
    resp = urllib.parse.quote(str(row.get('RESPONSABLE', '')))
    desc = urllib.parse.quote(str(row.get('PROBLEMA', '')))
    estado = urllib.parse.quote(str(row.get('ESTADO', '')))
    
    # Manejo de fecha (formato YYYY-MM-DD para Google Forms)
    fecha_val = row.get('FECHA DE CIERRE')
    fecha_str = ""
    if pd.notna(fecha_val):
        fecha_str = fecha_val.strftime("%Y-%m-%d")

    # IDs que extrajimos de tu enlace:
    params = {
        "entry.809586642": ticket,    # N° de Ticket
        "entry.1541179458": area,      # Área
        "entry.1946844485": resp,      # Responsable
        "entry.552314530": desc,       # Descripción
        "entry.705803950": estado,     # Estado
        "entry.536779116": fecha_str   # Fecha Cierre
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{url_form}?usp=pp_url&{query_string}"

# Crear la columna de acción
df['ACCIÓN'] = df.apply(generar_link_actualizacion, axis=1)

# Separar activos de cerrados
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)
df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

# ==========================================
# 3. INTERFAZ VISUAL
# ==========================================
st.title("🏭 Tablero QRQC")
st.link_button("➕ INGRESAR NUEVO TICKET", url_form, use_container_width=True, type="primary")

if st.button("🔄 Actualizar App", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.divider()

# Filtros
with st.expander("🔍 Buscador y Filtros"):
    busqueda = st.text_input("Buscar por palabra:")
    areas = sorted(df['ÁREA'].dropna().unique().tolist())
    f_area = st.selectbox("📍 Área:", ["Todas"] + areas)

if busqueda:
    df_activos = df_activos[df_activos['PROBLEMA'].str.contains(busqueda, case=False, na=False)]
if f_area != "Todas":
    df_activos = df_activos[df_activos['ÁREA'] == f_area]

# Listado de tarjetas
st.subheader(f"📋 Pendientes ({len(df_activos)})")
hoy = pd.Timestamp.today().date()

for _, row in df_activos.iterrows():
    with st.container(border=True):
        # Lógica de colores para fecha
        f_cierre = row['FECHA DE CIERRE']
        if pd.notna(f_cierre):
            f_str = f_cierre.strftime("%d/%m/%Y")
            color = "green" if f_cierre.date() >= hoy else "red"
            txt_fecha = f"**:{color}[📅 Cierre: {f_str}]**"
        else:
            txt_fecha = "📅 Sin fecha"

        st.markdown(f"**Ticket:** {row['N° DE TICKET']} | {txt_fecha}")
        st.markdown(f"**📍 Área:** {row['ÁREA']} | **👤 Resp:** {row['RESPONSABLE']}")
        st.markdown(f"**📌 Motivo de la Carga:** {row['ESTADO']}")
        st.error(f"**Descripción:**\n{row['PROBLEMA']}")
        
        st.link_button("🔄 Actualizar Datos de este Ticket", row['ACCIÓN'], use_container_width=True)

# Historial
with st.expander("✅ VER HISTORIAL CERRADOS"):
    for _, row in df_cerrados.iterrows():
        with st.container(border=True):
            st.write(f"**Ticket {row['N° DE TICKET']}** - {row['ÁREA']}")
            st.success(row['PROBLEMA'])
