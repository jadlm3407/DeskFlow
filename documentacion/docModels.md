# `models.py` — ORM Models (Database Tables)

## Purpose
Defines the relational schema using SQLAlchemy ORM. Each class maps to a DB table. Also declares the Enums used across the application.

---

## Enums

```python
class RoleEnum(str, enum.Enum):
    admin      # Full access
    profesor   # Can edit spaces, view history
    estudiante # Basic access: view + check-in/out
```

```python
class StatusEnum(str, enum.Enum):
    available    # 0 < occupancy / capacity < threshold (or capacity == 0)
    reserved     # Temporarily held; auto-expires after 5 min
    occupied     # occupancy >= capacity
    partial      # 0 < occupancy < capacity
    maintenance  # Blocked; no check-ins allowed
```

```python
class FloorEnum(str, enum.Enum):
    baja      # Ground floor
    primera   # First floor
```

---

## Tables

### `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK | Auto-increment |
| `dni` | String(20) | UNIQUE, NOT NULL | National ID used as login |
| `nombre` | String(100) | NOT NULL | First name |
| `apellidos` | String(150) | NOT NULL | Last name |
| `email` | String(150) | UNIQUE, NOT NULL | |
| `hashed_pw` | String(255) | NOT NULL | bcrypt hash |
| `role` | Enum(RoleEnum) | default=estudiante | |
| `is_active` | Boolean | default=True | Soft disable without deletion |
| `created_at` | DateTime(tz) | server_default=now() | |

**Relationships:** `occupancies` → one-to-many with `Occupancy`.

---

### `zones`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK | |
| `code` | String(10) | UNIQUE, NOT NULL | Short identifier: ZA, ZB, Z1… |
| `name` | String(100) | NOT NULL | Human-readable name |
| `floor` | Enum(FloorEnum) | NOT NULL | |
| `description` | String(255) | nullable | |

**Relationships:** `spaces` → one-to-many with `Space` (`cascade="all, delete-orphan"` — deleting a zone deletes its spaces).

---

### `spaces`

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | |
| `code` | String(10) | Room code: A1, P3… |
| `label` | String(150) | Display name: "A1 - SALA REUNIONES" |
| `zone_id` | FK → zones.id | |
| `capacity` | Integer | Max persons; 0 = unlimited |
| `status` | Enum(StatusEnum) | Current computed state |
| `occupancy` | Integer | Current person count |
| `pos_x/y` | Float | Position on floor map (%) |
| `pos_w/h` | Float | Size on floor map (%) |
| `updated_at` | DateTime(tz) | Auto-updated on any change |
| `reservation_user_id` | FK → users.id (nullable) | Who holds the active reservation |
| `reservation_expires_at` | DateTime(tz) (nullable) | When the reservation auto-cancels |

**Relationships:**
- `zone` → many-to-one with `Zone`
- `occupancies` → one-to-many with `Occupancy`

---

### `occupancies`

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → users.id | |
| `space_id` | FK → spaces.id | |
| `entered_at` | DateTime(tz) | server_default=now() |
| `exited_at` | DateTime(tz) | NULL while active |
| `active` | Boolean | True = currently inside |

Acts as an **audit log** for all entries and exits. An active row (`active=True, exited_at=NULL`) means the user is currently inside the space.

---

## Status Transition Diagram

```
available ──reserve──> reserved ──confirm/checkin──> partial/occupied
    ^                     │                               │
    │              [TTL expires]                     checkout
    │                     │                               │
    └─────────────────────┘───────────────────────────────┘
```
