"""Deterministic local seed data."""

from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from leasing_voice_assistant.core.config import get_settings
from leasing_voice_assistant.db.models import Property, Prospect, ProspectInterest, Unit
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


def seed_database(session: Session, *, reset: bool = False) -> None:
    """Load deterministic leasing seed data."""
    if reset:
        session.execute(delete(ProspectInterest))
        session.execute(delete(Prospect))
        session.execute(delete(Unit))
        session.execute(delete(Property))

    existing_property = session.scalar(select(Property.id).limit(1))
    if existing_property is not None:
        return

    aurora = Property(
        name="Aurora Heights",
        address="1250 Market Street",
        city="San Francisco",
        state="CA",
        phone="+14155550140",
        description="Transit-friendly apartments with rooftop lounge and in-building fitness.",
        pet_policy="Cats and dogs are welcome, up to two pets per home, with breed restrictions.",
        parking_policy="Garage parking is available for $275 per month.",
        application_fee_cents=5500,
        security_deposit_cents=75000,
        lease_terms="9, 12, and 15 month lease terms",
        units=[
            Unit(
                unit_number="4B",
                bedroom_count=1,
                bathroom_count=Decimal("1.0"),
                rent_cents=325000,
                square_feet=690,
                availability_date=date(2026, 7, 15),
                status="available",
                floor=4,
                view="city",
                notes="Corner one-bedroom with west-facing windows.",
            ),
            Unit(
                unit_number="8A",
                bedroom_count=2,
                bathroom_count=Decimal("2.0"),
                rent_cents=482500,
                square_feet=1040,
                availability_date=date(2026, 8, 1),
                status="available",
                floor=8,
                view="bay",
                notes="Two-bedroom home with balcony and bay view.",
            ),
            Unit(
                unit_number="2C",
                bedroom_count=0,
                bathroom_count=Decimal("1.0"),
                rent_cents=245000,
                square_feet=510,
                availability_date=date(2026, 7, 1),
                status="reserved",
                floor=2,
                view="courtyard",
                notes="Studio with courtyard exposure; currently reserved.",
            ),
        ],
    )

    pine = Property(
        name="Pine Garden Flats",
        address="880 Pine Avenue",
        city="Oakland",
        state="CA",
        phone="+15105550188",
        description="Quiet garden-style community near Lake Merritt and local cafes.",
        pet_policy="One cat or dog is allowed per home with a monthly pet rent.",
        parking_policy="One surface parking space is included with each lease.",
        application_fee_cents=4500,
        security_deposit_cents=50000,
        lease_terms="12 month lease terms",
        units=[
            Unit(
                unit_number="11",
                bedroom_count=1,
                bathroom_count=Decimal("1.0"),
                rent_cents=262500,
                square_feet=735,
                availability_date=date(2026, 7, 20),
                status="available",
                floor=1,
                view="garden",
                notes="Ground-floor one-bedroom with patio.",
            ),
            Unit(
                unit_number="24",
                bedroom_count=2,
                bathroom_count=Decimal("1.5"),
                rent_cents=347500,
                square_feet=960,
                availability_date=date(2026, 9, 5),
                status="available",
                floor=2,
                view="tree-lined street",
                notes="Two-bedroom flat with extra storage.",
            ),
        ],
    )

    session.add_all([aurora, pine])
    session.flush()


def main() -> None:
    """Console entrypoint for loading deterministic local seed data."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed the local leasing voice assistant database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing properties, units, prospects, and interests before seeding.",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_sqlite_engine(settings.database_url)
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        seed_database(session, reset=args.reset)
        session.commit()

    print(f"Seeded database at {settings.database_url}.")
