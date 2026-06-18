"""Per-call state for leasing agent tools."""

from dataclasses import dataclass


@dataclass
class ResolvedTarget:
    """Current resolved property or unit candidate for safe capture."""

    target_type: str
    target_id: int
    label: str
    confidence: float
    ambiguous: bool = False
    ambiguity_resolved: bool = False


@dataclass
class CallState:
    """Small call-scoped state needed by the agent tool layer."""

    caller_phone_number: str | None = None
    caller_name: str | None = None
    caller_email: str | None = None
    current_target: ResolvedTarget | None = None
    confirmed_interest: bool = False

    def set_caller_identity(
        self,
        *,
        name: str | None = None,
        email: str | None = None,
    ) -> None:
        """Store caller identity values when the caller provides them."""
        clean_name = _clean_optional_text(name)
        clean_email = _clean_optional_text(email)
        if clean_name is not None:
            self.caller_name = clean_name
        if clean_email is not None:
            self.caller_email = clean_email

    def set_target(self, target: ResolvedTarget | None) -> None:
        """Store the latest resolved target and reset confirmation if it changes."""
        if self.current_target != target:
            self.confirmed_interest = False
        self.current_target = target


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
