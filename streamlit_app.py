import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# ==========================================
# 1. CONFIGURACIÓN E INYECCIÓN CSS MÓVIL
# ==========================================
st.set_page_config(page_title="Tablero QRQC", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        header {visibility: hidden;}
        footer {visibility: hidden;}
        /* Estilo para las tarjetas de tickets */
        .ticket-card {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            background-color: #f9f9f9;
        }
    </style>
""", unsafe_allow_html=True)

# Enlaces
url_ingresos = "https://docs.google.com/spreadsheets/d/1xw4aqqpf6pWDa9LQSmS3ztLiF82n-ZQ0NqY3QRVTTFg/edit"
url_form_nuevo = "https://docs.google.com/forms/d/e/1FAIpQLSe9AHzNLjUkg3tdfbsUopdc8_YldXLk4YbGXYaeNKyWA198vQ/viewform"
url_base_form_actualizacion = "https://docs.google.com/forms/d/e/1FAIpQLSfppxJI7lPOKbFQZwsDzTBYdv4hWq3QN9ImKCkAvmVCLV0wDw/viewform?entry.1541179458="

# ==========================================
# 2. FUNCIÓN GENERADORA DE PDF (ORIGINAL)
# ==========================================
def generar_pdf(dataframe):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Reporte de Problemas QRQC - Planta", ln=True, align='C')
    pdf.ln(5)
    
    # Encabezados
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(20, 8, "Ticket", 1, 0, 'C', True)
    pdf.cell(40, 8, "Area", 1, 0, 'C', True)
    pdf.cell(40, 8, "Responsable", 1, 0, 'C', True)
    pdf.cell(30, 8, "Estado", 1, 0, 'C', True)
    pdf.cell(140, 8, "Descripcion del Problema", 1, 1, 'C', True)
    
    pdf.set_font("Arial", '', 9)
    for _, row in dataframe.iterrows():
        # Limpieza simple de texto para evitar errores de encoding en FPDF
        prob = str(row['PROBLEMA'])[:100].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(20, 8, str(row.get('N° DE TICKET', '-')), 1)
        pdf.cell(40, 8, str(row['ÁREA'])[:20], 1)
        pdf.cell(40, 8, str(row['RESPONSABLE'])[:20], 1)
        pdf.cell(30, 8, str(row['ESTADO']), 1)
        pdf.cell(140, 8, prob, 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. LECTURA DE DATOS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=url_ingresos, ttl=300)

if df.empty:
    st.warning("No hay datos.")
    st.stop()

# Limpieza y mapeo
df.columns = df.columns.str.strip()
mapeo = {'AREA': 'ÁREA', 'DESCRIPCION DE FALLA': 'PROBLEMA', 
         'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE', 'MOTIVO DE LA CARGA': 'ESTADO'}
df = df.rename(columns=mapeo)

if 'N° DE TICKET' in df.columns:
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False)
    df['ACCIÓN'] = url_base_form_actualizacion + df['N° DE TICKET']

# Separación inicial
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)
df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

# ==========================================
# 4. SIDEBAR: BUSCADOR Y FILTROS
# ==========================================
with st.sidebar:
    st.title("🔍 Búsqueda y Filtros")
    
    # 1. BUSCADOR DE TEXTO
    termino_busqueda = st.text_input("Buscar en descripción o área:", placeholder="Ej: fuga, prensa...")
    
    # 2. FILTRO POR ÁREA
    areas = sorted(df['ÁREA'].dropna().unique().tolist())
    filtro_area = st.selectbox("📍 Filtrar por Área:", ["Todas"] + areas)
    
    # 3. FILTRO POR RESPONSABLE
    resps = sorted(df_activos['RESPONSABLE'].dropna().unique().tolist())
    filtro_resp = st.selectbox("👤 Filtrar por Responsable:", ["Todos"] + resps)
    
    st.divider()
    if st.button("🔄 Refrescar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- APLICAR FILTROS A DF_ACTIVOS ---
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
# 5. INTERFAZ PRINCIPAL
# ==========================================
st.subheader("🏭 Tablero de Control QRQC")
st.link_button("➕ INGRESAR NUEVO TICKET", url_form_nuevo, use_container_width=True, type="primary")

st.write(f"Mostrando **{len(df_activos)}** problemas activos.")

# Listado de tarjetas
if not df_activos.empty:
    for _, row in df_activos.iterrows():
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**{row['ÁREA']}**")
            with col_b:
                st.caption(f"ID: {row.get('N° DE TICKET', 'S/N')}")
            
            st.markdown(f"👤 **Resp:** {row['RESPONSABLE']}")
            st.warning(f"{row['PROBLEMA']}")
            st.caption(f"Status: {row['ESTADO']}")
            
            if row.get('ACCIÓN'):
                st.link_button("🔄 Actualizar / Editar", row['ACCIÓN'], use_container_width=True)

    # --- BOTÓN PDF AL FINAL ---
    st.divider()
    try:
        pdf_data = generar_pdf(df_activos)
        st.download_button(
            label="📄 DESCARGAR LISTADO (PDF)",
            data=pdf_data,
            file_name="reporte_qrqc_planta.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="secondary"
        )
    except Exception as e:
        st.error("Error al generar PDF. Verifique caracteres especiales.")

else:
    st.success("✅ No se encontraron problemas con los filtros aplicados.")

# Historial resumido
with st.expander("Ver Historial Cerrados"):
    st.dataframe(df_cerrados[['ÁREA', 'PROBLEMA', 'RESPONSABLE']], hide_index=True)
