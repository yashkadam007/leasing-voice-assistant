"""Prospect and interest repository."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from leasing_voice_assistant.db.models import Property, Prospect, ProspectInterest, Unit


class ProspectsRepository:
    """Write repository for prospects and captured interest."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_by_phone(
        self,
        phone_number: str,
        *,
        name: str | None = None,
        email: str | None = None,
    ) -> Prospect:
        """Create or update a prospect by normalized phone number."""
        normalized_phone = normalize_phone_number(phone_number)
        prospect = self.session.scalar(
            select(Prospect).where(Prospect.phone_number == normalized_phone)
        )
        if prospect is None:
            prospect = Prospect(phone_number=normalized_phone)
            self.session.add(prospect)

        clean_name = _clean_optional_text(name)
        clean_email = _clean_optional_text(email)
        if clean_name is not None:
            prospect.name = clean_name
        if clean_email is not None:
            prospect.email = clean_email

        self.session.flush()
        return prospect

    def create_interest(
        self,
        *,
        prospect_id: int,
        property_id: int | None = None,
        unit_id: int | None = None,
        notes: str | None = None,
    ) -> tuple[ProspectInterest, bool]:
        """Create an idempotent interest for a property or unit.

        Returns the interest and a boolean indicating whether a new row was created.
        """
        if (property_id is None) == (unit_id is None):
            raise ValueError("exactly one of property_id or unit_id is required")

        if self.session.get(Prospect, prospect_id) is None:
            raise ValueError(f"prospect_id {prospect_id} does not exist")

        if property_id is not None:
            if self.session.get(Property, property_id) is None:
                raise ValueError(f"property_id {property_id} does not exist")
            existing = self.session.scalar(
                select(ProspectInterest).where(
                    ProspectInterest.prospect_id == prospect_id,
                    ProspectInterest.property_id == property_id,
                    ProspectInterest.unit_id.is_(None),
                )
            )
        else:
            if self.session.get(Unit, unit_id) is None:
                raise ValueError(f"unit_id {unit_id} does not exist")
            existing = self.session.scalar(
                select(ProspectInterest).where(
                    ProspectInterest.prospect_id == prospect_id,
                    ProspectInterest.unit_id == unit_id,
                )
            )

        if existing is not None:
            return existing, False

        interest = ProspectInterest(
            prospect_id=prospect_id,
            property_id=property_id,
            unit_id=unit_id,
            notes=_clean_optional_text(notes),
        )
        self.session.add(interest)
        self.session.flush()
        return interest, True


def normalize_phone_number(phone_number: str) -> str:
    """Normalize US caller phone numbers to E.164-like format."""
    digits = "".join(character for character in phone_number if character.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) >= 7:
        return f"+{digits}"
    raise ValueError("phone_number must contain at least seven digits")


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
