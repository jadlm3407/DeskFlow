# DeskFlow — Sistema de Gestión de Espacios de Profesores

Sistema web para gestionar la disponibilidad de despachos de profesores en tiempo real. Incluye identificación por tarjeta NFC, plano interactivo de sala, desbloqueo automático de sala secundaria y estadísticas de consumo energético con informe por email.

---

## Estructura del proyecto

```
DeskFlow/
├── main.py                  # Punto de entrada de la aplicación
├── database.py              # Configuración de la base de datos (SQLite)
├── models.py                # Modelos ORM (tablas de la BD)
├── schemas.py               # Esquemas Pydantic (validación de datos)
├── auth.py                  # Autenticación JWT y control de acceso por rol
├── websocket_manager.py     # Gestión de conexiones WebSocket en tiempo real
├── email_report.py          # Generación y envío de informes energéticos por email
├── seed.py                  # Script de inicialización de la base de datos
├── requirements.txt         # Dependencias Python
├── .gitignore
├── sistema-espacios.html    # Frontend completo (HTML + CSS + JS)
└── routers/
    ├── auth.py              # Endpoints de login/logout
    ├── users.py             # CRUD de usuarios
    ├── zones.py             # CRUD de zonas
    ├── spaces.py            # CRUD de espacios + checkin/checkout + desbloqueo SP2
    ├── energy.py            # Estadísticas de consumo energético + envío de informe
    └── nfc.py               # Identificación por tarjeta NFC (ESP32 + RC522)
```

---

## Funcionalidades principales

- **Identificación NFC** — el ESP32 con lector RC522 detecta la tarjeta y autentica al usuario automáticamente en el kiosko
- **Plano interactivo** — vista de despachos individuales con mobiliario, estado en tiempo real y checkin/checkout
- **Dos salas de profesores** — SP1 siempre abierta; SP2 se desbloquea automáticamente cuando SP1 alcanza el 75% de ocupación
- **WebSockets** — actualizaciones en tiempo real sin recargar la página
- **Panel de administración** — crear usuarios, registrar tarjetas NFC, ver historial de ocupación y enviar informes energéticos
- **Informe energético por email** — calcula kWh y coste por puesto y sala, envía HTML formateado al email indicado

---

## Requisitos previos

- Python 3.10 o superior
- Chrome, Edge o Safari para el frontend
- ESP32 con lector RFID-RC522 (para identificación NFC)

---

## Puesta en marcha

### 1. Crear y activar entorno virtual

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux / Mac
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Inicializar la base de datos

> Solo la primera vez.

```bash
python seed.py
```

### 4. Arrancar el servidor

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Servir el frontend (para acceso desde otros dispositivos)

En una segunda terminal:

```bash
python -m http.server 8080
```

Accede desde cualquier dispositivo en la misma red:
```
http://<IP-del-servidor>:8080/sistema-espacios.html
```

---

## Usuarios iniciales

| Rol   | DNI         | Contraseña  |
|-------|-------------|-------------|
| Admin | `00000001A` | `admin1234` |

> El administrador puede crear nuevos usuarios profesor desde el panel de administración del frontend.

---

## Roles y permisos

| Acción                        | Profesor | Admin |
|-------------------------------|----------|-------|
| Ver salas y despachos         | ✓        | ✓     |
| Checkin / Checkout            | ✓        | ✓     |
| Ver historial de ocupación    | ✓        | ✓     |
| Editar espacios               | ✓        | ✓     |
| Crear / eliminar usuarios     | ✗        | ✓     |
| Registrar tarjetas NFC        | ✗        | ✓     |
| Enviar informe energético     | ✗        | ✓     |
| Crear / eliminar zonas        | ✗        | ✓     |

---

## Modelo energético

| Concepto              | Potencia                              |
|-----------------------|---------------------------------------|
| PC sobremesa          | 200 W                                 |
| Monitor 24"           | 30 W                                  |
| Lámpara escritorio    | 10 W                                  |
| **Total por puesto**  | **240 W — 0,24 kWh/h**               |
| Aire acondicionado    | 1 500 W                               |
| Iluminación sala      | 8 × 40 W = 320 W                      |
| **Total por sala**    | **1 820 W — 1,82 kWh/h**             |
| Precio kWh            | 0,18 €/kWh (configurable en energy.py)|

---

## Documentación interactiva de la API

Con el servidor corriendo:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## WebSocket

El frontend se conecta a `ws://<host>:8000/ws?room=all`. Cada cambio de estado de un despacho emite:

```json
{
  "event": "space_updated",
  "payload": { "id": 1, "code": "T101", "status": "occupied", "occupancy": 1 }
}
```

El frontend actualiza el plano y las estadísticas en tiempo real sin recargar.