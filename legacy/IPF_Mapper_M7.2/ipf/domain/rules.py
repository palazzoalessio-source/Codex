from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .expressions import Expression, TruthValue

class RuleSemantic(str, Enum): ASSERTION='ASSERTION'; DERIVATION='DERIVATION'
class RuleEvaluationStatus(str, Enum): NOT_APPLICABLE='NOT_APPLICABLE'; COMPLIANT='COMPLIANT'; VIOLATED='VIOLATED'; UNKNOWN='UNKNOWN'; DERIVED='DERIVED'
@dataclass(frozen=True)
class RuleIdentity:
    id:int; uid:str; workspace_id:int; stable_code:str|None=None
@dataclass(frozen=True)
class PropertyTarget:
    entity_identity_id:int; property_definition_id:int
@dataclass(frozen=True)
class AssertionRuleDefinition:
    id:int|None; uid:str; identity_id:int; name:str; body:Expression; applicability:Expression|None=None; severity:str|None=None
@dataclass(frozen=True)
class DerivationRuleDefinition:
    id:int|None; uid:str; identity_id:int; name:str; target:PropertyTarget; body:Expression; applicability:Expression|None=None; severity:str|None=None
RuleDefinition=AssertionRuleDefinition|DerivationRuleDefinition
@dataclass(frozen=True)
class RuleEvaluation:
    rule_definition_id:int|None; status:RuleEvaluationStatus; value:object=None
