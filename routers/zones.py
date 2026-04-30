from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from auth import get_current_user, require_admin, require_profesor_or_admin
import models, schemas

router = APIRouter(prefix="/zones", tags=["zones"])


def _zone_summary(zone: models.Zone) -> schemas.ZoneSummary:
    spaces = zone.spaces
    total = len(spaces)
    avail = sum(1 for s in spaces if s.status == models.StatusEnum.available)
    occ   = sum(1 for s in spaces if s.status == models.StatusEnum.occupied)
    part  = sum(1 for s in spaces if s.status == models.StatusEnum.partial)
    cap_total = sum(s.capacity for s in spaces)
    occ_total = sum(s.occupancy for s in spaces)
    pct = round((occ_total / cap_total * 100) if cap_total else 0, 1)
    return schemas.ZoneSummary(
        id=zone.id, code=zone.code, name=zone.name, floor=zone.floor,
        total_spaces=total, available=avail, occupied=occ, partial=part,
        occupancy_pct=pct,
    )


@router.get("/", response_model=List[schemas.ZoneSummary])
def list_zones(
    floor: models.FloorEnum | None = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.Zone)
    if floor:
        q = q.filter(models.Zone.floor == floor)
    return [_zone_summary(z) for z in q.all()]


@router.get("/{zone_id}", response_model=schemas.ZoneOut)
def get_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    zone = db.get(models.Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zona no encontrada")
    return zone


@router.post("/", response_model=schemas.ZoneOut, dependencies=[Depends(require_admin)])
def create_zone(body: schemas.ZoneCreate, db: Session = Depends(get_db)):
    if db.query(models.Zone).filter(models.Zone.code == body.code).first():
        raise HTTPException(400, "Código de zona ya existe")
    zone = models.Zone(**body.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.patch("/{zone_id}", response_model=schemas.ZoneOut, dependencies=[Depends(require_admin)])
def update_zone(zone_id: int, body: schemas.ZoneUpdate, db: Session = Depends(get_db)):
    zone = db.get(models.Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zona no encontrada")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/{zone_id}", dependencies=[Depends(require_admin)])
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    zone = db.get(models.Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zona no encontrada")
    db.delete(zone)
    db.commit()
    return {"detail": f"Zona {zone.code} eliminada"}
