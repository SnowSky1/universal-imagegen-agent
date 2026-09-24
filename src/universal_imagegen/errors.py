class ImageGenError(Exception):
    """Base exception for expected, user-facing failures."""


class ConfigError(ImageGenError):
    """Configuration is missing or invalid."""


class RequestError(ImageGenError):
    """A generation or edit request is invalid."""


class ProviderError(ImageGenError):
    """The configured API provider failed."""


class OutputError(ImageGenError):
    """Generated output could not be validated or written."""
