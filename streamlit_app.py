import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# ==========================================
# 1. CONFIGURACIÓN INICIAL Y HACK CSS MÓVIL
# ==========================================
# Eliminamos la barra lateral por completo
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
url_form_nuevo = "https://docs.google.com/forms/d/e/1FAIpQLSe9AHzNLjUkg3tdfbsUopdc8_YldXLk4YbGXYaeNKyWA198vQ/viewform"
url_base_form_actualizacion = "https://docs.google.com/forms/d/e/1FAIpQLSfppxJI7lPOKbFQZwsDzTBYdv4hWq3QN9ImKCkAvmVCLV0wDw/viewform?entry.1541179458="

# ==========================================
# 2. CONEXIÓN Y LECTURA DE DATOS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=url_ingresos, ttl=300)

if df.empty:
    st.warning("No hay datos registrados en el sistema.")
    st.stop()

# Limpieza y mapeo
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

# Generador PDF (Puedes reemplazar esto con tu función original completa si lo prefieres)
def generar_pdf(dataframe):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Listado de Fallos / Problemas Activos", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 8, "Ticket", 1)
    pdf.cell(40, 8, "Area", 1)
    pdf.cell(40, 8, "Responsable", 1)
    pdf.cell(30, 8, "Estado", 1)
    pdf.cell(140, 8, "Problema", 1, 1)
    pdf.set_font("Arial", '', 9)
    for _, row in dataframe.iterrows():
        prob = str(row['PROBLEMA'])[:100].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(20, 8, str(row.get('N° DE TICKET', '-')), 1)
        pdf.cell(40, 8, str(row['ÁREA'])[:20], 1)
        pdf.cell(40, 8, str(row['RESPONSABLE'])[:20], 1)
        pdf.cell(30, 8, str(row['ESTADO']), 1)
        pdf.cell(140, 8, prob, 1, 1)
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. INTERFAZ VISUAL: ENCABEZADO Y FILTROS
# ==========================================
st.title("🏭 Tablero QRQC")
st.link_button("➕ INGRESAR NUEVO TICKET", url_form_nuevo, use_container_width=True, type="primary")

if st.button("🔄 Actualizar Datos", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.divider()

# --- BUSCADOR Y FILTROS EN PANTALLA PRINCIPAL ---
# Usamos un expander para que no ocupe toda la pantalla del celular al inicio
with st.expander("🔍 Buscar y Filtrar Problemas", expanded=False):
    termino_busqueda = st.text_input("Buscar palabra (Ej: motor, fuga...):")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        areas = sorted(df['ÁREA'].dropna().unique().tolist())
        filtro_area = st.selectbox("📍 Área:", ["Todas"] + areas)
    with col_f2:
        resps = sorted(df_activos['RESPONSABLE'].dropna().unique().tolist())
        filtro_resp = st.selectbox("👤 Resp:", ["Todos"] + resps)

# Aplicar los filtros
if termino_busqueda:
    df_activos = df_activos[
        df_activos['PROBLEMA'].str.contains(termino_busqueda, case=False, na=False) | 
        df_activos['ÁREA'].str.contains(termino_busqueda, case=False, na=False)
    ]
if filtro_area != "Todas":
    df_activos = df_activos[df_activos['ÁREA'] == filtro_area]
if filtro_resp != "Todos":
    df_activos = df_activos[df_activos['RESPONSABLE'] == filtro_resp]

# ==========================================
# 4. TARJETAS DE PROBLEMAS (ESTÉTICA RECUPERADA)
# ==========================================
st.subheader(f"📋 Pendientes ({len(df_activos)})")

if not df_activos.empty:
    for index, row in df_activos.iterrows():
        with st.container(border=True):
            # Recuperamos el formato original que te gustaba
            resp_app = row['RESPONSABLE'] if str(row['RESPONSABLE']).lower() != 'nan' else 'Sin asignar'
            
            st.markdown(f"**📍 Área:** {row['ÁREA']}")
            st.markdown(f"**👤 Resp:** {resp_app} | **📌 Estado:** {row['ESTADO']}")
            
            # El st.error le da ese cuadro rojo/rosado que destaca la descripción
            st.error(f"**Descripción del Problema:**\n{row['PROBLEMA']}")
            
            if row['ACCIÓN']:
                st.link_button("🔄 Actualizar Ticket", row['ACCIÓN'], use_container_width=True)

    # --- BOTÓN DE DESCARGA PDF AL FONDO ---
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
# 5. HISTORIAL DE CERRADOS
# ==========================================
with st.expander("✅ VER HISTORIAL DE PROBLEMAS CERRADOS"):
    if not df_cerrados.empty:
        st.caption(f"Mostrando {len(df_cerrados)} problemas cerrados.")
        for index, row in df_cerrados.iterrows():
            with st.container(border=True):
                resp_app = row['RESPONSABLE'] if str(row['RESPONSABLE']).lower() != 'nan' else '-'
                st.markdown(f"**📍 Área:** {row['ÁREA']} | **👤 Resp:** {resp_app}")
                # El st.success le da el cuadro verde de solucionado
                st.success(f"**Problema Resuelto:**\n{row['PROBLEMA']}")
    else:
        st.write("Aún no hay registros marcados como 'CIERRE'.")
