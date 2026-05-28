"""
Router de energía — estadísticas de consumo por puesto, sala y período.

Modelo de consumo
─────────────────
  Puestos de trabajo  (por sesión activa):
    • PC sobremesa  200 W
    • Monitor 24"    30 W
    • Lámpara escr.  10 W
    ─────────────────────
    Total / puesto   240 W  →  0,24 kWh/h

  Dispositivos de sala  (por cada hora que la sala estuvo abierta):
    • Aire acondicionado  1 500 W
    • 8 × Tubo LED 40 W    320 W
    ─────────────────────────────
    Total / sala       1 820 W  →  1,82 kWh/h

  La sala se considera "abierta" desde la primera entrada hasta la última salida
  del día/período.  Si hay sesiones activas en el momento del informe, se usa
  la hora actual como cierre provisional.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
import models
from database import get_db
from auth import get_current_user, require_admin, require_profesor_or_admin
from pydantic import BaseModel

router = APIRouter(prefix="/energy", tags=["energy"])

# ── Constantes ────────────────────────────────────────────────────────────────

PRICE_PER_KWH = 0.18   # €/kWh (tarifa estimada)

# Consumo de dispositivos de sala (independiente del número de puestos ocupados)
SALA_WATTS: dict[str, int] = {
    "SP1": 1_500 + 8 * 40,   # AC (1500 W) + 8 tubos LED (40 W c/u) = 1820 W
    "SP2": 1_500 + 8 * 40,
}
SALA_DEVICE_DESC = "AC 1 500 W + 8 tubos LED 40 W = 1 820 W"

# Consumo por puesto de trabajo
WORKSTATION_WATTS = 200 + 30 + 10   # PC + Monitor + Lámpara = 240 W
WORKSTATION_DESC  = "PC 200 W + Monitor 30 W + Lámpara 10 W = 240 W"


# ── Schemas locales ────────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    name: str
    watts: float
    location: models.DeviceLocationEnum
    description: Optional[str] = None

class DeviceOut(BaseModel):
    id: int; name: str; watts: float
    location: models.DeviceLocationEnum
    description: Optional[str]
    class Config: from_attributes = True

class AssignmentCreate(BaseModel):
    device_id: int
    quantity: int = 1

class AssignmentOut(BaseModel):
    id: int; device_id: int; device: DeviceOut; quantity: int
    class Config: from_attributes = True

class SpaceEnergyStats(BaseModel):
    space_id:    int
    space_code:  str
    space_label: str
    total_hours: float   # horas de sesión acumuladas en el período
    total_kwh:   float   # kWh del puesto (solo dispositivos de escritorio)
    cost_eur:    float

class ZonaEnergyStats(BaseModel):
    zone_id:   int
    zone_code: str
    zone_name: str
    # Sala completa
    open_hours:       float   # horas que la sala estuvo abierta
    sala_watts:       int     # W instalados en la sala (AC + ilum.)
    sala_kwh:         float   # kWh consumidos por dispositivos de sala
    sala_cost_eur:    float
    # Puestos de trabajo
    workstation_kwh:      float
    workstation_cost_eur: float
    # Total
    total_kwh:      float
    total_cost_eur: float
    # Detalle por puesto
    spaces: list[SpaceEnergyStats]

class EnergyStatsResponse(BaseModel):
    period:         str
    from_date:      str
    to_date:        str
    total_kwh:      float
    total_cost_eur: float
    price_per_kwh:  float
    salas:          list[ZonaEnergyStats]

class ReportRequest(BaseModel):
    period: str = "week"   # today | week | month | year


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_period_range(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise HTTPException(400, "Período no válido. Usa: today, week, month, year")
    return start, now


def _tz(dt: datetime) -> datetime:
    """Garantiza que el datetime tiene tzinfo UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt


def _session_hours(
    occ: models.Occupancy,
    period_start: datetime,
    period_end: datetime,
) -> float:
    """Horas activas de una sesión dentro del período."""
    entered = _tz(occ.entered_at)
    exited  = _tz(occ.exited_at) if occ.exited_at else period_end
    start   = max(entered, period_start)
    end     = min(exited, period_end)
    return max(0.0, (end - start).total_seconds() / 3600)


def calc_space_energy(
    space: models.Space,
    occupancies: list,
    period_start: datetime,
    period_end: datetime,
) -> SpaceEnergyStats:
    """
    Consumo de un puesto = Σ(duración sesión) × watts de dispositivos de escritorio.
    Los dispositivos de sala (AC, luz) se calculan a nivel de zona.
    """
    # Watts de dispositivos de puesto (desde la BD)
    desk_watts = sum(
        a.device.watts * a.quantity
        for a in space.device_assignments
    )

    total_hours = sum(
        _session_hours(occ, period_start, period_end)
        for occ in occupancies
        if occ.space_id == space.id
    )

    kwh      = round(desk_watts * total_hours / 1000, 4)
    cost_eur = round(kwh * PRICE_PER_KWH, 4)

    return SpaceEnergyStats(
        space_id=space.id,
        space_code=space.code,
        space_label=space.label,
        total_hours=round(total_hours, 2),
        total_kwh=kwh,
        cost_eur=cost_eur,
    )


def calc_zona_energy(
    zone: models.Zone,
    occupancies: list,
    period_start: datetime,
    period_end: datetime,
) -> ZonaEnergyStats:
    """
    Consumo total de una sala:
      1. Horas de sala abierta (primer entrada → última salida del período)
         × watts de dispositivos de sala (AC + iluminación)
      2. Suma de consumos individuales de cada puesto
    """
    zone_space_ids = {s.id for s in zone.spaces}
    zona_occs      = [o for o in occupancies if o.space_id in zone_space_ids]

    # ── Tiempo que la sala estuvo abierta ──
    open_hours = 0.0
    if zona_occs:
        first_entry = min(_tz(o.entered_at) for o in zona_occs)
        last_exit   = max(
            (_tz(o.exited_at) if o.exited_at else period_end)
            for o in zona_occs
        )
        start      = max(first_entry, period_start)
        end        = min(last_exit, period_end)
        open_hours = max(0.0, (end - start).total_seconds() / 3600)

    sala_w    = SALA_WATTS.get(zone.code, 0)
    sala_kwh  = round(sala_w * open_hours / 1000, 4)
    sala_cost = round(sala_kwh * PRICE_PER_KWH, 4)

    # ── Consumo de cada puesto ──
    space_stats = [
        calc_space_energy(s, occupancies, period_start, period_end)
        for s in zone.spaces
    ]
    ws_kwh  = round(sum(s.total_kwh  for s in space_stats), 4)
    ws_cost = round(sum(s.cost_eur   for s in space_stats), 4)

    return ZonaEnergyStats(
        zone_id=zone.id,
        zone_code=zone.code,
        zone_name=zone.name,
        open_hours=round(open_hours, 2),
        sala_watts=sala_w,
        sala_kwh=sala_kwh,
        sala_cost_eur=sala_cost,
        workstation_kwh=ws_kwh,
        workstation_cost_eur=ws_cost,
        total_kwh=round(sala_kwh + ws_kwh, 4),
        total_cost_eur=round(sala_cost + ws_cost, 4),
        spaces=space_stats,
    )


# ── Endpoints — catálogo de dispositivos ──────────────────────────────────────

@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.Device).all()


@router.post("/devices", response_model=DeviceOut)
def create_device(
    data: DeviceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    device = models.Device(**data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


# ── Endpoints — asignación de dispositivos ────────────────────────────────────

@router.get("/spaces/{space_id}/devices", response_model=list[AssignmentOut])
def list_space_devices(
    space_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    space = db.query(models.Space).filter_by(id=space_id).first()
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    return space.device_assignments


@router.post("/spaces/{space_id}/devices", response_model=AssignmentOut)
def assign_device(
    space_id: int,
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    _=Depends(require_profesor_or_admin),
):
    space  = db.query(models.Space).filter_by(id=space_id).first()
    device = db.query(models.Device).filter_by(id=data.device_id).first()
    if not space:  raise HTTPException(404, "Espacio no encontrado")
    if not device: raise HTTPException(404, "Dispositivo no encontrado")
    a = models.DeviceAssignment(space_id=space_id, device_id=data.device_id, quantity=data.quantity)
    db.add(a); db.commit(); db.refresh(a)
    return a


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    a = db.query(models.DeviceAssignment).filter_by(id=assignment_id).first()
    if not a: raise HTTPException(404, "Asignación no encontrada")
    db.delete(a); db.commit()
    return {"detail": "Asignación eliminada"}


# ── Endpoints — estadísticas ──────────────────────────────────────────────────

@router.get("/stats", response_model=EnergyStatsResponse)
def energy_stats(
    period:  str = Query("month"),
    zone_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    period_start, period_end = get_period_range(period)

    query = db.query(models.Zone)
    if zone_id:
        query = query.filter(models.Zone.id == zone_id)
    zones = query.all()

    all_space_ids = [s.id for z in zones for s in z.spaces]
    occupancies   = db.query(models.Occupancy).filter(
        models.Occupancy.space_id.in_(all_space_ids),
        models.Occupancy.entered_at >= period_start,
        models.Occupancy.entered_at <= period_end,
    ).all()

    sala_stats = [
        calc_zona_energy(z, occupancies, period_start, period_end)
        for z in zones
    ]
    total_kwh  = round(sum(s.total_kwh      for s in sala_stats), 4)
    total_cost = round(sum(s.total_cost_eur for s in sala_stats), 4)

    return EnergyStatsResponse(
        period=period,
        from_date=period_start.isoformat(),
        to_date=period_end.isoformat(),
        total_kwh=total_kwh,
        total_cost_eur=total_cost,
        price_per_kwh=PRICE_PER_KWH,
        salas=sala_stats,
    )


# ── Endpoint — envío de informe por email ─────────────────────────────────────

@router.post("/report")
def send_report(
    body: ReportRequest,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Genera las estadísticas del período y envía el informe por email al administrador."""
    from email_report import send_energy_report

    period_start, period_end = get_period_range(body.period)
    zones = db.query(models.Zone).all()

    all_space_ids = [s.id for z in zones for s in z.spaces]
    occupancies   = db.query(models.Occupancy).filter(
        models.Occupancy.space_id.in_(all_space_ids),
        models.Occupancy.entered_at >= period_start,
        models.Occupancy.entered_at <= period_end,
    ).all()

    sala_stats = [
        calc_zona_energy(z, occupancies, period_start, period_end)
        for z in zones
    ]
    total_kwh  = round(sum(s.total_kwh      for s in sala_stats), 4)
    total_cost = round(sum(s.total_cost_eur for s in sala_stats), 4)

    stats = {
        "period":         body.period,
        "from_date":      period_start.isoformat(),
        "to_date":        period_end.isoformat(),
        "total_kwh":      total_kwh,
        "total_cost_eur": total_cost,
        "price_per_kwh":  PRICE_PER_KWH,
        "salas":          [s.model_dump() for s in sala_stats],
    }

    period_labels = {
        "today": "diario", "week": "semanal",
        "month": "mensual", "year": "anual",
    }
    ok = send_energy_report(stats, period_labels.get(body.period, body.period))

    if ok:
        return {"detail": f"Informe {body.period} enviado correctamente"}
    raise HTTPException(500, "Error al enviar el email. Revisa la configuración.")
