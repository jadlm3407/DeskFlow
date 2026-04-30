# `zones.py` — Zones Router

## Purpose
CRUD endpoints for building zones. The list endpoint returns aggregated occupancy statistics per zone rather than raw data, optimized for the dashboard overview.

---

## Helper: `_zone_summary(zone)`

```python
def _zone_summary(zone: models.Zone) -> schemas.ZoneSummary
```

Computes from the zone's related spaces (loaded via ORM relationship):

| Field | Computation |
|---|---|
| `total_spaces` | `len(spaces)` |
| `available` | count where `status == available` |
| `occupied` | count where `status == occupied` |
| `partial` | count where `status == partial` |
| `occupancy_pct` | `(Σ occupancy / Σ capacity) * 100`, 0 if no capacity |

---

## Endpoints

### `GET /zones/` — List zones
**Auth:** Any authenticated user

Query params:
- `floor: FloorEnum?` — filter by `baja` or `primera`

Returns `List[ZoneSummary]` — aggregated stats, no nested spaces.

---

### `GET /zones/{zone_id}` — Get zone
**Auth:** Any authenticated user

Returns full `ZoneOut` including nested `spaces: List[SpaceOut]`.

---

### `POST /zones/` — Create zone
**Auth:** Admin only

**Request body:** `ZoneCreate` (`code`, `name`, `floor`, `description?`)

Validates `code` uniqueness → `HTTP 400` on duplicate. Returns `ZoneOut`.

---

### `PATCH /zones/{zone_id}` — Update zone
**Auth:** Admin only

**Request body:** `ZoneUpdate` — only `name` and `description` are editable (code and floor are immutable after creation). Returns updated `ZoneOut`.

---

### `DELETE /zones/{zone_id}` — Delete zone
**Auth:** Admin only

Cascade deletes all spaces in the zone (via `cascade="all, delete-orphan"` in the ORM relationship). Returns `{"detail": "Zona <code> eliminada"}`.

---

## Permission Matrix

| Action | Estudiante | Profesor | Admin |
|---|---|---|---|
| List / Get zones | ✓ | ✓ | ✓ |
| Create zone | ✗ | ✗ | ✓ |
| Update zone | ✗ | ✗ | ✓ |
| Delete zone | ✗ | ✗ | ✓ |
