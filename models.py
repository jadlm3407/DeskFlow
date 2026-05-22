from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database import Base


class RoleEnum(str, enum.Enum):
    admin = "admin"
    profesor = "profesor"
    estudiante = "estudiante"


class StatusEnum(str, enum.Enum):
    available = "available"
    reserved = "reserved"      # reservado, pendiente de confirmación
    occupied = "occupied"
    partial = "partial"
    maintenance = "maintenance"


class FloorEnum(str, enum.Enum):
    baja = "baja"
    primera = "primera"


# ── USERS ─────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    dni        = Column(String(20), unique=True, index=True, nullable=False)
    nombre     = Column(String(100), nullable=False)
    apellidos  = Column(String(150), nullable=False)
    email      = Column(String(150), unique=True, index=True, nullable=False)
    hashed_pw  = Column(String(255), nullable=False)
    role       = Column(Enum(RoleEnum), default=RoleEnum.estudiante, nullable=False)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    occupancies = relationship("Occupancy", back_populates="user")
    nfc_cards   = relationship("NfcCard", back_populates="user")


# ── ZONES ─────────────────────────────────────────────────────────────────────
class Zone(Base):
    __tablename__ = "zones"

    id          = Column(Integer, primary_key=True, index=True)
    code        = Column(String(10), unique=True, nullable=False)
    name        = Column(String(100), nullable=False)
    floor       = Column(Enum(FloorEnum), nullable=False)
    description = Column(String(255), nullable=True)

    spaces = relationship("Space", back_populates="zone", cascade="all, delete-orphan")


# ── SPACES ────────────────────────────────────────────────────────────────────
class Space(Base):
    __tablename__ = "spaces"

    id          = Column(Integer, primary_key=True, index=True)
    code        = Column(String(10), nullable=False)
    label       = Column(String(150), nullable=False)
    zone_id     = Column(Integer, ForeignKey("zones.id"), nullable=False)
    capacity    = Column(Integer, default=0)
    status      = Column(Enum(StatusEnum), default=StatusEnum.available)
    occupancy   = Column(Integer, default=0)
    pos_x       = Column(Float, default=0)
    pos_y       = Column(Float, default=0)
    pos_w       = Column(Float, default=10)
    pos_h       = Column(Float, default=10)
    updated_at              = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    reservation_user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    reservation_expires_at  = Column(DateTime(timezone=True), nullable=True)

    zone               = relationship("Zone", back_populates="spaces")
    occupancies        = relationship("Occupancy", back_populates="space")
    device_assignments = relationship("DeviceAssignment", back_populates="space")


# ── OCCUPANCIES ───────────────────────────────────────────────────────────────
class Occupancy(Base):
    __tablename__ = "occupancies"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    space_id   = Column(Integer, ForeignKey("spaces.id"), nullable=False)
    entered_at = Column(DateTime(timezone=True), server_default=func.now())
    exited_at  = Column(DateTime(timezone=True), nullable=True)
    active     = Column(Boolean, default=True)

    user  = relationship("User", back_populates="occupancies")
    space = relationship("Space", back_populates="occupancies")


# ── NFC CARDS ─────────────────────────────────────────────────────────────────
class NfcCard(Base):
    __tablename__ = "nfc_cards"

    id         = Column(Integer, primary_key=True, index=True)
    uid        = Column(String(50), unique=True, nullable=False)  # UID de la tarjeta
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    label      = Column(String(100), nullable=True)               # ej: "Tarjeta principal"
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="nfc_cards")


# ── ENERGY ────────────────────────────────────────────────────────────────────
class DeviceLocationEnum(str, enum.Enum):
    ceiling = "ceiling"
    wall    = "wall"
    floor   = "floor"
    desk    = "desk"


class Device(Base):
    __tablename__ = "devices"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    watts       = Column(Float, nullable=False)
    location    = Column(Enum(DeviceLocationEnum), nullable=False)
    description = Column(String(255), nullable=True)

    assignments = relationship("DeviceAssignment", back_populates="device")


class DeviceAssignment(Base):
    __tablename__ = "device_assignments"

    id        = Column(Integer, primary_key=True, index=True)
    space_id  = Column(Integer, ForeignKey("spaces.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    quantity  = Column(Integer, default=1)

    space  = relationship("Space", back_populates="device_assignments")
    device = relationship("Device", back_populates="assignments")