# `seed.py` — Database Seed Script

## Purpose
One-time initialization script that populates the database with sample data: users, zones, and spaces. Run once after the DB is created.

```bash
python seed.py
```

---

## What it creates

### Users (3)

| Role | DNI | Password | Email |
|---|---|---|---|
| admin | `00000001A` | `admin1234` | admin@espacios.local |
| estudiante | `12345678X` | `pass1234` | alberto@espacios.local |
| profesor | `87654321B` | `pass1234` | maria@espacios.local |

Passwords are hashed with bcrypt via `hash_password()` before insertion.

---

### Zones (6)

| Code | Name | Floor |
|---|---|---|
| ZA | Zona A | baja |
| ZB | Zona B | baja |
| ZC | Zona C | baja |
| Z1 | Bloque 1 | primera |
| Z2 | Bloque 2 | primera |
| Z3 | Bloque 3 | primera |

---

### Spaces (17)

**Planta Baja — Zona A (11 spaces):**

| Code | Label | Capacity | Initial Status | Occupancy |
|---|---|---|---|---|
| A1 | SALA REUNIONES | 8 | occupied | 8 |
| A2 | BIBLIOTECA | 30 | available | 4 |
| A3 | LABORATORIO | 20 | partial | 11 |
| A4 | SALA ESTUDIO | 16 | available | 2 |
| A5 | DESPACHO 1 | 4 | occupied | 4 |
| A6 | DESPACHO 2 | 4 | available | 0 |
| A7 | ZONA COMÚN | 25 | partial | 13 |
| A8 | AULA PEQUEÑA | 12 | available | 0 |
| A9 | SALA PROYECCIÓN | 40 | occupied | 38 |
| A10 | ALMACÉN | 0 | available | 0 |
| A11 | SALA TIC | 30 | partial | 16 |

**Primera Planta — Bloque 1 (6 spaces):**

| Code | Label | Capacity | Initial Status | Occupancy |
|---|---|---|---|---|
| P1 | AULA 101 | 40 | occupied | 38 |
| P2 | AULA 102 | 40 | occupied | 35 |
| P3 | AULA 103 | 40 | partial | 20 |
| P4 | BIBLIOTECA | 50 | available | 8 |
| P5 | SALA I+D | 15 | partial | 7 |
| P6 | CAFETERÍA | 60 | available | 12 |

Each space includes `pos_x, pos_y, pos_w, pos_h` (percentages) for rendering on the floor plan map.

---

## Idempotency

Before inserting each record, the script checks for an existing entry:
```python
if not db.query(models.User).filter_by(dni=u.dni).first():
    db.add(u)
```
Re-running the script on an already-seeded database is safe — no duplicates are created.

---

## Sequence

1. `Base.metadata.create_all(bind=engine)` — creates tables if they don't exist.
2. Insert users → `db.commit()`.
3. Insert zones → `db.commit()`.
4. Query zone IDs for FK references.
5. Insert spaces → `db.commit()`.
6. `db.close()`.
