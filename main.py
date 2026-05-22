import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, users, zones, spaces, energy, nfc
from database import engine, Base
from websocket_manager import manager


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

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTERS ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(zones.router)
app.include_router(spaces.router)
app.include_router(energy.router)
app.include_router(nfc.router)


# ── WEBSOCKET ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    room: str = Query(default="all"),
):
    client_id = str(uuid.uuid4())
    await manager.connect(ws, client_id, room)
    await manager.send_personal(client_id, "connected", {
        "client_id": client_id,
        "room": room,
        "clients_online": manager.connected_count,
    })

    try:
        while True:
            data = await ws.receive_text()
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