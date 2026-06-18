"""Provider adapter errors."""


class ProviderConfigurationError(ValueError):
    """Raised when selected provider settings are incomplete or unsupported."""

    def __init__(self, provider: str, component: str, message: str) -> None:
        self.provider = provider
        self.component = component
        super().__init__(f"{provider} {component} provider configuration error: {message}")


class ProviderDependencyError(ImportError):
    """Raised when a configured provider SDK is not installed."""

    def __init__(self, provider: str, component: str, package: str) -> None:
        self.provider = provider
        self.component = component
        self.package = package
        super().__init__(
            f"{provider} {component} provider requires optional package '{package}' "
            "to construct a runtime client"
        )
