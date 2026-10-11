import unittest
from datetime import datetime,timedelta,timezone
from ipf.database.connection import connect, initialize
from ipf.repositories.uow import UnitOfWork
from ipf.domain.expressions import *
from ipf.domain.expression_validation import ExpressionValidator
from ipf.domain.rules import *
from ipf.engines.expression_engine import ExpressionEngine
from ipf.engines.rule_engine import RuleEngine

def lit(t,v): return LiteralNode(TypedValue(t,v))
def expr(root): return Expression(None,'',root)
class M2(unittest.TestCase):
 def setUp(self):
  self.con=connect(); initialize(self.con); self.ee=ExpressionEngine(); self.re=RuleEngine(self.ee)
  self.ctx=EvaluationContext({}, {}, {}, {}, {}, {}, datetime(2026,10,3,tzinfo=timezone.utc))
 def test_ternary_logic(self):
  self.assertEqual(self.ee.evaluate(expr(OperationNode('AND',(lit(ValueType.BOOLEAN,False),ReferenceNode(ReferenceKind.VARIABLE,ReferenceScope.CONTEXT,variable_name='missing')))),self.ctx),TruthValue.FALSE)
  self.assertEqual(self.ee.evaluate(expr(OperationNode('OR',(lit(ValueType.BOOLEAN,True),ReferenceNode(ReferenceKind.VARIABLE,ReferenceScope.CONTEXT,variable_name='missing')))),self.ctx),TruthValue.TRUE)
  self.assertEqual(self.ee.evaluate(expr(OperationNode('AND',(lit(ValueType.BOOLEAN,True),ReferenceNode(ReferenceKind.VARIABLE,ReferenceScope.CONTEXT,variable_name='missing')))),self.ctx),TruthValue.UNKNOWN)
 def test_implication_prerequisite(self):
  # B.start => A.complete. False antecedent is compliant; true + unknown prerequisite is UNKNOWN.
  b=ReferenceNode(ReferenceKind.VARIABLE,ReferenceScope.CONTEXT,variable_name='b_started'); a=ReferenceNode(ReferenceKind.VARIABLE,ReferenceScope.CONTEXT,variable_name='a_complete')
  e=expr(OperationNode('IMPLIES',(b,a)))
  c=EvaluationContext({}, {}, {}, {'b_started':False}, {}, {}, None)
  self.assertEqual(self.ee.evaluate(e,c),TruthValue.TRUE)
  c=EvaluationContext({}, {}, {}, {'b_started':True}, {}, {}, None)
  self.assertEqual(self.ee.evaluate(e,c),TruthValue.UNKNOWN)
 def test_rule_statuses(self):
  body=expr(ReferenceNode(ReferenceKind.VARIABLE,ReferenceScope.CONTEXT,variable_name='ok'))
  r=AssertionRuleDefinition(1,'r',1,'R',body)
  for val,status in [(True,RuleEvaluationStatus.COMPLIANT),(False,RuleEvaluationStatus.VIOLATED)]:
   c=EvaluationContext({}, {}, {}, {'ok':val}, {}, {}, None); self.assertEqual(self.re.evaluate(r,c).status,status)
  self.assertEqual(self.re.evaluate(r,self.ctx).status,RuleEvaluationStatus.UNKNOWN)
 def test_not_applicable(self):
  app=expr(lit(ValueType.BOOLEAN,False)); body=expr(lit(ValueType.BOOLEAN,False)); r=AssertionRuleDefinition(1,'r',1,'R',body,app)
  self.assertEqual(self.re.evaluate(r,self.ctx).status,RuleEvaluationStatus.NOT_APPLICABLE)
 def test_derivation(self):
  body=expr(OperationNode('ADD',(lit(ValueType.NUMBER,2),lit(ValueType.NUMBER,3))))
  r=DerivationRuleDefinition(2,'r2',1,'D',PropertyTarget(1,6),body)
  ev=self.re.evaluate(r,self.ctx); self.assertEqual((ev.status,ev.value),(RuleEvaluationStatus.DERIVED,5))
 def test_expression_roundtrip(self):
  e=expr(OperationNode('GT',(lit(ValueType.NUMBER,500001),lit(ValueType.NUMBER,500000))))
  with UnitOfWork(self.con) as u:
   saved=u.expressions.insert(e); u.commit()
  got=UnitOfWork(self.con).expressions.get(saved.id)
  self.assertEqual(self.ee.evaluate(got,self.ctx),TruthValue.TRUE)
 def test_validator_arity_and_type(self):
  ops={r['code']:(r['min_args'],r['max_args']) for r in self.con.execute('select * from operation_definition')}
  v=ExpressionValidator(ops)
  bad=expr(OperationNode('NOT',(lit(ValueType.NUMBER,2),lit(ValueType.NUMBER,3))))
  report=v.validate(bad); self.assertFalse(report.is_valid); self.assertGreaterEqual(len(report.errors),2)
 def test_time_constraint(self):
  t0=datetime(2026,10,1,tzinfo=timezone.utc); t1=t0+timedelta(days=3)
  e=expr(OperationNode('GTE',(OperationNode('DURATION',(lit(ValueType.DATETIME,t0),lit(ValueType.DATETIME,t1))),lit(ValueType.DURATION,timedelta(days=2)))))
  self.assertEqual(self.ee.evaluate(e,self.ctx),TruthValue.TRUE)

 def test_temporal_roundtrip(self):
  t=datetime(2026,10,3,12,30,tzinfo=timezone.utc); d=timedelta(hours=5)
  e=expr(OperationNode('DURATION',(lit(ValueType.DATETIME,t),lit(ValueType.DATETIME,t+d))))
  with UnitOfWork(self.con) as u:
   saved=u.expressions.insert(e); u.commit()
  got=UnitOfWork(self.con).expressions.get(saved.id)
  self.assertEqual(self.ee.evaluate(got,self.ctx),d)
 def test_rule_persistence_roundtrip(self):
  with UnitOfWork(self.con) as u:
   w=u.workspaces.insert('W'); ri=u.rules.insert_identity(w.id)
   b=u.expressions.insert(expr(lit(ValueType.BOOLEAN,True)))
   rule=AssertionRuleDefinition(None,'',ri.id,'Always true',b)
   rid=u.rules.insert_definition(rule); u.commit()
  u=UnitOfWork(self.con); got=u.rules.get_definition(rid,u.expressions)
  self.assertEqual(self.re.evaluate(got,self.ctx).status,RuleEvaluationStatus.COMPLIANT)

if __name__=='__main__': unittest.main()
