from .rules import AssertionRuleDefinition,DerivationRuleDefinition
from .expressions import ValueType
from .models import ValidationIssue,ValidationReport,Severity
class RuleValidator:
    def __init__(self,expression_validator,property_types): self.ev=expression_validator; self.property_types=property_types
    def validate(self,rule):
        out=ValidationReport()
        if rule.applicability:
            t,r=self.ev.infer_type(rule.applicability); out.extend(r.issues)
            if t not in (ValueType.BOOLEAN,ValueType.ANY): out.issues.append(ValidationIssue('RULE_APPLICABILITY_NOT_BOOLEAN',Severity.ERROR,'Rule applicability must be BOOLEAN.','Rule'))
        t,r=self.ev.infer_type(rule.body); out.extend(r.issues)
        if isinstance(rule,AssertionRuleDefinition) and t not in (ValueType.BOOLEAN,ValueType.ANY): out.issues.append(ValidationIssue('ASSERTION_BODY_NOT_BOOLEAN',Severity.ERROR,'Assertion body must be BOOLEAN.','Rule'))
        if isinstance(rule,DerivationRuleDefinition):
            target=self.property_types.get(rule.target.property_definition_id)
            if target and t not in (target,ValueType.ANY) and not (target==ValueType.NUMBER and t==ValueType.INTEGER): out.issues.append(ValidationIssue('DERIVATION_TYPE_MISMATCH',Severity.ERROR,f'Derivation returns {t.value}, target requires {target.value}.','Rule'))
        return out
