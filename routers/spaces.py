from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from database import get_db
from auth import get_current_user, require_admin, require_profesor_or_admin
from websocket_manager import manager
import models, schemas

router = APIRouter(prefix="/spaces", tags=["spaces"])

# ── Configuración de desbloqueo automático ────────────────────────────────────
SALA1_CODE        = "SP1"
SALA2_CODE        = "SP2"
UNLOCK_THRESHOLD  = 0.75   # SP2 se abre cuando SP1 ≥ 75 % ocupado
SPACE_WATTS       = 240    # W por puesto (PC 200 + Monitor 30 + Lámpara 10)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_status(space: models.Space) -> models.StatusEnum:
    """Recalcula el estado de un espacio en función de occupancy/capacity."""
    if space.capacity == 0:
        return models.StatusEnum.available
    if space.occupancy == 0:
        return models.StatusEnum.available
    elif space.occupancy >= space.capacity:
        return models.StatusEnum.occupied
    else:
        return models.StatusEnum.partial


async def _broadcast_space(space: models.Space):
    """Emite un evento WebSocket con el estado actualizado del espacio."""
    payload = schemas.SpaceOut.model_validate(space).model_dump(mode="json")
    await manager.broadcast("space_updated", payload)


async def _check_sala_unlock(db: Session):
    """
    Lógica de apertura/cierre automático de SP2 basada en la ocupación de SP1:

    • SP1 ≥ 75 % ocupado  → desbloquea todos los puestos de SP2 (maintenance → available)
    • SP1 <  75 % ocupado → re-bloquea SP2 SOLO si está completamente vacía
    """
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
        # Desbloquear SP2
        for s in spaces2:
            if s.status == models.StatusEnum.maintenance:
                s.status = models.StatusEnum.available
                changed = True
    elif not sala2_active:
        # Re-bloquear SP2 solo si está vacía
        for s in spaces2:
            if s.status == models.StatusEnum.available:
                s.status = models.StatusEnum.maintenance
                changed = True

    if changed:
        db.commit()
        for s in spaces2:
            db.refresh(s)
            await _broadcast_space(s)


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
    db.delete(space)
    db.commit()
    return {"detail": f"Espacio {space.code} eliminado"}


# ── CHECK-IN / CHECK-OUT ──────────────────────────────────────────────────────

@router.post("/{space_id}/checkin", response_model=schemas.OccupancyOut)
async def checkin(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """
    Registra la entrada de un usuario al puesto.
    A partir de este momento comienza a contarse el tiempo de sesión,
    que determinará el consumo energético estimado del puesto.
    """
    space = db.get(models.Space, space_id)
    if not space:
        raise HTTPException(404, "Espacio no encontrado")
    if space.status == models.StatusEnum.maintenance:
        raise HTTPException(409, "Sala cerrada — acceso no disponible")
    if space.capacity > 0 and space.occupancy >= space.capacity:
        raise HTTPException(409, "Puesto ocupado")

    existing = (
        db.query(models.Occupancy)
        .filter_by(user_id=current.id, space_id=space_id, active=True)
        .first()
    )
    if existing:
        raise HTTPException(409, "Ya tienes check-in activo en este espacio")

    # Crear registro de ocupación — el campo entered_at inicia el cronómetro
    occ = models.Occupancy(user_id=current.id, space_id=space_id)
    db.add(occ)
    space.occupancy = (space.occupancy or 0) + 1
    space.status    = _compute_status(space)
    db.commit()
    db.refresh(occ)
    db.refresh(space)

    await _broadcast_space(space)
    await _check_sala_unlock(db)   # ← comprueba si hay que desbloquear SP2
    return occ


@router.post("/{space_id}/checkout", response_model=schemas.OccupancyOut)
async def checkout(
    space_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """
    Registra la salida del usuario.
    exited_at - entered_at = duración de la sesión → base del cálculo de consumo.
    """
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
    await _check_sala_unlock(db)   # ← comprueba si hay que re-bloquear SP2
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
