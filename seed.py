"""
Ejecutar una sola vez para poblar la BD:
    python seed.py
"""
from database import SessionLocal, engine, Base
from auth import hash_password
import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── USERS ─────────────────────────────────────────────────────────────────────
users = [
    models.User(dni="00000001A", nombre="Admin",    apellidos="Sistema",   email="admin@espacios.local",    hashed_pw=hash_password("admin1234"),   role=models.RoleEnum.admin),
    models.User(dni="12345678X", nombre="Alberto",  apellidos="Fernández", email="alberto@espacios.local",  hashed_pw=hash_password("pass1234"),    role=models.RoleEnum.estudiante),
    models.User(dni="87654321B", nombre="María",    apellidos="García",    email="maria@espacios.local",    hashed_pw=hash_password("pass1234"),    role=models.RoleEnum.profesor),
]
for u in users:
    if not db.query(models.User).filter_by(dni=u.dni).first():
        db.add(u)

# ── ZONES ─────────────────────────────────────────────────────────────────────
zones_data = [
    models.Zone(code="ZA", name="Zona A", floor=models.FloorEnum.baja,    description="Planta baja - ala este"),
    models.Zone(code="ZB", name="Zona B", floor=models.FloorEnum.baja,    description="Planta baja - ala central"),
    models.Zone(code="ZC", name="Zona C", floor=models.FloorEnum.baja,    description="Planta baja - ala oeste"),
    models.Zone(code="Z1", name="Bloque 1", floor=models.FloorEnum.primera, description="Primera planta - ala norte"),
    models.Zone(code="Z2", name="Bloque 2", floor=models.FloorEnum.primera, description="Primera planta - ala sur"),
    models.Zone(code="Z3", name="Bloque 3", floor=models.FloorEnum.primera, description="Primera planta - ala este"),
]
for z in zones_data:
    if not db.query(models.Zone).filter_by(code=z.code).first():
        db.add(z)

db.commit()

# ── SPACES ────────────────────────────────────────────────────────────────────
za = db.query(models.Zone).filter_by(code="ZA").first()
z1 = db.query(models.Zone).filter_by(code="Z1").first()

spaces_baja = [
    ("A1",  "A1 - SALA REUNIONES",  za.id,  8,  models.StatusEnum.occupied,   8,   2,  3,  22, 18),
    ("A2",  "A2 - BIBLIOTECA",      za.id,  30, models.StatusEnum.available,   4,  26,  3,  30, 20),
    ("A3",  "A3 - LABORATORIO",     za.id,  20, models.StatusEnum.partial,    11,  58,  3,  40, 25),
    ("A4",  "A4 - SALA ESTUDIO",    za.id,  16, models.StatusEnum.available,   2,   2, 24,  35, 20),
    ("A5",  "A5 - DESPACHO 1",      za.id,   4, models.StatusEnum.occupied,    4,  39, 26,  18, 16),
    ("A6",  "A6 - DESPACHO 2",      za.id,   4, models.StatusEnum.available,   0,  59, 30,  18, 14),
    ("A7",  "A7 - ZONA COMÚN",      za.id,  25, models.StatusEnum.partial,    13,   2, 47,  55, 22),
    ("A8",  "A8 - AULA PEQUEÑA",    za.id,  12, models.StatusEnum.available,   0,  59, 47,  20, 20),
    ("A9",  "A9 - SALA PROYECCIÓN", za.id,  40, models.StatusEnum.occupied,   38,   2, 72,  36, 25),
    ("A10", "A10 - ALMACÉN",        za.id,   0, models.StatusEnum.available,   0,  40, 72,  20, 25),
    ("A11", "A11 - SALA TIC",       za.id,  30, models.StatusEnum.partial,    16,  62, 70,  36, 27),
]
spaces_primera = [
    ("P1", "P1 - AULA 101",   z1.id, 40, models.StatusEnum.occupied,  38,  2,  3, 30, 20),
    ("P2", "P2 - AULA 102",   z1.id, 40, models.StatusEnum.occupied,  35, 34,  3, 30, 20),
    ("P3", "P3 - AULA 103",   z1.id, 40, models.StatusEnum.partial,   20, 66,  3, 32, 20),
    ("P4", "P4 - BIBLIOTECA", z1.id, 50, models.StatusEnum.available,  8,  2, 26, 45, 30),
    ("P5", "P5 - SALA I+D",   z1.id, 15, models.StatusEnum.partial,    7, 49, 26, 49, 30),
    ("P6", "P6 - CAFETERÍA",  z1.id, 60, models.StatusEnum.available, 12,  2, 59, 96, 38),
]

for code, label, zone_id, cap, status, occ, x, y, w, h in [*spaces_baja, *spaces_primera]:
    if not db.query(models.Space).filter_by(code=code, zone_id=zone_id).first():
        db.add(models.Space(
            code=code, label=label, zone_id=zone_id,
            capacity=cap, status=status, occupancy=occ,
            pos_x=x, pos_y=y, pos_w=w, pos_h=h,
        ))

db.commit()
db.close()
print("✓ Seed completado")
print("  admin:   DNI=00000001A  pass=admin1234")
print("  student: DNI=12345678X  pass=pass1234")
print("  prof:    DNI=87654321B  pass=pass1234")
