from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class RevisionStatus(str, Enum):
    DRAFT = 'DRAFT'; PUBLISHED = 'PUBLISHED'; ARCHIVED = 'ARCHIVED'

class Severity(str, Enum):
    ERROR = 'ERROR'; WARNING = 'WARNING'; INFO = 'INFO'

@dataclass(frozen=True)
class Workspace:
    id: int; uid: str; name: str; description: Optional[str] = None

@dataclass(frozen=True)
class EntityType:
    id: int; code: str; parent_type_id: Optional[int]

@dataclass(frozen=True)
class EntityIdentity:
    id: int; uid: str; workspace_id: int; entity_type_id: int; stable_code: Optional[str] = None

@dataclass(frozen=True)
class EntityDefinition:
    id: int; uid: str; identity_id: int; name: str; description: Optional[str]; origin: str

@dataclass(frozen=True)
class RelationDefinition:
    id: int; uid: str; workspace_id: int; semantic_id: int; source_identity_id: int; target_identity_id: int

@dataclass(frozen=True)
class ProcessModel:
    id: int; uid: str; workspace_id: int; name: str

@dataclass(frozen=True)
class ModelRevision:
    id: int; uid: str; process_model_id: int; parent_revision_id: Optional[int]; revision_code: str; purpose: Optional[str]; status: RevisionStatus
    @property
    def is_editable(self) -> bool: return self.status == RevisionStatus.DRAFT

@dataclass(frozen=True)
class ExecutionContext:
    id: int; uid: str; workspace_id: int; name: str

@dataclass(frozen=True)
class ModelExecution:
    id: int; uid: str; execution_context_id: int; model_revision_id: int

@dataclass(frozen=True)
class EntityInstance:
    id: int; uid: str; execution_context_id: int; entity_definition_id: int


@dataclass(frozen=True)
class RelationInstance:
    id: int; uid: str; execution_context_id: int; semantic_id: int; source_instance_id: int; target_instance_id: int; relation_definition_id: Optional[int] = None

@dataclass(frozen=True)
class ValidationIssue:
    code: str; severity: Severity; message: str; object_kind: str = ''; object_uid: Optional[str] = None

@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    @property
    def errors(self): return [i for i in self.issues if i.severity == Severity.ERROR]
    @property
    def warnings(self): return [i for i in self.issues if i.severity == Severity.WARNING]
    @property
    def is_valid(self): return not self.errors
    def extend(self, items): self.issues.extend(items)

@dataclass(frozen=True)
class ChangeImpact:
    relation_ids: tuple[int, ...] = ()
    rule_ids: tuple[int, ...] = ()
    @property
    def has_impact(self): return bool(self.relation_ids or self.rule_ids)

@dataclass(frozen=True)
class RevisionSnapshot:
    revision: ModelRevision
    model: ProcessModel
    entities: tuple[tuple[EntityIdentity, EntityDefinition], ...]
    relations: tuple[RelationDefinition, ...]
