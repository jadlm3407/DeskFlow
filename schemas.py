from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from models import RoleEnum, StatusEnum, FloorEnum


# ── AUTH ──────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    dni: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class TokenData(BaseModel):
    user_id: Optional[int] = None


# ── USERS ─────────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    dni: str
    nombre: str
    apellidos: str
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.estudiante

class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id: int
    dni: str
    nombre: str
    apellidos: str
    email: str
    role: RoleEnum
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ZONES ─────────────────────────────────────────────────────────────────────
class ZoneCreate(BaseModel):
    code: str
    name: str
    floor: FloorEnum
    description: Optional[str] = None

class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class ZoneOut(BaseModel):
    id: int
    code: str
    name: str
    floor: FloorEnum
    description: Optional[str]
    spaces: list["SpaceOut"] = []

    model_config = {"from_attributes": True}

class ZoneSummary(BaseModel):
    id: int
    code: str
    name: str
    floor: FloorEnum
    total_spaces: int
    available: int
    occupied: int
    partial: int
    occupancy_pct: float

    model_config = {"from_attributes": True}


# ── SPACES ────────────────────────────────────────────────────────────────────
class SpaceCreate(BaseModel):
    code: str
    label: str
    zone_id: int
    capacity: int = 0
    pos_x: float = 0
    pos_y: float = 0
    pos_w: float = 10
    pos_h: float = 10

class SpaceUpdate(BaseModel):
    label: Optional[str] = None
    capacity: Optional[int] = None
    status: Optional[StatusEnum] = None
    occupancy: Optional[int] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_w: Optional[float] = None
    pos_h: Optional[float] = None

class SpaceOut(BaseModel):
    id: int
    code: str
    label: str
    zone_id: int
    capacity: int
    status: StatusEnum
    occupancy: int
    pos_x: float
    pos_y: float
    pos_w: float
    pos_h: float
    updated_at: datetime
    reservation_user_id: Optional[int] = None
    reservation_expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReservationOut(BaseModel):
    space_id: int
    user_id: int
    expires_at: datetime
    message: str


# ── OCCUPANCY LOG ─────────────────────────────────────────────────────────────
class OccupancyOut(BaseModel):
    id: int
    user_id: int
    space_id: int
    entered_at: datetime
    exited_at: Optional[datetime]
    active: bool

    model_config = {"from_attributes": True}


# ── WS EVENT ─────────────────────────────────────────────────────────────────
class WSEvent(BaseModel):
    event: str          # "space_updated" | "zone_updated"
    payload: dict


# Forward refs
Token.model_rebuild()
ZoneOut.model_rebuild()
