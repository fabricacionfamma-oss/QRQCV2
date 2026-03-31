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

st.title("🏭 Tablero de Control QRQC")

# --- BOTÓN PARA INGRESAR NUEVO PROBLEMA ---
st.link_button("➕ INGRESAR NUEVO TICKET / PROBLEMA", url_form_nuevo, use_container_width=True, type="primary")

st.divider()

# Botón de actualización manual
if st.button("🔄 Actualizar Tabla de Datos", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 2. CONEXIÓN Y LECTURA DE DATOS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=url_ingresos, ttl=300)

# Limpieza básica
df.columns = df.columns.str.strip()

if df.empty:
    st.warning("No hay datos registrados en el sistema.")
    st.stop()

# ==========================================
# 3. PROCESAMIENTO Y COLUMNAS
# ==========================================
# Mapeo exacto según tus columnas del Formulario
mapeo_columnas = {
    'AREA': 'ÁREA',
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE',
    'MOTIVO DE LA CARGA': 'ESTADO'
}

df = df.rename(columns=mapeo_columnas)

# Columnas que vamos a mostrar
columnas_visibles = ['ÁREA', 'PROBLEMA', 'RESPONSABLE', 'ESTADO']

# Asegurar que existan (por seguridad)
for col in columnas_visibles:
    if col not in df.columns:
        df[col] = "N/A"

# ==========================================
# 4. FILTRADO (ACTIVOS VS CERRADOS)
# ==========================================
# Consideramos "Cerrado" si el estado contiene la palabra "CIERRE"
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
            "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large"),
            "ESTADO": st.column_config.TextColumn("Estado", width="small")
        }
    )
else:
    st.success("✅ No hay problemas pendientes en este momento.")

st.divider()

# --- SECCIÓN 2: PROBLEMAS CERRADOS ---
with st.expander("✅ VER HISTORIAL DE PROBLEMAS CERRADOS"):
    if not df_cerrados.empty:
        st.dataframe(
            df_cerrados[columnas_visibles],
            use_container_width=True,
            hide_index=True,
            column_config={
                "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large")
            }
        )
    else:
        st.write("Aún no hay registros marcados como 'CIERRE'.")
