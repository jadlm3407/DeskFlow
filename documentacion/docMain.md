# `main.py` — Application Entry Point

## Purpose
Creates the FastAPI application, registers all routers, configures CORS, defines the WebSocket endpoint, and creates DB tables on startup via lifespan.

---

## Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
```
Runs `CREATE TABLE IF NOT EXISTS` for all models before the app accepts traffic. No teardown logic on shutdown.

---

## CORS Middleware

```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```
Fully open for development. In production, restrict `allow_origins` to the actual frontend domain.

---

## Registered Routers

| Router | Prefix | File |
|---|---|---|
| `auth` | `/auth` | `authRouters.py` |
| `users` | `/users` | `users.py` |
| `zones` | `/zones` | `zones.py` |
| `spaces` | `/spaces` | `spaces.py` |

> **Bug:** `from routers import auth, users, zones, spaces` is duplicated. The second import shadows the first but has no practical effect.

---

## WebSocket Endpoint `/ws`

```
ws://localhost:8000/ws?room=baja
ws://localhost:8000/ws?room=primera
ws://localhost:8000/ws          → subscribes to all events
```

### Flow
1. Generate a UUID as `client_id`.
2. `manager.connect(ws, client_id, room)` — accepts the WS and registers it.
3. Send a `connected` event back to the client with its ID, room, and online count.
4. Enter a receive loop:
   - If the client sends `"ping"` → respond with `"pong"` + current connected count.
   - `WebSocketDisconnect` → `manager.disconnect(client_id)`.

### Emitted Events (server → client)

```json
{ "event": "space_updated",  "payload": { ...SpaceOut } }
{ "event": "ping",           "payload": { "clients": N } }
{ "event": "connected",      "payload": { "client_id": "...", "room": "...", "clients_online": N } }
{ "event": "pong",           "payload": { "clients": N } }
```

---

## Health Endpoint

```
GET /health
```
Returns `{ "status": "ok", "ws_clients": N }`. Useful for load balancer probes.

---

## Interactive Docs (dev only)

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
