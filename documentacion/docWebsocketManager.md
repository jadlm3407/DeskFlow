# `websocket_manager.py` — WebSocket Connection Manager

## Purpose
Manages all active WebSocket connections. Supports room-based subscriptions so the server can broadcast only to clients watching a specific floor, or to all clients at once.

---

## Data Structures

```python
_active: Dict[str, WebSocket]    # client_id (UUID) -> WebSocket instance
_rooms:  Dict[str, Set[str]]     # room name -> set of client_ids
```

Rooms are strings: `"baja"`, `"primera"`, or `"all"`.

---

## Methods

### `connect(ws, client_id, room="all")`
```python
async def connect(self, ws: WebSocket, client_id: str, room: str = "all")
```
1. Accepts the WebSocket handshake (`ws.accept()`).
2. Registers the client in `_active`.
3. Adds the client to both `room` and `"all"` sets in `_rooms`.

> Every client is always added to `"all"`, regardless of the requested room. This means `broadcast(..., room="all")` reaches every connected client.

---

### `disconnect(client_id)`
```python
def disconnect(self, client_id: str)
```
Removes the client from `_active` and from every room set. Called on `WebSocketDisconnect` or when a send fails.

---

### `broadcast(event, payload, room="all")`
```python
async def broadcast(self, event: str, payload: dict, room: str = "all")
```
Serializes `{"event": event, "payload": payload}` as JSON and sends it to all clients in the specified room.

Dead connections (send fails) are collected and cleaned up via `disconnect()` after iteration.

Called by `spaces.py` after every state-changing operation (check-in, checkout, reserve, confirm, PATCH).

---

### `send_personal(client_id, event, payload)`
```python
async def send_personal(self, client_id: str, event: str, payload: dict)
```
Sends a message to a single client by `client_id`. Used for the `connected` and `pong` responses.

---

### `connected_count` (property)
```python
@property
def connected_count(self) -> int
```
Returns the number of currently active connections. Exposed in `/health` and WS `pong` messages.

---

## Singleton

```python
manager = ConnectionManager()
```
Module-level singleton imported by `main.py` (WebSocket endpoint) and `spaces.py` (broadcast after state changes). All parts of the app share the same instance.

---

## Room Subscription Logic

```
Client connects with ?room=primera
    → added to _rooms["primera"]
    → added to _rooms["all"]

broadcast("space_updated", payload, room="primera")
    → sends only to clients in _rooms["primera"]

broadcast("space_updated", payload, room="all")       ← default
    → sends to every connected client
```

Clients on `"baja"` do NOT receive broadcasts for `"primera"` events (and vice versa) when the caller specifies the room. In practice, `spaces.py` currently always calls `broadcast` without a room argument, so every client receives every event.
