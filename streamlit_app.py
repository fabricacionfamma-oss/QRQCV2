¡Por supuesto! Aquí tienes el código completo y unificado con absolutamente todas las mejoras que implementamos:

Lectura en vivo de Google Sheets.

Diseño de "tarjetas" adaptables para el móvil (sin cortes de texto).

Scroll vertical interno (para mostrar todos los problemas sin alargar la página al infinito).

Filtro dinámico por Responsable.

Descarga de reporte en PDF horizontal estilo tabla (que respeta el filtro que elijas y limpia los "nan").

Links directos al formulario de actualización por cada ticket.

Puedes copiar este bloque entero y reemplazar todo el contenido de tu archivo app.py:

Python
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# ==========================================
# 1. CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(page_title="Tablero QRQC", layout="centered")

# Enlaces definitivos de Google
url_ingresos = "https://docs.google.com/spreadsheets/d/1xw4aqqpf6pWDa9LQSmS3ztLiF82n-ZQ0NqY3QRVTTFg/edit"
url_form_nuevo = "https://docs.google.com/forms/d/e/1FAIpQLSe9AHzNLjUkg3tdfbsUopdc8_YldXLk4YbGXYaeNKyWA198vQ/viewform"
url_base_form_actualizacion = "https://docs.google.com/forms/d/e/1FAIpQLSfppxJI7lPOKbFQZwsDzTBYdv4hWq3QN9ImKCkAvmVCLV0wDw/viewform?entry.1541179458="

st.title("🏭 Tablero de Control QRQC")

# Botones principales
st.link_button("➕ INGRESAR NUEVO TICKET / PROBLEMA", url_form_nuevo, use_container_width=True, type="primary")

st.divider()

if st.button("🔄 Actualizar Datos Ahora", use_container_width=True):
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

# Generar el enlace de actualización basado en el N° de Ticket
if 'N° DE TICKET' in df.columns:
    df['N° DE TICKET'] = df['N° DE TICKET'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df['ACCIÓN'] = url_base_form_actualizacion + df['N° DE TICKET']
else:
    df['ACCIÓN'] = None

columnas_visibles = ['ÁREA', 'PROBLEMA', 'RESPONSABLE', 'ESTADO', 'ACCIÓN']

# Rellenar columnas faltantes por seguridad
for col in columnas_visibles:
    if col not in df.columns:
        df[col] = "N/A"

# ==========================================
# 4. FILTRADO INICIAL Y FUNCIÓN PDF
# ==========================================
es_cerrado = df['ESTADO'].astype(str).str.contains("CIERRE", case=False, na=False)

df_activos = df[~es_cerrado].copy()
df_cerrados = df[es_cerrado].copy()

def generar_pdf(dataframe):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False) 
    pdf.add_page()
    
    # Título del PDF
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Listado de Fallos / Problemas Activos", ln=True, align='C')
    pdf.ln(5)
    
    # Anchos de las columnas en el PDF
    w_ticket = 18
    w_area = 45
    w_resp = 35
    w_estado = 25
    w_prob = 154
    
    def imprimir_encabezados():
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(220, 220, 220) 
        pdf.cell(w_ticket, 8, "Ticket", border=1, fill=True, align='C')
        pdf.cell(w_area, 8, "Área", border=1, fill=True, align='C')
        pdf.cell(w_resp, 8, "Responsable", border=1, fill=True, align='C')
        pdf.cell(w_estado, 8, "Estado", border=1, fill=True, align='C')
        pdf.cell(w_prob, 8, "Descripción del Problema", border=1, fill=True, align='C')
        pdf.ln()

    imprimir_encabezados()
    pdf.set_font("Arial", '', 9)
    
    for index, row in dataframe.iterrows():
        # Limpieza de textos y eliminación de "nan"
        area = str(row['ÁREA']).encode('latin-1', 'replace').decode('latin-1')
        resp = str(row['RESPONSABLE']).encode('latin-1', 'replace').decode('latin-1')
        if resp.lower() == 'nan': resp = '-'
        estado = str(row['ESTADO']).encode('latin-1', 'replace').decode('latin-1')
        problema = str(row['PROBLEMA']).encode('latin-1', 'replace').decode('latin-1')
        ticket = str(row.get('N° DE TICKET', 'S/N')).encode('latin-1', 'replace').decode('latin-1')
        if ticket.lower() == 'nan': ticket = '-'

        # Salto de página automático
        lineas_estimadas = max(len(problema) / 80, len(area) / 25, 1) 
        alto_estimado = lineas_estimadas * 6
        if pdf.get_y() + alto_estimado > 185: 
            pdf.add_page()
            imprimir_encabezados()
            pdf.set_font("Arial", '', 9)

        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # Textos multilínea (Área y Problema)
        pdf.set_xy(x_start + w_ticket, y_start)
        pdf.multi_cell(w_area, 6, area, border=0, align='C')
        y_area = pdf.get_y()
        
        pdf.set_xy(x_start + w_ticket + w_area + w_resp + w_estado, y_start)
        pdf.multi_cell(w_prob, 6, problema, border=0, align='L')
        y_prob = pdf.get_y()
        
        # Calcular altura final de la fila
        max_y = max(y_area, y_prob, y_start + 6)
        row_height = max_y - y_start
        
        # Textos de 1 sola línea
        pdf.set_xy(x_start, y_start)
        pdf.cell(w_ticket, row_height, ticket, border=0, align='C')
        
        pdf.set_xy(x_start + w_ticket + w_area, y_start)
        pdf.cell(w_resp, row_height, resp, border=0, align='C')
        
        pdf.set_xy(x_start + w_ticket + w_area + w_resp, y_start)
        pdf.cell(w_estado, row_height, estado, border=0, align='C')
        
        # Dibujar los bordes de la tabla
        pdf.rect(x_start, y_start, w_ticket, row_height)
        pdf.rect(x_start + w_ticket, y_start, w_area, row_height)
        pdf.rect(x_start + w_ticket + w_area, y_start, w_resp, row_height)
        pdf.rect(x_start + w_ticket + w_area + w_resp, y_start, w_estado, row_height)
        pdf.rect(x_start + w_ticket + w_area + w_resp + w_estado, y_start, w_prob, row_height)
        
        pdf.set_xy(x_start, max_y)

    return bytes(pdf.output(dest='S'), 'latin-1')

# ==========================================
# 5. INTERFAZ VISUAL Y FILTROS DINÁMICOS
# ==========================================

st.subheader("📋 Problemas en Curso / Pendientes")

if not df_activos.empty:
    
    # --- FILTRO POR RESPONSABLE ---
    lista_responsables = df_activos['RESPONSABLE'].astype(str).unique().tolist()
    lista_responsables = sorted([r for r in lista_responsables if r.lower() != 'nan'])
    
    opciones_filtro = ["Todos"] + lista_responsables
    filtro_seleccionado = st.selectbox("🔍 Filtrar por Responsable:", opciones_filtro)
    
    # Aplicar el filtro a la vista
    if filtro_seleccionado != "Todos":
        df_activos = df_activos[df_activos['RESPONSABLE'] == filtro_seleccionado]
        
    st.write("") # Espaciador visual
    
    if df_activos.empty:
        st.info(f"No hay problemas activos asignados a: {filtro_seleccionado}")
    else:
        st.caption(f"Mostrando {len(df_activos)} problemas activos.")
        
        # --- CONTENEDOR CON SCROLL (Altura fija, carga todos los registros) ---
        with st.container(height=600, border=False):
            for index, row in df_activos.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**📍 Área:** {row['ÁREA']}")
                        resp_app = row['RESPONSABLE'] if str(row['RESPONSABLE']).lower() != 'nan' else 'Sin asignar'
                        st.markdown(f"**👤 Resp:** {resp_app}")
                        
                    with col2:
                        st.markdown(f"**📌 Estado:** {row['ESTADO']}")
                    
                    st.error(f"**Descripción del Problema:**\n{row['PROBLEMA']}")
                    
                    if row['ACCIÓN']:
                        st.link_button("🔄 Actualizar Ticket", row['ACCIÓN'], use_container_width=True)

        # --- BOTÓN DE DESCARGA PDF ---
        st.divider()
        pdf_bytes = generar_pdf(df_activos)
        st.download_button(
            label="📄 Descargar Listado en PDF",
            data=pdf_bytes,
            file_name="Reporte_Fallos_Activos.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )
        
else:
    st.success("✅ No hay problemas pendientes en este momento.")

st.divider()

# --- SECCIÓN 2: HISTORIAL DE CERRADOS ---
with st.expander("✅ VER HISTORIAL DE PROBLEMAS CERRADOS"):
    if not df_cerrados.empty:
        st.caption(f"Mostrando {len(df_cerrados)} problemas cerrados.")
        
        # Contenedor con scroll también para el historial
        with st.container(height=500, border=False):
            for index, row in df_cerrados.iterrows():
                with st.container(border=True):
                    resp_app = row['RESPONSABLE'] if str(row['RESPONSABLE']).lower() != 'nan' else '-'
                    st.markdown(f"**📍 Área:** {row['ÁREA']} | **👤 Resp:** {resp_app}")
                    st.success(f"**Problema Resuelto:**\n{row['PROBLEMA']}")
    else:
        st.write("Aún no hay registros marcados como 'CIERRE'.")
