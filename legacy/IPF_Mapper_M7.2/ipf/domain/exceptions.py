class DomainError(Exception): pass
class ValidationError(DomainError): pass
class InvariantViolation(DomainError): pass
class NotFoundError(DomainError): pass
class ConflictError(DomainError): pass
class ImmutableObjectError(DomainError): pass
class WorkspaceMismatchError(DomainError): pass
class InvalidStateTransitionError(DomainError): pass
