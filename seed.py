"""
Ejecutar una sola vez para poblar la BD:
    python seed.py

Estructura:
  - 2 salas de profesores (SP1, SP2)
  - 10 puestos por sala (2 filas × 5 columnas)
  - SP2 arranca en modo "maintenance" (cerrada)
  - SP2 se desbloquea automáticamente cuando SP1 alcanza el 75 % de ocupación
  - Dispositivos por puesto: PC (200 W) + Monitor (30 W) + Lámpara (10 W)
  - Dispositivos de sala (AC + iluminación) → constantes en energy.py, NO en la BD
"""
from database import SessionLocal, engine, Base
from auth import hash_password
import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── USERS ─────────────────────────────────────────────────────────────────────
users = [
    models.User(
        dni="00000001A", nombre="Admin", apellidos="Sistema",
        email="admin@espacios.local", hashed_pw=hash_password("admin1234"),
        role=models.RoleEnum.admin,
    ),
    models.User(
        dni="87654321B", nombre="María", apellidos="García",
        email="maria@espacios.local", hashed_pw=hash_password("pass1234"),
        role=models.RoleEnum.profesor,
    ),
    models.User(
        dni="11111111C", nombre="Carlos", apellidos="López",
        email="carlos@espacios.local", hashed_pw=hash_password("pass1234"),
        role=models.RoleEnum.profesor,
    ),
]
for u in users:
    if not db.query(models.User).filter_by(dni=u.dni).first():
        db.add(u)
db.commit()
print("✓ Usuarios insertados")

# ── ZONES ─────────────────────────────────────────────────────────────────────
zones_data = [
    models.Zone(
        code="SP1", name="Sala Profesores 1", floor=models.FloorEnum.baja,
        description="Sala activa por defecto — se abre en primer lugar",
    ),
    models.Zone(
        code="SP2", name="Sala Profesores 2", floor=models.FloorEnum.baja,
        description="Se desbloquea cuando SP1 alcanza el 75 % de ocupación",
    ),
]
for z in zones_data:
    if not db.query(models.Zone).filter_by(code=z.code).first():
        db.add(z)
db.commit()
print("✓ Zonas insertadas")

sp1 = db.query(models.Zone).filter_by(code="SP1").first()
sp2 = db.query(models.Zone).filter_by(code="SP2").first()

# ── SPACES (10 puestos × 2 salas) ─────────────────────────────────────────────
# Layout: 2 filas × 5 columnas
# pos_x: [3, 22, 41, 60, 79]  pos_y: [5, 55]  pos_w: 16  pos_h: 38
X_POS = [3, 22, 41, 60, 79]
Y_POS = [5, 55]


def create_spaces(zone_id: int, prefix: str, status: models.StatusEnum) -> list:
    rows = []
    for row_i, y in enumerate(Y_POS):
        for col_i, x in enumerate(X_POS):
            num = row_i * 5 + col_i + 1
            code  = f"{prefix}{num:02d}"
            label = f"Puesto {prefix}-{num:02d}"
            rows.append((code, label, zone_id, 1, status, 0, x, y, 16, 38))
    return rows


sp1_spaces = create_spaces(sp1.id, "T1", models.StatusEnum.available)
sp2_spaces = create_spaces(sp2.id, "T2", models.StatusEnum.maintenance)

for code, label, zone_id, cap, status, occ, x, y, w, h in [*sp1_spaces, *sp2_spaces]:
    if not db.query(models.Space).filter_by(code=code, zone_id=zone_id).first():
        db.add(models.Space(
            code=code, label=label, zone_id=zone_id,
            capacity=cap, status=status, occupancy=occ,
            pos_x=x, pos_y=y, pos_w=w, pos_h=h,
        ))
db.commit()
print("✓ Espacios insertados (SP1: 10 disponibles, SP2: 10 en mantenimiento)")

# ── DEVICES (solo dispositivos de puesto) ─────────────────────────────────────
# Los dispositivos de sala (AC + iluminación) son constantes en energy.py
devices_data = [
    models.Device(
        name="Ordenador sobremesa", watts=200.0,
        location=models.DeviceLocationEnum.desk,
        description="PC de trabajo — 1 por puesto · 200 W",
    ),
    models.Device(
        name='Monitor 24"', watts=30.0,
        location=models.DeviceLocationEnum.desk,
        description="Monitor LED — 1 por puesto · 30 W",
    ),
    models.Device(
        name="Lámpara escritorio", watts=10.0,
        location=models.DeviceLocationEnum.desk,
        description="Iluminación de escritorio — 1 por puesto · 10 W",
    ),
]
for d in devices_data:
    if not db.query(models.Device).filter_by(name=d.name).first():
        db.add(d)
db.commit()

pc      = db.query(models.Device).filter_by(name="Ordenador sobremesa").first()
monitor = db.query(models.Device).filter_by(name='Monitor 24"').first()
lamp    = db.query(models.Device).filter_by(name="Lámpara escritorio").first()
print("✓ Dispositivos insertados")

# ── DEVICE ASSIGNMENTS (todos los puestos: PC + monitor + lámpara) ─────────────
all_spaces = db.query(models.Space).all()
for space in all_spaces:
    for device in [pc, monitor, lamp]:
        exists = db.query(models.DeviceAssignment).filter_by(
            space_id=space.id, device_id=device.id
        ).first()
        if not exists:
            db.add(models.DeviceAssignment(
                space_id=space.id, device_id=device.id, quantity=1,
            ))
db.commit()
print("✓ Asignaciones de dispositivos insertadas (240 W/puesto × 20 puestos)")

# ── NFC CARDS ──────────────────────────────────────────────────────────────────
admin_user = db.query(models.User).filter_by(dni="00000001A").first()
maria_user = db.query(models.User).filter_by(dni="87654321B").first()

nfc_cards = [
    models.NfcCard(uid="04:FC:B2:40:BC:2A:81", user_id=admin_user.id, label="Tarjeta admin"),
    models.NfcCard(uid="04:FD:B2:40:BC:2A:81", user_id=maria_user.id, label="Tarjeta María"),
]
for card in nfc_cards:
    if not db.query(models.NfcCard).filter_by(uid=card.uid).first():
        db.add(card)
db.commit()
print("✓ Tarjetas NFC insertadas")

db.close()
print()
print("═══════════════════════════════════════════════")
print("  ✓ Seed completado")
print("  admin : DNI=00000001A  pass=admin1234")
print("  prof1 : DNI=87654321B  pass=pass1234")
print("  prof2 : DNI=11111111C  pass=pass1234")
print("═══════════════════════════════════════════════")
print()
print("  Consumo por puesto  : 240 W (PC 200W + Monitor 30W + Lámpara 10W)")
print("  Consumo por sala    : 1 820 W (AC 1500W + 8 tubos LED 40W c/u)")
print("  Umbral desbloqueo   : SP1 ≥ 75 % (8 de 10 puestos ocupados)")
