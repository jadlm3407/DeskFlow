# DeskFlow — Sistema de Gestión de Espacios

Sistema web para gestionar la disponibilidad de espacios (aulas, salas, laboratorios) en tiempo real. Incluye autenticación biométrica simulada, mapa interactivo de plantas y actualización en vivo mediante WebSockets.

---

## Estructura del proyecto

```
DeskFlow/
├── main.py                  # Punto de entrada de la aplicación
├── database.py              # Configuración de la base de datos
├── models.py                # Modelos de la base de datos (tablas)
├── schemas.py               # Validación de datos (entrada/salida de la API)
├── auth.py                  # Lógica de autenticación JWT
├── websocket_manager.py     # Gestión de conexiones WebSocket en tiempo real
├── seed.py                  # Script para poblar la BD con datos iniciales
├── requirements.txt         # Dependencias Python
├── .gitignore               # Archivos excluidos del control de versiones
├── sistema-espacios.html    # Frontend (interfaz web)
└── routers/
    ├── auth.py              # Endpoints de login/logout
    ├── users.py             # Endpoints de gestión de usuarios
    ├── zones.py             # Endpoints de zonas
    └── spaces.py            # Endpoints de espacios + check-in/out
```

---

## Archivos — descripción detallada

### `main.py`
Punto de entrada principal. Crea la aplicación FastAPI, registra todos los routers, configura CORS (para que el HTML pueda hablar con la API) y define el endpoint WebSocket `/ws`. También crea las tablas de la BD al arrancar si no existen.

### `database.py`
Configura la conexión a SQLite mediante SQLAlchemy. Define el motor (`engine`), la sesión (`SessionLocal`) y la clase base de modelos (`Base`). Expone la función `get_db()` que los endpoints usan como dependencia para obtener una sesión de BD.

### `models.py`
Define las tablas de la base de datos como clases Python:

| Clase | Tabla | Descripción |
|-------|-------|-------------|
| `User` | `users` | Usuarios del sistema (admin, profesor, estudiante) |
| `Zone` | `zones` | Zonas del edificio (ZA, ZB, ZC...) |
| `Space` | `spaces` | Espacios individuales dentro de cada zona (A1, A2...) |
| `Occupancy` | `occupancies` | Registro histórico de entradas y salidas |

### `schemas.py`
Define los esquemas Pydantic para validar los datos que entran y salen de la API. Hay esquemas de creación (`Create`), actualización (`Update`) y respuesta (`Out`) para cada entidad. También define el esquema del evento WebSocket (`WSEvent`).

### `auth.py`
Contiene toda la lógica de seguridad:
- `hash_password` / `verify_password` — cifrado de contraseñas con bcrypt
- `create_access_token` — genera un JWT con expiración de 8 horas
- `decode_token` — valida y decodifica un JWT
- `get_current_user` — dependencia FastAPI que extrae el usuario del token
- `require_admin` / `require_profesor_or_admin` — dependencias de control de acceso por rol

### `websocket_manager.py`
Gestiona todas las conexiones WebSocket activas. Permite:
- Conectar/desconectar clientes identificados por UUID
- Suscribir clientes a salas (`baja`, `primera`, `all`)
- Hacer broadcast a todos los clientes de una sala cuando cambia el estado de un espacio
- Detectar y limpiar conexiones muertas automáticamente

### `seed.py`
Script de inicialización que se ejecuta **una sola vez** para crear los datos de prueba: 3 usuarios, 6 zonas y 17 espacios con posiciones y estados de ejemplo. Tras ejecutarlo puedes hacer login inmediatamente.

### `requirements.txt`
Lista de dependencias del proyecto:

| Paquete | Para qué sirve |
|---------|---------------|
| `fastapi` | Framework web de la API |
| `uvicorn` | Servidor ASGI para ejecutar FastAPI |
| `sqlalchemy` | ORM para interactuar con la base de datos |
| `python-jose` | Generación y validación de tokens JWT |
| `bcrypt` | Cifrado seguro de contraseñas |
| `pydantic[email]` | Validación de datos y soporte para campos EmailStr |
| `python-multipart` | Soporte para formularios en FastAPI |
| `websockets` | Soporte WebSocket |

> **Nota:** La dependencia original `passlib[bcrypt]` fue eliminada por incompatibilidad con Python 3.13+. El proyecto usa `bcrypt` directamente.

### `.gitignore`
Excluye del repositorio los archivos generados automáticamente: `__pycache__/`, el entorno virtual `.venv/`, la base de datos local `espacios.db` y ficheros de variables de entorno `.env`.

### `sistema-espacios.html`
Frontend completo en un único archivo HTML+CSS+JS. No necesita servidor propio, se abre directamente en el navegador. Incluye:
- Pantalla de login con DNI y contraseña
- Animación de escaneo biométrico tras autenticarse
- Dashboard con mapa interactivo de planta, disponibilidad por zonas y estadísticas globales
- Conexión WebSocket para actualizaciones en tiempo real sin recargar la página

### `routers/auth.py`
Tres endpoints de autenticación:
- `POST /auth/login` — recibe DNI + contraseña, devuelve JWT + datos del usuario
- `POST /auth/logout` — cierra sesión (el cliente descarta el token)
- `GET /auth/me` — devuelve los datos del usuario autenticado

### `routers/users.py`
CRUD completo de usuarios. Los endpoints de listado y creación requieren rol admin. Un usuario puede ver y editar su propio perfil, pero no puede cambiar su propio rol.

### `routers/zones.py`
CRUD de zonas. El listado devuelve un resumen con número de espacios libres/ocupados y porcentaje de ocupación por zona. La creación y eliminación requieren rol admin.

### `routers/spaces.py`
CRUD de espacios más dos endpoints especiales:
- `POST /spaces/{id}/checkin` — registra la entrada de un usuario al espacio, incrementa el contador de ocupación y recalcula el estado (`available` / `partial` / `occupied`). Emite evento WebSocket.
- `POST /spaces/{id}/checkout` — registra la salida, decrementa el contador y recalcula el estado. Emite evento WebSocket.
- `GET /spaces/{id}/history` — historial de entradas y salidas de un espacio (requiere profesor o admin).

---

## Requisitos previos

- **Python 3.10 o superior** (probado en Python 3.14)
- **Chrome o Edge** para abrir el frontend (recomendado)

Comprueba tu versión de Python:
```bash
python --version
```

---

## Puesta en marcha

### 1. Crear entorno virtual

```bash
python -m venv .venv
```

### 2. Activar el entorno virtual

> ⚠️ Este paso hay que repetirlo cada vez que abras una nueva terminal.

```bash
# Windows — CMD
.venv\Scripts\activate.bat

# Windows — PowerShell
.venv\Scripts\Activate.ps1

# Linux / Mac
source .venv/bin/activate
```

Una vez activo verás `(.venv)` al inicio del prompt.

> Si PowerShell da error de permisos, ejecuta primero:
> ```bash
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Inicializar la base de datos con datos de prueba

> Solo se hace una vez.

```bash
python seed.py
```

### 5. Arrancar el servidor

```bash
uvicorn main:app --reload --port 8000
```

Deja esta terminal abierta mientras usas la app. Para detener el servidor pulsa `Ctrl+C`.

### 6. Abrir el frontend

Abre `sistema-espacios.html` directamente en el navegador (doble clic o arrastrar a Chrome/Edge).

---

## Usuarios de prueba

| Rol | DNI | Contraseña |
|-----|-----|-----------|
| Admin | `00000001A` | `admin1234` |
| Estudiante | `12345678X` | `pass1234` |
| Profesor | `87654321B` | `pass1234` |

---

## Documentación interactiva de la API

Con el servidor corriendo, accede a:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Roles y permisos

| Acción | Estudiante | Profesor | Admin |
|--------|-----------|---------|-------|
| Ver zonas y espacios | ✓ | ✓ | ✓ |
| Check-in / Check-out | ✓ | ✓ | ✓ |
| Editar espacios | ✗ | ✓ | ✓ |
| Ver historial | ✗ | ✓ | ✓ |
| Gestionar usuarios | ✗ | ✗ | ✓ |
| Crear/eliminar zonas | ✗ | ✗ | ✓ |

---

## WebSocket

El frontend se conecta a `ws://localhost:8000/ws?room=all`. Cada vez que un espacio cambia de estado (por check-in, checkout o PATCH), el servidor emite:

```json
{
  "event": "space_updated",
  "payload": { "id": 1, "code": "A1", "status": "occupied", "occupancy": 8, ... }
}
```

El frontend actualiza el mapa y las estadísticas automáticamente sin recargar.
