"""Panel de Control (Frontend) - Operativa.ia

Interfaz interactiva construida con Streamlit para la gestión de citas y métricas.
"""

import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Operativa.ia - Dashboard",
    page_icon="🚀",
    layout="wide",
)

# Encabezado principal
st.title("🚀 Operativa.ia - Panel de Control")
st.caption("Sistema de Automatización Operativa y Atención 24/7 para Clínicas")

# Métricas en tiempo real
col1, col2, col3, col4 = st.columns(4)
col1.metric(label="Llamadas Atendidas 24/7", value="42", delta="+12 esta semana")
col2.metric(label="Citas Agendadas", value="18", delta="+5 hoy")
col3.metric(label="Tasa de Conversión", value="42.8%", delta="+3.2%")
col4.metric(label="Ingresos Salvados", value="$2,150 USD", delta="+$450 hoy")

st.divider()

# Layout de dos columnas: Tabla de Citas y Simulación de Chat
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📅 Citas Agendadas Recientemente")
    citas_demo = [
        {
            "Paciente": "María García",
            "Tratamiento": "Limpieza Dental",
            "Fecha": "Mañana 10:00 AM",
            "Estado": "Confirmada",
        },
        {
            "Paciente": "Carlos López",
            "Tratamiento": "Ortodoncia",
            "Fecha": "Mañana 11:30 AM",
            "Estado": "Confirmada",
        },
        {
            "Paciente": "Ana Martínez",
            "Tratamiento": "Blanqueamiento",
            "Fecha": "Mañana 03:00 PM",
            "Estado": "Pendiente de Anticipo",
        },
    ]
    st.dataframe(citas_demo, use_container_width=True)

with col_right:
    st.subheader("💬 Simulación de Chat con Sofía (IA)")
    user_input = st.text_input(
        "Escribe una consulta como paciente:",
        placeholder="Hola, quisiera agendar una limpieza dental...",
    )

    if st.button("Enviar Mensaje"):
        if user_input:
            st.write(f"👤 **Paciente:** {user_input}")
            st.info(
                "🤖 **Sofía (Operativa.ia):** ¡Hola! Con gusto te ayuda a agendar "
                "tu limpieza. Tengo disponibilidad mañana a las 10:00 AM y a las 3:00 PM. "
                "¿Cuál horario prefieres?"
            )
        else:
            st.warning("Por favor escribe un mensaje antes de enviar.")
