# `spaces.py` — Spaces Router

## Purpose
CRUD + check-in/checkout + reservation endpoints for individual spaces. Every state-changing operation broadcasts a WebSocket event to all connected clients.

---

## Constants & State

```python
RESERVATION_TTL_SECONDS = 300   # 5-minute reservation window
_expiry_tasks: dict[int, asyncio.Task]  # space_id -> running expiry coroutine
```

---

## Helper: `_compute_status(space)`

```python
def _compute_status(space: models.Space) -> models.StatusEnum
```

| Condition | Status |
|---|---|
| `capacity == 0` | `available` |
| `occupancy == 0` | `available` |
| `occupancy >= capacity` | `occupied` |
| `0 < occupancy < capacity` | `partial` |

Called after every occupancy change to recalculate status automatically.

---

## Helper: `_broadcast_space(space)`

Serializes the space to `SpaceOut` and calls `manager.broadcast("space_updated", payload)`. Async — must be awaited.

---

## Reservation Expiry

### `_cancel_expiry(space_id)`
Cancels and removes the running `asyncio.Task` for a space's reservation timer, if any.

### `_expire_reservation(space_id)` *(coroutine)*
Background task launched by `reserve`. After sleeping `RESERVATION_TTL_SECONDS`:
1. Opens a new DB session (the original request session is long gone).
2. If the space is still `reserved` → resets to `available`, clears reservation fields.
3. Broadcasts `space_updated` and `reservation_expired` via WebSocket.

---

## Endpoints

### `GET /spaces/` — List spaces
**Auth:** Any authenticated user

Query params: `zone_id?`, `status?`

Returns `List[SpaceOut]`.

---

### `GET /spaces/{space_id}` — Get space
**Auth:** Any authenticated user

Returns `SpaceOut` or `HTTP 404`.

---

### `POST /spaces/` — Create space
**Auth:** Admin only

Validates that the referenced `zone_id` exists. Returns `SpaceOut`.

---

### `PATCH /spaces/{space_id}` — Update space
**Auth:** Profesor or Admin

If `occupancy` is included in the body, recomputes `status` via `_compute_status`. Broadcasts `space_updated`.

---

### `DELETE /spaces/{space_id}` — Delete space
**Auth:** Admin only

Cancels any running expiry task for this space before deletion.

---

### `POST /spaces/{space_id}/reserve` — Reserve space
**Auth:** Any authenticated user

**Validations:**
- Space exists.
- Status is not `maintenance`.
- If already `reserved`, the existing reservation has not expired yet → `HTTP 409`.
- `occupancy < capacity` (if capacity > 0).

**Effect:**
1. Set `status = reserved`, `reservation_user_id = current.id`, `reservation_expires_at = now + 5 min`.
2. Launch `_expire_reservation` as an `asyncio.Task`.
3. Broadcast `space_updated`.

Returns `ReservationOut`.

---

### `POST /spaces/{space_id}/confirm` — Confirm reservation
**Auth:** Reservation owner only

Converts an active reservation into a real check-in:
1. Validates: space is `reserved`, caller is the reservation owner, reservation has not expired.
2. Cancels the expiry task.
3. Creates an `Occupancy` record.
4. Increments `occupancy`, recomputes `status`, clears reservation fields.
5. Broadcasts `space_updated`.

Returns `OccupancyOut`.

---

### `POST /spaces/{space_id}/checkin` — Check in
**Auth:** Any authenticated user

**Validations:**
- Space is not in `maintenance`.
- If `reserved`, the caller must be the reservation owner.
- `occupancy < capacity`.
- No existing active `Occupancy` for this user+space → `HTTP 409`.

**Effect:**
1. If caller has a reservation on this space, cancel the expiry task and clear reservation fields.
2. Create `Occupancy` record, increment `occupancy`, recompute `status`.
3. Broadcast `space_updated`.

Returns `OccupancyOut`.

---

### `POST /spaces/{space_id}/checkout` — Check out
**Auth:** Any authenticated user

Finds the active `Occupancy` for `current.id + space_id`. If none → `HTTP 404`.

Sets `exited_at = now`, `active = False`, decrements `occupancy` (floor 0), recomputes `status`. Broadcasts `space_updated`.

Returns `OccupancyOut`.

---

### `GET /spaces/{space_id}/history` — Occupancy history
**Auth:** Profesor or Admin

Query param: `limit: int = 50` (max 500)

Returns `List[OccupancyOut]` ordered by `entered_at DESC`.

---

## Permission Matrix

| Action | Estudiante | Profesor | Admin |
|---|---|---|---|
| List / Get spaces | ✓ | ✓ | ✓ |
| Create space | ✗ | ✗ | ✓ |
| Update space (PATCH) | ✗ | ✓ | ✓ |
| Delete space | ✗ | ✗ | ✓ |
| Reserve / Confirm / Check-in / Check-out | ✓ | ✓ | ✓ |
| View history | ✗ | ✓ | ✓ |

---

## State Transitions

```
available ──/reserve──────────────────────> reserved
    ^                                          │
    │                                   /confirm or /checkin
    │                                          │
    │                                          ▼
    │                               partial / occupied
    │                                          │
    └────────────────── /checkout ─────────────┘

reserved ──[TTL expires]──> available
```
