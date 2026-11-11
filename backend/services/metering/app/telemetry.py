"""Permanent business-invalid MQTT samples (never retried indefinitely)."""

class InvalidTelemetry(ValueError):
    pass

class UnknownMeter(InvalidTelemetry):
    pass
