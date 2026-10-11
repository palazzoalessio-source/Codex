from ..domain.expressions import TruthValue
from ..domain.rules import *
class RuleEngine:
    def __init__(self, expression_engine): self.expression_engine=expression_engine
    def evaluate(self,rule,ctx):
        if rule.applicability is not None:
            a=TruthValue.from_value(self.expression_engine.evaluate(rule.applicability,ctx))
            if a==TruthValue.FALSE: return RuleEvaluation(rule.id,RuleEvaluationStatus.NOT_APPLICABLE)
            if a==TruthValue.UNKNOWN: return RuleEvaluation(rule.id,RuleEvaluationStatus.UNKNOWN)
        value=self.expression_engine.evaluate(rule.body,ctx)
        if isinstance(rule,AssertionRuleDefinition):
            t=TruthValue.from_value(value)
            status={TruthValue.TRUE:RuleEvaluationStatus.COMPLIANT,TruthValue.FALSE:RuleEvaluationStatus.VIOLATED,TruthValue.UNKNOWN:RuleEvaluationStatus.UNKNOWN}[t]
            return RuleEvaluation(rule.id,status,t)
        if value==TruthValue.UNKNOWN: return RuleEvaluation(rule.id,RuleEvaluationStatus.UNKNOWN,value)
        return RuleEvaluation(rule.id,RuleEvaluationStatus.DERIVED,value)
