import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(page_title="Listado de Problemas", layout="centered")
st.title("📋 Listado de Problemas")

# Enlace a la hoja principal
url_ingresos = "https://docs.google.com/spreadsheets/d/1xw4aqqpf6pWDa9LQSmS3ztLiF82n-ZQ0NqY3QRVTTFg/edit"

if st.button("🔄 Actualizar Datos", type="primary"):
    st.cache_data.clear()
    st.rerun()

st.divider()

# ==========================================
# 2. CONEXIÓN Y LECTURA DE DATOS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=url_ingresos, ttl=300)

# Limpiar espacios en los nombres de las columnas
df.columns = df.columns.str.strip()

if df.empty:
    st.warning("No hay datos cargados en el formulario todavía.")
    st.stop()

# ==========================================
# 3. PROCESAMIENTO Y FILTRADO DE COLUMNAS
# ==========================================
# Mapeamos los nombres EXACTOS de tu Google Sheet a los nombres limpios para la tabla.
mapeo_columnas = {
    'AREA': 'ÁREA',
    'DESCRIPCION DE FALLA': 'PROBLEMA',
    'QUE AREA ES RESPONSABLE DE EL PROBLEMA?': 'RESPONSABLE',
    'MOTIVO DE LA CARGA': 'ESTADO' 
}

# Renombramos las columnas
df = df.rename(columns=mapeo_columnas)

# Definimos las 4 columnas estrictas que solicitaste
columnas_finales = ['ÁREA', 'PROBLEMA', 'RESPONSABLE', 'ESTADO']

# Escudo protector: Si falta alguna columna, la rellenamos para evitar errores
for col in columnas_finales:
    if col not in df.columns:
        if col == 'ESTADO':
            df[col] = 'Pendiente'
        else:
            df[col] = 'Sin asignar'

# ==========================================
# 4. INTERFAZ VISUAL (LA TABLA)
# ==========================================
st.dataframe(
    df[columnas_finales],
    use_container_width=True,
    hide_index=True,
    column_config={
        "ÁREA": st.column_config.TextColumn("Área", width="medium"),
        "PROBLEMA": st.column_config.TextColumn("Problema", width="large"),
        "RESPONSABLE": st.column_config.TextColumn("Responsable", width="medium"),
        "ESTADO": st.column_config.TextColumn("Estado", width="small")
    }
)
