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
    ("A1",  "A1 - SALA REUNIONES",  za.id,  8,  models.StatusEnum.available, 0,   2,  3,  22, 18),
    ("A2",  "A2 - BIBLIOTECA",      za.id,  30, models.StatusEnum.available, 0,  26,  3,  30, 20),
    ("A3",  "A3 - LABORATORIO",     za.id,  20, models.StatusEnum.available, 0,  58,  3,  40, 25),
    ("A4",  "A4 - SALA ESTUDIO",    za.id,  16, models.StatusEnum.available, 0,   2, 24,  35, 20),
    ("A5",  "A5 - DESPACHO 1",      za.id,   4, models.StatusEnum.available, 0,  39, 26,  18, 16),
    ("A6",  "A6 - DESPACHO 2",      za.id,   4, models.StatusEnum.available, 0,  59, 30,  18, 14),
    ("A7",  "A7 - ZONA COMÚN",      za.id,  25, models.StatusEnum.available, 0,   2, 47,  55, 22),
    ("A8",  "A8 - AULA PEQUEÑA",    za.id,  12, models.StatusEnum.available, 0,  59, 47,  20, 20),
    ("A9",  "A9 - SALA PROYECCIÓN", za.id,  40, models.StatusEnum.available, 0,   2, 72,  36, 25),
    ("A10", "A10 - ALMACÉN",        za.id,   0, models.StatusEnum.available, 0,  40, 72,  20, 25),
    ("A11", "A11 - SALA TIC",       za.id,  30, models.StatusEnum.available, 0,  62, 70,  36, 27),
]
spaces_primera = [
    ("P1", "P1 - AULA 101",   z1.id, 40, models.StatusEnum.available, 0,  2,  3, 30, 20),
    ("P2", "P2 - AULA 102",   z1.id, 40, models.StatusEnum.available, 0, 34,  3, 30, 20),
    ("P3", "P3 - AULA 103",   z1.id, 40, models.StatusEnum.available, 0, 66,  3, 32, 20),
    ("P4", "P4 - BIBLIOTECA", z1.id, 50, models.StatusEnum.available, 0,  2, 26, 45, 30),
    ("P5", "P5 - SALA I+D",   z1.id, 15, models.StatusEnum.available, 0, 49, 26, 49, 30),
    ("P6", "P6 - CAFETERÍA",  z1.id, 60, models.StatusEnum.available, 0,  2, 59, 96, 38),
]

for code, label, zone_id, cap, status, occ, x, y, w, h in [*spaces_baja, *spaces_primera]:
    if not db.query(models.Space).filter_by(code=code, zone_id=zone_id).first():
        db.add(models.Space(
            code=code, label=label, zone_id=zone_id,
            capacity=cap, status=status, occupancy=occ,
            pos_x=x, pos_y=y, pos_w=w, pos_h=h,
        ))

db.commit()

# Referencia a los espacios de ZA para asignar dispositivos
za_spaces = db.query(models.Space).filter_by(zone_id=za.id).order_by(models.Space.id).all()
z1_spaces = db.query(models.Space).filter_by(zone_id=z1.id).order_by(models.Space.id).all()

# ── DEVICES ───────────────────────────────────────────────────────────────────
devices_data = [
    models.Device(name="Fluorescente LED",      watts=40.0,   location=models.DeviceLocationEnum.ceiling, description="Iluminación techo"),
    models.Device(name="Proyector",             watts=300.0,  location=models.DeviceLocationEnum.ceiling, description="Proyector de techo"),
    models.Device(name="Aire acondicionado",    watts=1500.0, location=models.DeviceLocationEnum.wall,    description="Split de pared"),
    models.Device(name="Ordenador sobremesa",   watts=200.0,  location=models.DeviceLocationEnum.desk,    description="PC de trabajo"),
    models.Device(name='Monitor 24"',           watts=30.0,   location=models.DeviceLocationEnum.desk,    description="Monitor LED"),
    models.Device(name="Impresora",             watts=500.0,  location=models.DeviceLocationEnum.floor,   description="Impresora láser"),
]
for d in devices_data:
    if not db.query(models.Device).filter_by(name=d.name).first():
        db.add(d)
db.commit()

# Referencia a dispositivos
led       = db.query(models.Device).filter_by(name="Fluorescente LED").first()
proyector = db.query(models.Device).filter_by(name="Proyector").first()
ac        = db.query(models.Device).filter_by(name="Aire acondicionado").first()
pc        = db.query(models.Device).filter_by(name="Ordenador sobremesa").first()
monitor   = db.query(models.Device).filter_by(name='Monitor 24"').first()
impresora = db.query(models.Device).filter_by(name="Impresora").first()

# ── DEVICE ASSIGNMENTS ────────────────────────────────────────────────────────
assignments = [
    # A1 - SALA REUNIONES
    models.DeviceAssignment(space_id=za_spaces[0].id, device_id=led.id,       quantity=4),
    models.DeviceAssignment(space_id=za_spaces[0].id, device_id=proyector.id, quantity=1),
    models.DeviceAssignment(space_id=za_spaces[0].id, device_id=ac.id,        quantity=1),
    # A2 - BIBLIOTECA
    models.DeviceAssignment(space_id=za_spaces[1].id, device_id=led.id,       quantity=8),
    models.DeviceAssignment(space_id=za_spaces[1].id, device_id=ac.id,        quantity=2),
    # A3 - LABORATORIO
    models.DeviceAssignment(space_id=za_spaces[2].id, device_id=led.id,       quantity=6),
    models.DeviceAssignment(space_id=za_spaces[2].id, device_id=pc.id,        quantity=10),
    models.DeviceAssignment(space_id=za_spaces[2].id, device_id=monitor.id,   quantity=10),
    models.DeviceAssignment(space_id=za_spaces[2].id, device_id=ac.id,        quantity=1),
    # A4 - SALA ESTUDIO
    models.DeviceAssignment(space_id=za_spaces[3].id, device_id=led.id,       quantity=6),
    models.DeviceAssignment(space_id=za_spaces[3].id, device_id=ac.id,        quantity=1),
    # A5 - DESPACHO 1
    models.DeviceAssignment(space_id=za_spaces[4].id, device_id=led.id,       quantity=2),
    models.DeviceAssignment(space_id=za_spaces[4].id, device_id=pc.id,        quantity=1),
    models.DeviceAssignment(space_id=za_spaces[4].id, device_id=monitor.id,   quantity=1),
    # A6 - DESPACHO 2
    models.DeviceAssignment(space_id=za_spaces[5].id, device_id=led.id,       quantity=2),
    models.DeviceAssignment(space_id=za_spaces[5].id, device_id=pc.id,        quantity=1),
    models.DeviceAssignment(space_id=za_spaces[5].id, device_id=monitor.id,   quantity=1),
    # A7 - ZONA COMÚN
    models.DeviceAssignment(space_id=za_spaces[6].id, device_id=led.id,       quantity=10),
    models.DeviceAssignment(space_id=za_spaces[6].id, device_id=ac.id,        quantity=2),
    # A9 - SALA PROYECCIÓN
    models.DeviceAssignment(space_id=za_spaces[8].id, device_id=led.id,       quantity=8),
    models.DeviceAssignment(space_id=za_spaces[8].id, device_id=proyector.id, quantity=2),
    models.DeviceAssignment(space_id=za_spaces[8].id, device_id=ac.id,        quantity=2),
    # A11 - SALA TIC
    models.DeviceAssignment(space_id=za_spaces[10].id, device_id=led.id,      quantity=8),
    models.DeviceAssignment(space_id=za_spaces[10].id, device_id=pc.id,       quantity=15),
    models.DeviceAssignment(space_id=za_spaces[10].id, device_id=monitor.id,  quantity=15),
    models.DeviceAssignment(space_id=za_spaces[10].id, device_id=ac.id,       quantity=2),
    # P1 - AULA 101
    models.DeviceAssignment(space_id=z1_spaces[0].id, device_id=led.id,       quantity=8),
    models.DeviceAssignment(space_id=z1_spaces[0].id, device_id=proyector.id, quantity=1),
    models.DeviceAssignment(space_id=z1_spaces[0].id, device_id=ac.id,        quantity=2),
    # P4 - BIBLIOTECA
    models.DeviceAssignment(space_id=z1_spaces[3].id, device_id=led.id,       quantity=12),
    models.DeviceAssignment(space_id=z1_spaces[3].id, device_id=ac.id,        quantity=2),
    # P6 - CAFETERÍA
    models.DeviceAssignment(space_id=z1_spaces[5].id, device_id=led.id,       quantity=15),
    models.DeviceAssignment(space_id=z1_spaces[5].id, device_id=ac.id,        quantity=3),
]

for a in assignments:
    db.add(a)
db.commit()

db.close()
print("✓ Seed completado")
print("  admin:   DNI=00000001A  pass=admin1234")
print("  student: DNI=12345678X  pass=pass1234")
print("  prof:    DNI=87654321B  pass=pass1234")