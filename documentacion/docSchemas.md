# `schemas.py` — Pydantic Schemas (API Validation)

## Purpose
Defines request/response data shapes using Pydantic v2. Separates API contracts from ORM models. Uses `model_config = {"from_attributes": True}` to allow building schemas directly from SQLAlchemy model instances.

---

## Auth Schemas

| Schema | Direction | Fields |
|---|---|---|
| `LoginRequest` | → Request | `dni`, `password` |
| `Token` | ← Response | `access_token`, `token_type="bearer"`, `user: UserOut` |
| `TokenData` | Internal | `user_id: Optional[int]` — payload of decoded JWT |

---

## User Schemas

| Schema | Direction | Fields |
|---|---|---|
| `UserCreate` | → Request | `dni`, `nombre`, `apellidos`, `email`, `password`, `role=estudiante` |
| `UserUpdate` | → Request (PATCH) | All fields optional: `nombre`, `apellidos`, `email`, `role`, `is_active` |
| `UserOut` | ← Response | All fields except `hashed_pw`; includes `id`, `created_at` |

> `UserOut` uses `EmailStr` for input validation but exposes `email: str` in output.

---

## Zone Schemas

| Schema | Direction | Fields |
|---|---|---|
| `ZoneCreate` | → Request | `code`, `name`, `floor`, `description?` |
| `ZoneUpdate` | → Request (PATCH) | `name?`, `description?` |
| `ZoneOut` | ← Response | Full zone with nested `spaces: list[SpaceOut]` |
| `ZoneSummary` | ← Response (list) | Aggregated stats: `total_spaces`, `available`, `occupied`, `partial`, `occupancy_pct` |

`ZoneSummary` is returned by `GET /zones/` — avoids loading full space data for the dashboard overview.

---

## Space Schemas

| Schema | Direction | Fields |
|---|---|---|
| `SpaceCreate` | → Request | `code`, `label`, `zone_id`, `capacity`, `pos_x/y/w/h` |
| `SpaceUpdate` | → Request (PATCH) | All optional: `label`, `capacity`, `status`, `occupancy`, `pos_*` |
| `SpaceOut` | ← Response | All space fields including `reservation_user_id`, `reservation_expires_at` |
| `ReservationOut` | ← Response | `space_id`, `user_id`, `expires_at`, `message` |

---

## Occupancy Schemas

| Schema | Direction | Fields |
|---|---|---|
| `OccupancyOut` | ← Response | `id`, `user_id`, `space_id`, `entered_at`, `exited_at?`, `active` |

Returned by `checkin`, `checkout`, and `confirm` endpoints.

---

## WebSocket Schema

```python
class WSEvent(BaseModel):
    event: str    # "space_updated" | "reservation_expired" | "connected" | "pong"
    payload: dict
```
Used internally to validate the structure of WS broadcast messages.

---

## Forward References

```python
Token.model_rebuild()   # Token references UserOut (defined after Token)
ZoneOut.model_rebuild() # ZoneOut references SpaceOut (defined after ZoneOut)
```
Required by Pydantic v2 when a schema references another defined later in the file.
