import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(page_title="Tablero QRQC", layout="centered")

# Enlaces de Google
url_ingresos = "https://docs.google.com/spreadsheets/d/1xw4aqqpf6pWDa9LQSmS3ztLiF82n-ZQ0NqY3QRVTTFg/edit"
url_form_nuevo = "https://docs.google.com/forms/d/e/1FAIpQLSe9AHzNLjUkg3tdfbsUopdc8_YldXLk4YbGXYaeNKyWA198vQ/viewform"
url_base_form_actualizacion = "https://docs.google.com/forms/d/e/1FAIpQLSfppxJI7lPOKbFQZwsDzTBYdv4hWq3QN9ImKCkAvmVCLV0wDw/viewform?entry.1541179458="

st.title("🏭 Tablero de Control QRQC")

# Botón principal para nuevo ingreso
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
# Mapeo de columnas
mapeo_columnas = {
    'AREA': 'ÁREA',
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE',
    'MOTIVO DE LA CARGA': 'ESTADO'
}

df = df.rename(columns=mapeo_columnas)

# Generar el link de actualización si existe el N° DE TICKET
if 'N° DE TICKET' in df.columns:
    # Limpiamos el número por si Google Sheets lo trae como decimal (ej: 105.0)
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False).str.strip()
    # Creamos la columna con el enlace final
    df['ACCIÓN'] = url_base_form_actualizacion + df['N° DE TICKET']
else:
    df['ACCIÓN'] = None

# Columnas que vamos a mostrar (ahora son 5)
columnas_visibles = ['ÁREA', 'PROBLEMA', 'RESPONSABLE', 'ESTADO', 'ACCIÓN']

for col in columnas_visibles:
    if col not in df.columns:
        df[col] = "N/A"

# ==========================================
# 4. FILTRADO (ACTIVOS VS CERRADOS)
# ==========================================
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)

df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

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
        column_config={
            "ÁREA": st.column_config.TextColumn("Área", width="small"),
            "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large"),
            "RESPONSABLE": st.column_config.TextColumn("Responsable", width="small"),
            "ESTADO": st.column_config.TextColumn("Estado", width="small"),
            "ACCIÓN": st.column_config.LinkColumn("Actualizar", display_text="🔄 Actualizar")
        }
    )
else:
    st.success("✅ No hay problemas pendientes en este momento.")

st.divider()

# --- SECCIÓN 2: PROBLEMAS CERRADOS ---
with st.expander("✅ VER HISTORIAL DE PROBLEMAS CERRADOS"):
    if not df_cerrados.empty:
        # Para los cerrados, quitamos la columna 'ACCIÓN' porque ya no hace falta actualizarlos
        columnas_cerrados = ['ÁREA', 'PROBLEMA', 'RESPONSABLE', 'ESTADO']
        st.dataframe(
            df_cerrados[columnas_cerrados],
            use_container_width=True,
            hide_index=True,
            column_config={
                "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large")
            }
        )
    else:
        st.write("Aún no hay registros marcados como 'CIERRE'.")
