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

RESERVATION_TTL_SECONDS = 300   # 5 minutos

# ── Tareas de expiración en vuelo: space_id -> asyncio.Task ───────────────────
_expiry_tasks: dict[int, asyncio.Task] = {}


def _compute_status(space: models.Space) -> models.StatusEnum:
    if space.capacity == 0:
        return models.StatusEnum.available
    ratio = space.occupancy / space.capacity
    if ratio == 0:
        return models.StatusEnum.available
    elif ratio >= 1:
        return models.StatusEnum.occupied
    else:
        return models.StatusEnum.partial


async def _broadcast_space(space: models.Space):
    payload = schemas.SpaceOut.model_validate(space).model_dump(mode="json")
    await manager.broadcast("space_updated", payload)


def _cancel_expiry(space_id: int):
    task = _expiry_tasks.pop(space_id, None)
    if task and not task.done():
        task.cancel()


async def _expire_reservation(space_id: int):
    """Cancela la reserva tras TTL si no se confirmó."""
    await asyncio.sleep(RESERVATION_TTL_SECONDS)
    db = SessionLocal()
    try:
        space = db.get(models.Space, space_id)
        if space and space.status == models.StatusEnum.reserved:
            space.status = models.StatusEnum.available
            space.reservation_user_id = None
            space.reservation_expires_at = None
            db.commit()
            db.refresh(space)
            await _broadcast_space(space)
            await manager.broadcast("reservation_expired", {"space_id": space_id})
    finally:
        db.close()
    _expiry_tasks.pop(space_id, None)


# ── CRUD ─────────────────────────────────────────────────────────────────────
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


# ── RESERVA ───────────────────────────────────────────────────────────────────
@router.post("/{space_id}/reserve", response_model=schemas.ReservationOut)
async def reserve_space(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """
    Reserva un espacio durante RESERVATION_TTL_SECONDS (5 min).
    Si no llega POST /confirm antes de que expire, se cancela automáticamente.
    """
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    if space.status == models.StatusEnum.maintenance:
        raise HTTPException(409, "Espacio en mantenimiento")
    if space.status == models.StatusEnum.reserved:
        # Comprobar si la reserva ya expiró según el reloj (race condition mínima)
        now = datetime.now(timezone.utc)
        exp = space.reservation_expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and now < exp:
            raise HTTPException(409, "Espacio ya reservado")
    if space.capacity > 0 and space.occupancy >= space.capacity:
        raise HTTPException(409, "Espacio lleno")

    # Cancelar tarea anterior si la hubiera (reserva expirada no limpiada aún)
    _cancel_expiry(space_id)

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=RESERVATION_TTL_SECONDS)
    space.status = models.StatusEnum.reserved
    space.reservation_user_id = current.id
    space.reservation_expires_at = expires_at
    db.commit()
    db.refresh(space)

    # Lanzar tarea de expiración en background
    task = asyncio.create_task(_expire_reservation(space_id))
    _expiry_tasks[space_id] = task

    await _broadcast_space(space)

    return schemas.ReservationOut(
        space_id=space_id,
        user_id=current.id,
        expires_at=expires_at,
        message=f"Reserva activa. Confirma en {RESERVATION_TTL_SECONDS // 60} min o se cancelará.",
    )


@router.post("/{space_id}/confirm", response_model=schemas.OccupancyOut)
async def confirm_reservation(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """
    Confirma la reserva → convierte en check-in real y cancela el timer de expiración.
    Solo puede confirmarla el mismo usuario que reservó.
    """
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    if space.status != models.StatusEnum.reserved:
        raise HTTPException(409, "El espacio no tiene una reserva activa")
    if space.reservation_user_id != current.id:
        raise HTTPException(403, "No eres el titular de esta reserva")

    # Verificar que no haya expirado (protección ante race condition)
    now = datetime.now(timezone.utc)
    exp = space.reservation_expires_at
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and now > exp:
        raise HTTPException(410, "La reserva ha expirado")

    # Cancelar timer
    _cancel_expiry(space_id)

    # Crear occupancy real
    occ = models.Occupancy(user_id=current.id, space_id=space_id)
    db.add(occ)

    space.occupancy = (space.occupancy or 0) + 1
    space.status = _compute_status(space)
    space.reservation_user_id = None
    space.reservation_expires_at = None
    db.commit()
    db.refresh(occ)
    db.refresh(space)

    await _broadcast_space(space)
    return occ


# ── CHECK-IN / CHECK-OUT ──────────────────────────────────────────────────────
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
        raise HTTPException(409, "Espacio en mantenimiento")
    if space.status == models.StatusEnum.reserved and space.reservation_user_id != current.id:
        raise HTTPException(409, "Espacio reservado por otro usuario")
    if space.capacity > 0 and space.occupancy >= space.capacity:
        raise HTTPException(409, "Espacio lleno")

    existing = (
        db.query(models.Occupancy)
        .filter_by(user_id=current.id, space_id=space_id, active=True)
        .first()
    )
    if existing:
        raise HTTPException(409, "Ya tienes check-in en este espacio")

    # Si tenía reserva propia, cancelar timer al hacer checkin directo
    if space.reservation_user_id == current.id:
        _cancel_expiry(space_id)
        space.reservation_user_id = None
        space.reservation_expires_at = None

    occ = models.Occupancy(user_id=current.id, space_id=space_id)
    db.add(occ)

    space.occupancy = (space.occupancy or 0) + 1
    space.status = _compute_status(space)
    db.commit()
    db.refresh(occ)
    db.refresh(space)

    await _broadcast_space(space)
    return occ


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
    occ.active = False

    space = db.get(models.Space, space_id)
    space.occupancy = max(0, (space.occupancy or 1) - 1)
    space.status = _compute_status(space)
    db.commit()
    db.refresh(occ)
    db.refresh(space)

    await _broadcast_space(space)
    return occ


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
