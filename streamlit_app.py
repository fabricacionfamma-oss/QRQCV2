import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# ==========================================
# 1. CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(page_title="Tablero QRQC", layout="centered")

# Enlaces de Google
url_ingresos = "https://docs.google.com/spreadsheets/d/1xw4aqqpf6pWDa9LQSmS3ztLiF82n-ZQ0NqY3QRVTTFg/edit"
url_form_nuevo = "https://docs.google.com/forms/d/e/1FAIpQLSe9AHzNLjUkg3tdfbsUopdc8_YldXLk4YbGXYaeNKyWA198vQ/viewform"
url_base_form_actualizacion = "https://docs.google.com/forms/d/e/1FAIpQLSfppxJI7lPOKbFQZwsDzTBYdv4hWq3QN9ImKCkAvmVCLV0wDw/viewform?entry.1541179458="

st.title("🏭 Tablero de Control QRQC")

st.link_button("➕ INGRESAR NUEVO TICKET / PROBLEMA", url_form_nuevo, use_container_width=True, type="primary")

st.divider()

if st.button("🔄 Actualizar Tabla de Datos", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 2. CONEXIÓN Y LECTURA DE DATOS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=url_ingresos, ttl=300)

df.columns = df.columns.str.strip()

if df.empty:
    st.warning("No hay datos registrados en el sistema.")
    st.stop()

# ==========================================
# 3. PROCESAMIENTO Y COLUMNAS
# ==========================================
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

# ==========================================
# 4. FILTRADO Y GENERACIÓN DE PDF
# ==========================================
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)

df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

def generar_pdf(dataframe):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Listado de Fallos / Problemas Activos", ln=True, align='C')
    pdf.ln(5)
    
    for index, row in dataframe.iterrows():
        area = str(row['ÁREA']).encode('latin-1', 'replace').decode('latin-1')
        resp = str(row['RESPONSABLE']).encode('latin-1', 'replace').decode('latin-1')
        estado = str(row['ESTADO']).encode('latin-1', 'replace').decode('latin-1')
        problema = str(row['PROBLEMA']).encode('latin-1', 'replace').decode('latin-1')
        ticket = str(row.get('N° DE TICKET', 'S/N')).encode('latin-1', 'replace').decode('latin-1')

        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 6, txt=f"Ticket: {ticket} | Área: {area} | Resp: {resp} | Estado: {estado}", ln=True)
        
        pdf.set_font("Arial", '', 10)
        pdf.multi_cell(0, 6, txt=f"Problema: {problema}")
        pdf.ln(4)

    return bytes(pdf.output(dest='S'), 'latin-1')

# ==========================================
# 5. INTERFAZ VISUAL
# ==========================================

# --- SECCIÓN 1: PROBLEMAS ACTIVOS ---
st.subheader("📋 Problemas en Curso / Pendientes")

if not df_activos.empty:
    st.dataframe(
        df_activos[columnas_visibles],
        use_container_width=True,
        hide_index=True,
        height=600, # <-- ALTURA AJUSTADA PARA MOSTRAR ~15 PROBLEMAS
        column_config={
            "ÁREA": st.column_config.TextColumn("Área", width="small"),
            "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large"), # <-- MAXIMO ESPACIO
            "RESPONSABLE": st.column_config.TextColumn("Responsable", width="small"),
            "ESTADO": st.column_config.TextColumn("Estado", width="small"),
            "ACCIÓN": st.column_config.LinkColumn("Actualizar", display_text="🔄 Actualizar", width="small") # <-- AJUSTADO AL TEXTO
        }
    )
    
    # --- BOTÓN DE DESCARGA PDF ---
    pdf_bytes = generar_pdf(df_activos)
    st.download_button(
        label="📄 Descargar Listado en PDF",
        data=pdf_bytes,
        file_name="Listado_Fallos_Activos.pdf",
        mime="application/pdf",
        use_container_width=True
    )
    
else:
    st.success("✅ No hay problemas pendientes en este momento.")

st.divider()

# --- SECCIÓN 2: PROBLEMAS CERRADOS ---
with st.expander("✅ VER HISTORIAL DE PROBLEMAS CERRADOS"):
    if not df_cerrados.empty:
        columnas_cerrados = ['ÁREA', 'PROBLEMA', 'RESPONSABLE', 'ESTADO']
        st.dataframe(
            df_cerrados[columnas_cerrados],
            use_container_width=True,
            hide_index=True,
            height=600, # <-- ALTURA AJUSTADA PARA MOSTRAR ~15 PROBLEMAS TAMBIÉN AQUÍ
            column_config={
                "ÁREA": st.column_config.TextColumn("Área", width="small"),
                "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large"),
                "RESPONSABLE": st.column_config.TextColumn("Responsable", width="small"),
                "ESTADO": st.column_config.TextColumn("Estado", width="small")
            }
        )
    else:
        st.write("Aún no hay registros marcados como 'CIERRE'.")
