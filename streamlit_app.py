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
# 4. FILTRADO Y GENERACIÓN DE PDF HORIZONTAL
# ==========================================
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)

df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

def generar_pdf(dataframe):
    # Crear PDF en formato 'L' (Landscape / Horizontal)
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False) # Manejamos los saltos de página manualmente para la tabla
    pdf.add_page()
    
    # Título Principal
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Listado de Fallos / Problemas Activos", ln=True, align='C')
    pdf.ln(5)
    
    # Configuración de anchos de columnas (Total ~277mm para ocupar toda la hoja horizontal)
    w_ticket = 25
    w_area = 40
    w_resp = 40
    w_estado = 32
    w_prob = 140
    
    # Función interna para imprimir los encabezados de la tabla
    def imprimir_encabezados():
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(220, 220, 220) # Fondo gris claro
        pdf.cell(w_ticket, 8, "Ticket", border=1, fill=True, align='C')
        pdf.cell(w_area, 8, "Área", border=1, fill=True, align='C')
        pdf.cell(w_resp, 8, "Responsable", border=1, fill=True, align='C')
        pdf.cell(w_estado, 8, "Estado", border=1, fill=True, align='C')
        pdf.cell(w_prob, 8, "Descripción del Problema", border=1, fill=True, align='C')
        pdf.ln()

    imprimir_encabezados()
    pdf.set_font("Arial", '', 9)
    
    for index, row in dataframe.iterrows():
        # Limpieza de textos para la librería FPDF
        area = str(row['ÁREA']).encode('latin-1', 'replace').decode('latin-1')
        resp = str(row['RESPONSABLE']).encode('latin-1', 'replace').decode('latin-1')
        estado = str(row['ESTADO']).encode('latin-1', 'replace').decode('latin-1')
        problema = str(row['PROBLEMA']).encode('latin-1', 'replace').decode('latin-1')
        ticket = str(row.get('N° DE TICKET', 'S/N')).encode('latin-1', 'replace').decode('latin-1')

        # Control de salto de página (Si estamos muy cerca del borde inferior, ~180mm)
        lineas_estimadas = max(1, len(problema) / 70) 
        alto_estimado = lineas_estimadas * 6
        if pdf.get_y() + alto_estimado > 180: 
            pdf.add_page()
            imprimir_encabezados()
            pdf.set_font("Arial", '', 9)

        # Guardamos las coordenadas iniciales (X, Y) de la fila
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # 1. Imprimimos el texto largo primero para ver cuánto espacio hacia abajo (Y) ocupa
        pdf.set_xy(x_start + w_ticket + w_area + w_resp + w_estado, y_start)
        pdf.multi_cell(w_prob, 6, problema, border=1)
        y_end = pdf.get_y()
        
        # 2. Calculamos la altura real que tomó la fila
        row_height = y_end - y_start
        
        # 3. Dibujamos el resto de las celdas con la altura exacta para que los bordes cuadren
        pdf.set_xy(x_start, y_start)
        pdf.cell(w_ticket, row_height, ticket, border=1, align='C')
        pdf.cell(w_area, row_height, area, border=1, align='C')
        pdf.cell(w_resp, row_height, resp, border=1, align='C')
        pdf.cell(w_estado, row_height, estado, border=1, align='C')
        
        # 4. Movemos el cursor listo para la siguiente fila
        pdf.set_xy(x_start, y_end)

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
        height=600, 
        column_config={
            "ÁREA": st.column_config.TextColumn("Área", width="small"),
            "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large"), 
            "RESPONSABLE": st.column_config.TextColumn("Responsable", width="small"),
            "ESTADO": st.column_config.TextColumn("Estado", width="small"),
            "ACCIÓN": st.column_config.LinkColumn("Actualizar", display_text="🔄 Actualizar", width="small")
        }
    )
    
    # --- BOTÓN DE DESCARGA PDF ---
    pdf_bytes = generar_pdf(df_activos)
    st.download_button(
        label="📄 Descargar Tabla en PDF (Horizontal)",
        data=pdf_bytes,
        file_name="Reporte_Fallos_Activos.pdf",
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
            height=600, 
            column_config={
                "ÁREA": st.column_config.TextColumn("Área", width="small"),
                "PROBLEMA": st.column_config.TextColumn("Descripción del Problema", width="large"),
                "RESPONSABLE": st.column_config.TextColumn("Responsable", width="small"),
                "ESTADO": st.column_config.TextColumn("Estado", width="small")
            }
        )
    else:
        st.write("Aún no hay registros marcados como 'CIERRE'.")
