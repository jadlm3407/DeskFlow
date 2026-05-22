"""
Router NFC — identificación de usuarios por tarjeta NFC.

Endpoints:
  POST /nfc/scan          → el ESP32 envía el UID y recibe un token JWT
  GET  /nfc/pending       → el frontend consulta si hay sesión pendiente
  GET  /nfc/cards         → lista todas las tarjetas (admin)
  POST /nfc/cards         → registra una tarjeta nueva (admin)
  DELETE /nfc/cards/{id}  → elimina una tarjeta (admin)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import threading

import models
import schemas
from database import get_db
from auth import create_access_token, require_admin

router = APIRouter(prefix="/nfc", tags=["nfc"])

# ── Sesión pendiente en memoria (se limpia al ser recogida o tras 30s) ─────────
_pending_lock = threading.Lock()
_pending_session: dict = {}          # { token, user, expires_at }
PENDING_TTL_SECONDS = 30


# ── Schemas ───────────────────────────────────────────────────────────────────

class NfcScanRequest(BaseModel):
    uid: str

class NfcScanResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: schemas.UserOut

class NfcPendingResponse(BaseModel):
    available: bool
    access_token: Optional[str] = None
    user: Optional[schemas.UserOut] = None

class NfcCardCreate(BaseModel):
    uid: str
    user_id: int
    label: Optional[str] = None

class NfcCardOut(BaseModel):
    id: int
    uid: str
    user_id: int
    label: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan", response_model=NfcScanResponse)
def nfc_scan(body: NfcScanRequest, db: Session = Depends(get_db)):
    """
    El ESP32 llama a este endpoint cuando detecta una tarjeta NFC.
    Guarda la sesión en memoria para que el frontend la recoja con GET /nfc/pending.
    """
    uid = body.uid.upper().strip()

    card = db.query(models.NfcCard).filter_by(uid=uid, is_active=True).first()
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no registrada o inactiva")

    user = card.user
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    token = create_access_token(user.id)
    user_out = schemas.UserOut.model_validate(user)

    with _pending_lock:
        _pending_session.clear()
        _pending_session.update({
            "token": token,
            "user": user_out,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=PENDING_TTL_SECONDS),
        })

    return NfcScanResponse(access_token=token, user=user_out)


@router.get("/pending", response_model=NfcPendingResponse)
def nfc_pending():
    """
    El frontend consulta este endpoint cada 2 segundos.
    Si hay una sesión pendiente la devuelve y la elimina (consumo único).
    """
    with _pending_lock:
        if not _pending_session:
            return NfcPendingResponse(available=False)

        # Comprobar si ha expirado
        if datetime.now(timezone.utc) > _pending_session["expires_at"]:
            _pending_session.clear()
            return NfcPendingResponse(available=False)

        token = _pending_session["token"]
        user  = _pending_session["user"]
        _pending_session.clear()   # consumo único — el frontend solo lo recoge una vez

    return NfcPendingResponse(available=True, access_token=token, user=user)


@router.get("/cards", response_model=list[NfcCardOut])
def list_cards(db: Session = Depends(get_db), _=Depends(require_admin)):
    return db.query(models.NfcCard).all()


@router.post("/cards", response_model=NfcCardOut)
def register_card(body: NfcCardCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    uid = body.uid.upper().strip()

    if db.query(models.NfcCard).filter_by(uid=uid).first():
        raise HTTPException(status_code=400, detail="UID ya registrado")

    user = db.get(models.User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    card = models.NfcCard(uid=uid, user_id=body.user_id, label=body.label)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/cards/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    card = db.get(models.NfcCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    db.delete(card)
    db.commit()
    return {"detail": f"Tarjeta {card.uid} eliminada"}