"""Domain exceptions. Handlers map these onto HTTP-style status codes."""


class HospitalError(Exception):
    """Base class for all domain errors."""


class NotFoundError(HospitalError):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(f"{entity} '{entity_id}' not found")
        self.entity = entity
        self.entity_id = entity_id


class ValidationError(HospitalError):
    """Input failed validation or an operation is not allowed in the current state."""


class SchedulingConflictError(HospitalError):
    """A booking collides with an existing booking, shift or business rule."""


class CapacityError(HospitalError):
    """No beds/slots are available."""


class BillingError(HospitalError):
    """Invoice or payment operation not permitted."""
