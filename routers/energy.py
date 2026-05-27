"""
Router de energía — estadísticas de consumo eléctrico por espacio y período.

Endpoints:
  GET  /energy/devices                  → lista todos los dispositivos del catálogo
  POST /energy/devices                  → crea un dispositivo (admin)
  GET  /energy/spaces/{id}/devices      → dispositivos asignados a un espacio
  POST /energy/spaces/{id}/devices      → asigna un dispositivo a un espacio (admin/prof)
  DELETE /energy/assignments/{id}       → elimina una asignación (admin)
  GET  /energy/stats                    → estadísticas de consumo (filtro por período, espacio, zona)
  POST /energy/report                   → genera y envía el informe por email (admin)
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


# ── Schemas locales ────────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    name: str
    watts: float
    location: models.DeviceLocationEnum
    description: Optional[str] = None

class DeviceOut(BaseModel):
    id: int
    name: str
    watts: float
    location: models.DeviceLocationEnum
    description: Optional[str]
    class Config:
        from_attributes = True

class AssignmentCreate(BaseModel):
    device_id: int
    quantity: int = 1

class AssignmentOut(BaseModel):
    id: int
    device_id: int
    device: DeviceOut
    quantity: int
    class Config:
        from_attributes = True

class SpaceEnergyStats(BaseModel):
    space_id: int
    space_code: str
    space_label: str
    total_hours: float
    total_wh: float
    total_kwh: float
    cost_eur: float

class EnergyStatsResponse(BaseModel):
    period: str
    from_date: str
    to_date: str
    total_kwh: float
    total_cost_eur: float
    price_per_kwh: float
    spaces: list[SpaceEnergyStats]

class ReportRequest(BaseModel):
    period: str = "week"   # today, week, month, year


# ── Precio por kWh ────────────────────────────────────────────────────────────
PRICE_PER_KWH = 0.18


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_period_range(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise HTTPException(status_code=400, detail="Período no válido. Usa: today, week, month, year")
    return start, now


def calc_space_energy(space: models.Space, occupancies: list, period_start: datetime, period_end: datetime) -> SpaceEnergyStats:
    total_watts = sum(
        a.device.watts * a.quantity
        for a in space.device_assignments
    )
    total_seconds = 0.0
    for occ in occupancies:
        if occ.space_id != space.id:
            continue
        entered = occ.entered_at
        if entered.tzinfo is None:
            entered = entered.replace(tzinfo=timezone.utc)
        start = max(entered, period_start)
        end = occ.exited_at if occ.exited_at else period_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        end = min(end, period_end)
        if end > start:
            total_seconds += (end - start).total_seconds()

    total_hours = total_seconds / 3600
    total_wh    = total_watts * total_hours
    total_kwh   = total_wh / 1000
    cost_eur    = total_kwh * PRICE_PER_KWH

    return SpaceEnergyStats(
        space_id=space.id,
        space_code=space.code,
        space_label=space.label,
        total_hours=round(total_hours, 2),
        total_wh=round(total_wh, 2),
        total_kwh=round(total_kwh, 4),
        cost_eur=round(cost_eur, 4),
    )


# ── Endpoints — catálogo de dispositivos ──────────────────────────────────────

@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.Device).all()


@router.post("/devices", response_model=DeviceOut)
def create_device(data: DeviceCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    device = models.Device(**data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


# ── Endpoints — asignación de dispositivos ────────────────────────────────────

@router.get("/spaces/{space_id}/devices", response_model=list[AssignmentOut])
def list_space_devices(space_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    space = db.query(models.Space).filter_by(id=space_id).first()
    if not space:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    return space.device_assignments


@router.post("/spaces/{space_id}/devices", response_model=AssignmentOut)
def assign_device(space_id: int, data: AssignmentCreate, db: Session = Depends(get_db), _=Depends(require_profesor_or_admin)):
    space = db.query(models.Space).filter_by(id=space_id).first()
    if not space:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    device = db.query(models.Device).filter_by(id=data.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    assignment = models.DeviceAssignment(space_id=space_id, device_id=data.device_id, quantity=data.quantity)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete("/assignments/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    assignment = db.query(models.DeviceAssignment).filter_by(id=assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    db.delete(assignment)
    db.commit()
    return {"detail": "Asignación eliminada"}


# ── Endpoints — estadísticas ──────────────────────────────────────────────────

@router.get("/stats", response_model=EnergyStatsResponse)
def energy_stats(
    period: str = Query("month"),
    space_id: Optional[int] = Query(None),
    zone_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    period_start, period_end = get_period_range(period)

    query = db.query(models.Space)
    if space_id:
        query = query.filter(models.Space.id == space_id)
    if zone_id:
        query = query.filter(models.Space.zone_id == zone_id)
    spaces = query.all()

    occupancies = db.query(models.Occupancy).filter(
        models.Occupancy.entered_at >= period_start,
        models.Occupancy.entered_at <= period_end,
    ).all()

    space_stats = [
        calc_space_energy(space, occupancies, period_start, period_end)
        for space in spaces
    ]

    total_kwh  = round(sum(s.total_kwh for s in space_stats), 4)
    total_cost = round(sum(s.cost_eur for s in space_stats), 4)

    return EnergyStatsResponse(
        period=period,
        from_date=period_start.isoformat(),
        to_date=period_end.isoformat(),
        total_kwh=total_kwh,
        total_cost_eur=total_cost,
        price_per_kwh=PRICE_PER_KWH,
        spaces=space_stats,
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

    spaces      = db.query(models.Space).all()
    occupancies = db.query(models.Occupancy).filter(
        models.Occupancy.entered_at >= period_start,
        models.Occupancy.entered_at <= period_end,
    ).all()

    space_stats = [
        calc_space_energy(space, occupancies, period_start, period_end)
        for space in spaces
    ]

    total_kwh  = round(sum(s.total_kwh for s in space_stats), 4)
    total_cost = round(sum(s.cost_eur for s in space_stats), 4)

    stats = {
        "period": body.period,
        "from_date": period_start.isoformat(),
        "to_date": period_end.isoformat(),
        "total_kwh": total_kwh,
        "total_cost_eur": total_cost,
        "price_per_kwh": PRICE_PER_KWH,
        "spaces": [s.model_dump() for s in space_stats],
    }

    period_labels = {"today": "diario", "week": "semanal", "month": "mensual", "year": "anual"}
    ok = send_energy_report(stats, period_labels.get(body.period, body.period))

    if ok:
        return {"detail": f"Informe {body.period} enviado correctamente a peihaosun2007@gmail.com"}
    else:
        raise HTTPException(status_code=500, detail="Error al enviar el email. Revisa la configuración.")