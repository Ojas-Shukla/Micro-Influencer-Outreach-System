class OutreachError(RuntimeError):
    """Base error for outreach delivery operations."""


class OutreachConfigurationError(OutreachError):
    """Email delivery is not configured safely."""


class OutreachDeliveryError(OutreachError):
    """A delivery failed before Gmail accepted the message."""


class OutreachOutcomeUnknown(OutreachError):
    """The delivery request outcome is uncertain; do not retry blindly."""


class DuplicateOutreachError(OutreachError):
    """A previous delivery or unresolved attempt blocks this send."""
