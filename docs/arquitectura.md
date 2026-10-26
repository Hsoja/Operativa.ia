```
# 🏗️ Arquitectura del Sistema - Operativa.ia

Este documento describe el flujo de datos y los componentes tecnológicos que conforman la plataforma **Operativa.ia**.

---

## 🔄 Flujo de Datos

```mermaid
graph TD
    A[Cliente / Paciente] --&gt;|Llamada de voz o WhatsApp| B[Agente de IA - Vapi / Groq]
    B --&gt;|Procesa mensaje y extrae intención| C[Backend Python - FastAPI]
    C --&gt;|Verifica disponibilidad| D[Google Calendar API]
    C --&gt;|Guarda registro y log| E[Supabase - PostgreSQL]
    D --&gt;|Confirma cita| B
    B --&gt;|Responde con confirmación| A

```
