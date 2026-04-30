import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, users, zones, spaces
from database import engine, Base
from websocket_manager import manager
from routers import users, zones, spaces


# ── LIFESPAN (crea tablas al arrancar) ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Sistema de Gestión de Espacios",
    version="1.0.0",
    description="Backend para el sistema de identificación y disponibilidad de espacios",
    lifespan=lifespan,
)

# ── CORS (ajusta origins en producción) ───────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # en prod: ["https://tu-frontend.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTERS ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(zones.router)
app.include_router(spaces.router)


# ── WEBSOCKET ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    room: str = Query(default="all"),   # ?room=baja | ?room=primera | ?room=all
):
    """
    Conexión en tiempo real.  El cliente puede suscribirse a una planta concreta:
        ws://localhost:8000/ws?room=baja
        ws://localhost:8000/ws?room=primera
        ws://localhost:8000/ws          → recibe todos los eventos

    Mensajes recibidos del servidor:
        { "event": "space_updated", "payload": { ...SpaceOut } }
        { "event": "ping",          "payload": { "clients": N } }
    """
    client_id = str(uuid.uuid4())
    await manager.connect(ws, client_id, room)
    await manager.send_personal(client_id, "connected", {
        "client_id": client_id,
        "room": room,
        "clients_online": manager.connected_count,
    })

    try:
        while True:
            data = await ws.receive_text()   # keep-alive / ping del cliente
            if data == "ping":
                await manager.send_personal(client_id, "pong", {
                    "clients": manager.connected_count
                })
    except WebSocketDisconnect:
        manager.disconnect(client_id)


# ── HEALTH ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "ws_clients": manager.connected_count,
    }
