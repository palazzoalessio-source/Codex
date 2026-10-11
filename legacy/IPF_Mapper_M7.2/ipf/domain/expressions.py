from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

class ValueType(str, Enum):
    BOOLEAN='BOOLEAN'; INTEGER='INTEGER'; NUMBER='NUMBER'; TEXT='TEXT'; DATE='DATE'; DATETIME='DATETIME'; DURATION='DURATION'; ENUM='ENUM'; SET='SET'; ANY='ANY'; UNKNOWN='UNKNOWN'
class TruthValue(str, Enum):
    TRUE='TRUE'; FALSE='FALSE'; UNKNOWN='UNKNOWN'
    @staticmethod
    def from_value(v):
        if isinstance(v, TruthValue): return v
        if v is True: return TruthValue.TRUE
        if v is False: return TruthValue.FALSE
        return TruthValue.UNKNOWN
class ReferenceKind(str, Enum): ENTITY='ENTITY'; PROPERTY='PROPERTY'; VARIABLE='VARIABLE'; CONTEXT='CONTEXT'
class ReferenceScope(str, Enum): DEFINITION='DEFINITION'; INSTANCE='INSTANCE'; CONTEXT='CONTEXT'

@dataclass(frozen=True)
class TypedValue:
    type: ValueType
    value: Any
@dataclass(frozen=True)
class LiteralNode:
    value: TypedValue
@dataclass(frozen=True)
class ReferenceNode:
    kind: ReferenceKind
    scope: ReferenceScope
    entity_identity_id: int|None=None
    property_definition_id: int|None=None
    variable_name: str|None=None
@dataclass(frozen=True)
class OperationNode:
    operation_code: str
    children: tuple['ExpressionNode', ...]=()
ExpressionNode = LiteralNode|ReferenceNode|OperationNode
@dataclass(frozen=True)
class Expression:
    id: int|None
    uid: str
    root: ExpressionNode
@dataclass(frozen=True)
class EvaluationContext:
    definition_properties: dict[tuple[int,int], Any]
    instance_properties: dict[tuple[int,int], Any]
    context_values: dict[str, Any]
    variables: dict[str, Any]
    instances_by_identity: dict[int, tuple[int,...]]
    current_instance_by_identity: dict[int,int]
    now: Any=None
    graph: Any=None
