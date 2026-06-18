"""Domain database models for leasing data."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leasing_voice_assistant.db.base import Base


class Property(Base):
    """Leasing community with exact structured facts."""

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    pet_policy: Mapped[str] = mapped_column(Text, nullable=False)
    parking_policy: Mapped[str] = mapped_column(Text, nullable=False)
    application_fee_cents: Mapped[int] = mapped_column(nullable=False)
    security_deposit_cents: Mapped[int] = mapped_column(nullable=False)
    lease_terms: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    units: Mapped[list["Unit"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="Unit.unit_number",
    )
    interests: Mapped[list["ProspectInterest"]] = relationship(back_populates="property")


class Unit(Base):
    """Rentable unit tied to a property."""

    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("property_id", "unit_number", name="uq_units_property_unit_number"),
        CheckConstraint("bedroom_count >= 0", name="ck_units_bedroom_count_non_negative"),
        CheckConstraint("bathroom_count > 0", name="ck_units_bathroom_count_positive"),
        CheckConstraint("rent_cents > 0", name="ck_units_rent_cents_positive"),
        CheckConstraint("square_feet > 0", name="ck_units_square_feet_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id"), nullable=False, index=True
    )
    unit_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    bedroom_count: Mapped[int] = mapped_column(nullable=False)
    bathroom_count: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    rent_cents: Mapped[int] = mapped_column(nullable=False)
    square_feet: Mapped[int] = mapped_column(nullable=False)
    availability_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    floor: Mapped[int] = mapped_column(nullable=False)
    view: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)

    property: Mapped[Property] = relationship(back_populates="units")
    interests: Mapped[list["ProspectInterest"]] = relationship(back_populates="unit")


class Prospect(Base):
    """Caller prospect keyed by normalized phone number."""

    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    interests: Mapped[list["ProspectInterest"]] = relationship(
        back_populates="prospect",
        cascade="all, delete-orphan",
    )


class ProspectInterest(Base):
    """Captured interest in either a property or a specific unit."""

    __tablename__ = "prospect_interests"
    __table_args__ = (
        CheckConstraint(
            "(property_id IS NOT NULL AND unit_id IS NULL) OR "
            "(property_id IS NULL AND unit_id IS NOT NULL)",
            name="ck_prospect_interests_exactly_one_target",
        ),
        Index(
            "uq_prospect_interests_property_target",
            "prospect_id",
            "property_id",
            unique=True,
            sqlite_where=text("property_id IS NOT NULL AND unit_id IS NULL"),
        ),
        Index(
            "uq_prospect_interests_unit_target",
            "prospect_id",
            "unit_id",
            unique=True,
            sqlite_where=text("unit_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    prospect_id: Mapped[int] = mapped_column(ForeignKey("prospects.id"), nullable=False, index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    prospect: Mapped[Prospect] = relationship(back_populates="interests")
    property: Mapped[Property | None] = relationship(back_populates="interests")
    unit: Mapped[Unit | None] = relationship(back_populates="interests")
