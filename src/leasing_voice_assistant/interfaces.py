from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

MessageRole = Literal["system", "user", "assistant", "tool"]
UnitStatus = Literal["available", "leased"]
InterestStatus = Literal["new", "contacted"]


@dataclass(frozen=True)
class ModelMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class ModelResponse:
    text: str


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    content_type: str


@dataclass(frozen=True)
class VoiceSession:
    session_id: str
    caller_phone: str | None = None


@dataclass(frozen=True)
class PropertyRecord:
    id: str
    name: str
    address: str
    city: str


@dataclass(frozen=True)
class UnitRecord:
    id: str
    property_id: str
    label: str
    bedrooms: int
    bathrooms: float
    monthly_rent: int
    status: UnitStatus
    view: str | None = None
    parking: str | None = None
    pet_policy: str | None = None
    amenities: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProspectRecord:
    id: str
    name: str
    phone: str
    email: str | None = None


@dataclass(frozen=True)
class ProspectInterestRecord:
    id: str
    prospect_id: str
    property_id: str | None
    unit_id: str | None
    source: str
    status: InterestStatus = "new"
    notes: str | None = None


@dataclass(frozen=True)
class KnowledgeSnippet:
    source_id: str
    text: str
    score: float


class ModelProvider(Protocol):
    def generate(self, messages: Sequence[ModelMessage]) -> ModelResponse:
        """Generate a text response from structured messages."""


class SpeechToTextProvider(Protocol):
    def transcribe(self, audio: bytes, *, content_type: str) -> Transcript:
        """Convert audio bytes into a transcript."""


class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedSpeech:
        """Convert text into spoken audio bytes."""


class VoiceSessionProvider(Protocol):
    def start_session(self, session_id: str, *, caller_phone: str | None = None) -> VoiceSession:
        """Create or attach to a voice session."""

    def send_audio(self, session_id: str, audio: bytes, *, content_type: str) -> None:
        """Send assistant audio to the active session."""

    def close_session(self, session_id: str) -> None:
        """Close a voice session."""


class PropertyRepository(Protocol):
    def search_properties(self, query: str) -> Sequence[PropertyRecord]:
        """Search properties by caller-supplied text."""

    def list_units(self, property_id: str) -> Sequence[UnitRecord]:
        """List units for a property."""

    def get_unit(self, unit_id: str) -> UnitRecord | None:
        """Read one unit by ID."""


class ProspectRepository(Protocol):
    def upsert_prospect(self, *, name: str, phone: str, email: str | None = None) -> ProspectRecord:
        """Create or update a prospect by phone number."""

    def record_interest(
        self,
        *,
        prospect_id: str,
        property_id: str | None = None,
        unit_id: str | None = None,
        source: str = "voice_call",
        notes: str | None = None,
    ) -> ProspectInterestRecord:
        """Record a prospect's interest in a property or unit."""


class KnowledgeRetriever(Protocol):
    def retrieve(self, query: str, *, limit: int = 5) -> Sequence[KnowledgeSnippet]:
        """Retrieve knowledge-base snippets for a query."""
