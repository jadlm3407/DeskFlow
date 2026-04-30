from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from auth import get_current_user, require_admin, hash_password
import models, schemas

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[schemas.UserOut], dependencies=[Depends(require_admin)])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    role: models.RoleEnum | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.User)
    if role:
        q = q.filter(models.User.role == role)
    return q.offset(skip).limit(limit).all()


@router.post("/", response_model=schemas.UserOut, dependencies=[Depends(require_admin)])
def create_user(body: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.dni == body.dni).first():
        raise HTTPException(400, "DNI ya registrado")
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(400, "Email ya registrado")

    user = models.User(
        dni=body.dni,
        nombre=body.nombre,
        apellidos=body.apellidos,
        email=body.email,
        hashed_pw=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: int,
    current: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Un usuario sólo puede ver su propio perfil; admin puede ver cualquiera
    if current.role != models.RoleEnum.admin and current.id != user_id:
        raise HTTPException(403, "Sin permisos")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    body: schemas.UserUpdate,
    current: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != models.RoleEnum.admin and current.id != user_id:
        raise HTTPException(403, "Sin permisos")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    # No-admin no puede cambiar su propio rol ni desactivarse
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in ("role", "is_active") and current.role != models.RoleEnum.admin:
            raise HTTPException(403, f"No puedes cambiar '{field}'")
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    db.delete(user)
    db.commit()
    return {"detail": f"Usuario {user.dni} eliminado"}
