import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# ==========================================
# 1. CONFIGURACIÓN INICIAL Y HACK CSS (MÓVIL)
# ==========================================
# initial_sidebar_state="collapsed" asegura que el menú esté cerrado en móviles al iniciar
st.set_page_config(page_title="Tablero QRQC", layout="centered", initial_sidebar_state="collapsed")

# CSS para forzar la vista móvil (elimina márgenes y oculta elementos innecesarios)
st.markdown("""
    <style>
        /* Reducir el padding general para aprovechar toda la pantalla del celular */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        /* Ocultar el menú superior de "Deploy" de Streamlit */
        header {visibility: hidden;}
        /* Ocultar el footer de "Made with Streamlit" */
        footer {visibility: hidden;}
        /* Ajustar el tamaño del texto para móviles */
        p, div, span, label {
            font-size: 15px !important;
        }
    </style>
""", unsafe_allow_html=True)

# Enlaces definitivos de Google
url_ingresos = "https://docs.google.com/spreadsheets/d/1xw4aqqpf6pWDa9LQSmS3ztLiF82n-ZQ0NqY3QRVTTFg/edit"
url_form_nuevo = "https://docs.google.com/forms/d/e/1FAIpQLSe9AHzNLjUkg3tdfbsUopdc8_YldXLk4YbGXYaeNKyWA198vQ/viewform"
url_base_form_actualizacion = "https://docs.google.com/forms/d/e/1FAIpQLSfppxJI7lPOKbFQZwsDzTBYdv4hWq3QN9ImKCkAvmVCLV0wDw/viewform?entry.1541179458="

# ==========================================
# 2. MENÚ LATERAL (SIDEBAR) PARA MÓVILES
# ==========================================
# En celulares, esto se convierte en el menú "hamburguesa" de la esquina superior izquierda
with st.sidebar:
    st.title("⚙️ Opciones")
    if st.button("🔄 Actualizar Datos Ahora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.write("Filtros de Búsqueda")
    # El selectbox de filtro lo inicializaremos vacío y lo llenaremos luego de cargar los datos
    filtro_container = st.empty() 
    
    st.divider()
    st.write("Acciones")
    # Movemos el botón de descarga del PDF al menú para no estorbar en la pantalla principal
    btn_descarga_pdf = st.empty()

# ==========================================
# 3. PANTALLA PRINCIPAL
# ==========================================
st.markdown("### 🏭 Tablero QRQC")
st.link_button("➕ NUEVO TICKET", url_form_nuevo, use_container_width=True, type="primary")

# Conexión y Lectura (igual que tu código)
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=url_ingresos, ttl=300)

if df.empty:
    st.warning("No hay datos registrados en el sistema.")
    st.stop()

# Procesamiento de columnas (igual que tu código)
df.columns = df.columns.str.strip()
mapeo_columnas = {
    'AREA': 'ÁREA',
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE',
    'MOTIVO DE LA CARGA': 'ESTADO'
}
df = df.rename(columns=mapeo_columnas)

if 'N° DE TICKET' in df.columns:
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df['ACCIÓN'] = url_base_form_actualizacion + df['N° DE TICKET']
else:
    df['ACCIÓN'] = None

columnas_visibles = ['ÁREA', 'PROBLEMA', 'RESPONSABLE', 'ESTADO', 'ACCIÓN']
for col in columnas_visibles:
    if col not in df.columns:
        df[col] = "N/A"

es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)
df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

# Generador PDF (Mantén tu función generar_pdf aquí tal cual está)
def generar_pdf(dataframe):
    pass # Reemplaza este 'pass' con tu función original generar_pdf()

# ==========================================
# 4. RENDERIZADO DE VISTA MÓVIL
# ==========================================

# Rellenar el filtro en el sidebar ahora que tenemos los datos
if not df_activos.empty:
    lista_responsables = sorted([str(r) for r in df_activos['RESPONSABLE'].unique() if str(r).lower() != 'nan'])
    opciones_filtro = ["Todos"] + lista_responsables
    with filtro_container:
        filtro_seleccionado = st.selectbox("👤 Responsable:", opciones_filtro)
    
    if filtro_seleccionado != "Todos":
        df_activos = df_activos[df_activos['RESPONSABLE'] == filtro_seleccionado]

# Dibujar botones de PDF en el sidebar
if not df_activos.empty:
    with btn_descarga_pdf:
        # pdf_bytes = generar_pdf(df_activos) # Descomenta cuando pongas tu función PDF
        # st.download_button("📄 Bajar PDF", data=pdf_bytes, file_name="Reporte.pdf", mime="application/pdf", use_container_width=True)
        pass

# --- TARJETAS DE PROBLEMAS ACTIVOS ---
st.markdown(f"**📌 Pendientes ({len(df_activos)})**")

if not df_activos.empty:
    # NOTA: ELIMINAMOS el st.container(height=600) para permitir el scroll táctil natural
    for index, row in df_activos.iterrows():
        with st.container(border=True):
            resp_app = row['RESPONSABLE'] if str(row['RESPONSABLE']).lower() != 'nan' else 'Sin asignar'
            
            # Usamos un markdown compacto en lugar de múltiples st.columns para evitar problemas visuales en el celular
            st.markdown(f"**📍 {row['ÁREA']}** | 👤 {resp_app}")
            st.markdown(f"**Estado:** `{row['ESTADO']}`")
            st.info(f"{row['PROBLEMA']}")
            
            if row['ACCIÓN']:
                st.link_button("✏️ Actualizar", row['ACCIÓN'], use_container_width=True)
else:
    st.success("✅ Todo resuelto.")

# --- HISTORIAL CERRADOS ---
st.write("") # Espaciador
with st.expander("✅ VER CERRADOS"):
    if not df_cerrados.empty:
        # Nuevamente, SIN altura fija para no trabar el celular
        for index, row in df_cerrados.iterrows():
            with st.container(border=True):
                resp_app = row['RESPONSABLE'] if str(row['RESPONSABLE']).lower() != 'nan' else '-'
                st.markdown(f"📍 {row['ÁREA']} | 👤 {resp_app}")
                st.markdown(f"_{row['PROBLEMA']}_")
    else:
        st.write("No hay registros cerrados.")
