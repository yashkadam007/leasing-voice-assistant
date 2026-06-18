"""FastAPI control-plane entrypoint."""

from datetime import datetime

from fastapi import FastAPI, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from leasing_voice_assistant.core.config import Settings, get_settings
from leasing_voice_assistant.db.models import Prospect, ProspectInterest
from leasing_voice_assistant.db.session import (
    create_session_factory,
    create_sqlite_engine,
)


class ProspectInterestVerification(BaseModel):
    """Read-only prospect interest details for reviewer verification."""

    id: int
    property_id: int | None
    property_name: str | None
    unit_id: int | None
    unit_number: str | None
    notes: str | None
    created_at: datetime


class ProspectVerification(BaseModel):
    """Read-only prospect details for reviewer verification."""

    id: int
    phone_number: str
    name: str | None
    email: str | None
    created_at: datetime
    updated_at: datetime
    interests: list[ProspectInterestVerification]


class ProspectsVerificationResponse(BaseModel):
    """Collection response for captured prospect verification."""

    count: int
    prospects: list[ProspectVerification]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application."""
    app_settings = settings or get_settings()
    engine = create_sqlite_engine(app_settings.database_url)
    session_factory = create_session_factory(engine)
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": app_settings.app_name,
            "environment": app_settings.app_env,
        }

    @app.get("/prospects", response_model=ProspectsVerificationResponse, tags=["verification"])
    def list_prospects(
        limit: int = Query(default=50, ge=1, le=200),
    ) -> ProspectsVerificationResponse:
        """Return recently updated prospects and captured interests for demo verification."""
        with session_factory() as session:
            prospects = (
                session.scalars(
                    select(Prospect)
                    .options(
                        selectinload(Prospect.interests).selectinload(ProspectInterest.property),
                        selectinload(Prospect.interests).selectinload(ProspectInterest.unit),
                    )
                    .order_by(Prospect.updated_at.desc(), Prospect.id.desc())
                    .limit(limit)
                )
                .unique()
                .all()
            )

            return ProspectsVerificationResponse(
                count=len(prospects),
                prospects=[
                    ProspectVerification(
                        id=prospect.id,
                        phone_number=prospect.phone_number,
                        name=prospect.name,
                        email=prospect.email,
                        created_at=prospect.created_at,
                        updated_at=prospect.updated_at,
                        interests=[
                            ProspectInterestVerification(
                                id=interest.id,
                                property_id=interest.property_id,
                                property_name=interest.property.name
                                if interest.property is not None
                                else None,
                                unit_id=interest.unit_id,
                                unit_number=interest.unit.unit_number
                                if interest.unit is not None
                                else None,
                                notes=interest.notes,
                                created_at=interest.created_at,
                            )
                            for interest in sorted(
                                prospect.interests,
                                key=lambda interest: interest.created_at,
                                reverse=True,
                            )
                        ],
                    )
                    for prospect in prospects
                ],
            )

    return app


app = create_app()


def run() -> None:
    """Run the API with uvicorn for console-script usage."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "leasing_voice_assistant.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "local",
    )
