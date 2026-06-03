from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone, timedelta
import asyncio

from database import get_db, SessionLocal
from auth import get_current_user, require_admin, require_profesor_or_admin
from websocket_manager import manager
import models, schemas

router = APIRouter(prefix="/spaces", tags=["spaces"])

# ── Configuración ─────────────────────────────────────────────────────────────
SALA1_CODE            = "SP1"
SALA2_CODE            = "SP2"
SALAS_PROFE_CODES     = {"SP1", "SP2"}   # zonas de puestos de profesor
UNLOCK_THRESHOLD      = 0.75
RESERVATION_TTL       = 300              # 5 min para salas de reuniones

_expiry_tasks: dict[int, asyncio.Task] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_status(space: models.Space) -> models.StatusEnum:
    if space.capacity == 0:
        return models.StatusEnum.available
    if space.occupancy == 0:
        return models.StatusEnum.available
    elif space.occupancy >= space.capacity:
        return models.StatusEnum.occupied
    else:
        return models.StatusEnum.partial


async def _broadcast_space(space: models.Space):
    payload = schemas.SpaceOut.model_validate(space).model_dump(mode="json")
    await manager.broadcast("space_updated", payload)


def _is_profe_zone(zone_code: str) -> bool:
    return zone_code in SALAS_PROFE_CODES


def _user_has_active_profe_checkin(user_id: int, db: Session) -> bool:
    """Devuelve True si el usuario ya tiene un puesto activo en SP1 o SP2."""
    sp1 = db.query(models.Zone).filter_by(code=SALA1_CODE).first()
    sp2 = db.query(models.Zone).filter_by(code=SALA2_CODE).first()
    zone_ids = [z.id for z in [sp1, sp2] if z]
    if not zone_ids:
        return False
    profe_space_ids = [
        s.id for s in db.query(models.Space).filter(
            models.Space.zone_id.in_(zone_ids)
        ).all()
    ]
    if not profe_space_ids:
        return False
    return db.query(models.Occupancy).filter(
        models.Occupancy.user_id == user_id,
        models.Occupancy.space_id.in_(profe_space_ids),
        models.Occupancy.active == True,
    ).first() is not None


async def _check_sala_unlock(db: Session):
    zona1 = db.query(models.Zone).filter_by(code=SALA1_CODE).first()
    zona2 = db.query(models.Zone).filter_by(code=SALA2_CODE).first()
    if not zona1 or not zona2:
        return

    spaces1 = db.query(models.Space).filter_by(zone_id=zona1.id).all()
    if not spaces1:
        return

    occupied1 = sum(
        1 for s in spaces1
        if s.status in (models.StatusEnum.occupied, models.StatusEnum.partial)
    )
    pct1 = occupied1 / len(spaces1)

    spaces2      = db.query(models.Space).filter_by(zone_id=zona2.id).all()
    sala2_active = any(s.occupancy > 0 for s in spaces2)

    changed = False
    if pct1 >= UNLOCK_THRESHOLD:
        for s in spaces2:
            if s.status == models.StatusEnum.maintenance:
                s.status = models.StatusEnum.available
                changed = True
    elif not sala2_active:
        for s in spaces2:
            if s.status == models.StatusEnum.available:
                s.status = models.StatusEnum.maintenance
                changed = True

    if changed:
        db.commit()
        for s in spaces2:
            db.refresh(s)
            await _broadcast_space(s)


# ── Expiración de reservas ────────────────────────────────────────────────────

def _cancel_expiry(space_id: int):
    task = _expiry_tasks.pop(space_id, None)
    if task:
        task.cancel()


async def _expire_reservation(space_id: int):
    await asyncio.sleep(RESERVATION_TTL)
    db = SessionLocal()
    try:
        space = db.get(models.Space, space_id)
        if space and space.status == models.StatusEnum.reserved:
            space.status                = models.StatusEnum.available
            space.reservation_user_id   = None
            space.reservation_expires_at = None
            db.commit()
            db.refresh(space)
            payload = schemas.SpaceOut.model_validate(space).model_dump(mode="json")
            await manager.broadcast("space_updated", payload)
            await manager.broadcast("reservation_expired", {"space_id": space_id})
    finally:
        db.close()
    _expiry_tasks.pop(space_id, None)


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[schemas.SpaceOut])
def list_spaces(
    zone_id: int | None = None,
    status: models.StatusEnum | None = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.Space)
    if zone_id:
        q = q.filter(models.Space.zone_id == zone_id)
    if status:
        q = q.filter(models.Space.status == status)
    return q.all()


@router.get("/{space_id}", response_model=schemas.SpaceOut)
def get_space(
    space_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    return space


@router.post("/", response_model=schemas.SpaceOut, dependencies=[Depends(require_admin)])
def create_space(body: schemas.SpaceCreate, db: Session = Depends(get_db)):
    if not db.get(models.Zone, body.zone_id):
        raise HTTPException(404, "Zona no encontrada")
    space = models.Space(**body.model_dump())
    db.add(space)
    db.commit()
    db.refresh(space)
    return space


@router.patch("/{space_id}", response_model=schemas.SpaceOut)
async def update_space(
    space_id: int,
    body: schemas.SpaceUpdate,
    db: Session = Depends(get_db),
    current: models.User = Depends(require_profesor_or_admin),
):
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(space, field, value)
    if "occupancy" in body.model_dump(exclude_unset=True):
        space.status = _compute_status(space)
    db.commit()
    db.refresh(space)
    await _broadcast_space(space)
    return space


@router.delete("/{space_id}", dependencies=[Depends(require_admin)])
def delete_space(space_id: int, db: Session = Depends(get_db)):
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    _cancel_expiry(space_id)
    db.delete(space)
    db.commit()
    return {"detail": f"Espacio {space.code} eliminado"}


# ── RESERVA (salas de reuniones) ──────────────────────────────────────────────

@router.post("/{space_id}/reserve", response_model=schemas.ReservationOut)
async def reserve(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    if space.status == models.StatusEnum.maintenance:
        raise HTTPException(409, "Sala cerrada")
    if space.status == models.StatusEnum.reserved:
        raise HTTPException(409, "La sala ya está reservada")
    if space.capacity > 0 and space.occupancy >= space.capacity:
        raise HTTPException(409, "Sala llena")

    expires = datetime.now(timezone.utc) + timedelta(seconds=RESERVATION_TTL)
    space.status                 = models.StatusEnum.reserved
    space.reservation_user_id   = current.id
    space.reservation_expires_at = expires
    db.commit()
    db.refresh(space)

    _cancel_expiry(space_id)
    _expiry_tasks[space_id] = asyncio.create_task(_expire_reservation(space_id))

    await _broadcast_space(space)
    return schemas.ReservationOut(
        space_id=space_id,
        user_id=current.id,
        expires_at=expires,
        message=f"Sala reservada por 5 minutos",
    )


@router.post("/{space_id}/cancel-reserve")
async def cancel_reserve(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    if space.status != models.StatusEnum.reserved:
        raise HTTPException(409, "La sala no está reservada")
    if space.reservation_user_id != current.id:
        raise HTTPException(403, "No eres el titular de esta reserva")

    _cancel_expiry(space_id)
    space.status                 = models.StatusEnum.available
    space.reservation_user_id   = None
    space.reservation_expires_at = None
    db.commit()
    db.refresh(space)
    await _broadcast_space(space)
    return {"detail": "Reserva cancelada"}


# ── CHECK-IN ──────────────────────────────────────────────────────────────────

@router.post("/{space_id}/checkin", response_model=schemas.OccupancyOut)
async def checkin(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    if space.status == models.StatusEnum.maintenance:
        raise HTTPException(409, "Sala cerrada — acceso no disponible")
    if space.capacity > 0 and space.occupancy >= space.capacity:
        raise HTTPException(409, "Puesto ocupado")

    # ── Regla: un solo puesto activo por profesor en SP1/SP2 ──────────────────
    zone = db.get(models.Zone, space.zone_id)
    if zone and _is_profe_zone(zone.code):
        if _user_has_active_profe_checkin(current.id, db):
            raise HTTPException(409, "Ya tienes un puesto activo — haz checkout antes de ocupar otro")

    existing = (
        db.query(models.Occupancy)
        .filter_by(user_id=current.id, space_id=space_id, active=True)
        .first()
    )
    if existing:
        raise HTTPException(409, "Ya tienes check-in activo en este espacio")

    occ = models.Occupancy(user_id=current.id, space_id=space_id)
    db.add(occ)
    space.occupancy = (space.occupancy or 0) + 1
    space.status    = _compute_status(space)
    db.commit()
    db.refresh(occ)
    db.refresh(space)

    await _broadcast_space(space)
    await _check_sala_unlock(db)
    return occ


# ── CHECK-OUT ─────────────────────────────────────────────────────────────────

@router.post("/{space_id}/checkout", response_model=schemas.OccupancyOut)
async def checkout(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    occ = (
        db.query(models.Occupancy)
        .filter_by(user_id=current.id, space_id=space_id, active=True)
        .first()
    )
    if not occ:
        raise HTTPException(404, "No tienes check-in activo en este espacio")

    occ.exited_at = datetime.now(timezone.utc)
    occ.active    = False

    space = db.get(models.Space, space_id)
    space.occupancy = max(0, (space.occupancy or 1) - 1)
    space.status    = _compute_status(space)
    db.commit()
    db.refresh(occ)
    db.refresh(space)

    await _broadcast_space(space)
    await _check_sala_unlock(db)
    return occ


# ── HISTORIAL ─────────────────────────────────────────────────────────────────

@router.get("/{space_id}/history", response_model=List[schemas.OccupancyOut])
def occupancy_history(
    space_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_profesor_or_admin),
):
    return (
        db.query(models.Occupancy)
        .filter_by(space_id=space_id)
        .order_by(models.Occupancy.entered_at.desc())
        .limit(limit)
        .all()
    )