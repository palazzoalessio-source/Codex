import unittest
from ipf.domain.active import *
from ipf.domain.expressions import EvaluationContext

def ctx(inst=None, vars=None): return EvaluationContext({}, {}, {}, vars or {}, inst or {}, {}, None)
class M4(unittest.TestCase):
 def test_defaults(self):
  s=ActiveStateResolver().resolve([1],ctx()).by_identity(1); self.assertEqual((s.applicability,s.requirement,s.enablement),(ApplicabilityStatus.APPLICABLE,RequirementStatus.OPTIONAL,EnablementStatus.ENABLED))
 def test_configurable_business_threshold_no_code_change(self):
  def rule(c): return RequirementStatus.REQUIRED if c.variables['po_amount']>=c.variables['approval_threshold'] else RequirementStatus.OPTIONAL
  r=StateRule(1,RulePurpose.REQUIREMENT,rule)
  a=ActiveStateResolver().resolve([1],ctx(vars={'po_amount':600000,'approval_threshold':500000}),[r]).by_identity(1)
  b=ActiveStateResolver().resolve([1],ctx(vars={'po_amount':600000,'approval_threshold':750000}),[r]).by_identity(1)
  self.assertEqual(a.requirement,RequirementStatus.REQUIRED); self.assertEqual(b.requirement,RequirementStatus.OPTIONAL)
 def test_not_applicable_but_realized(self):
  r=StateRule(1,RulePurpose.APPLICABILITY,lambda c:ApplicabilityStatus.NOT_APPLICABLE)
  s=ActiveStateResolver().resolve([1],ctx({1:(9,)}),[r]).by_identity(1)
  self.assertEqual((s.applicability,s.realization),(ApplicabilityStatus.NOT_APPLICABLE,RealizationStatus.REALIZED))
 def test_adhoc(self):
  s=ActiveStateResolver().resolve([],ctx({8:(99,)})).by_identity(8); self.assertEqual((s.presence,s.applicability),(ModelPresence.AD_HOC,ApplicabilityStatus.NOT_MODELED))
 def test_multiple(self): self.assertEqual(ActiveStateResolver().resolve([1],ctx({1:(1,2)})).by_identity(1).realization,RealizationStatus.MULTIPLE)
 def test_conflict(self):
  rs=[StateRule(1,RulePurpose.REQUIREMENT,lambda c:RequirementStatus.REQUIRED),StateRule(1,RulePurpose.REQUIREMENT,lambda c:RequirementStatus.FORBIDDEN)]
  self.assertEqual(ActiveStateResolver().resolve([1],ctx(),rs).by_identity(1).requirement,RequirementStatus.CONFLICT)
 def test_unknown_conservative(self):
  rs=[StateRule(1,RulePurpose.REQUIREMENT,lambda c:RequirementStatus.REQUIRED),StateRule(1,RulePurpose.REQUIREMENT,lambda c:None)]
  self.assertEqual(ActiveStateResolver().resolve([1],ctx(),rs).by_identity(1).requirement,RequirementStatus.UNKNOWN)
 def test_blocked(self):
  r=StateRule(1,RulePurpose.ENABLEMENT,lambda c:EnablementStatus.ENABLED if c.variables.get('tech_complete') else EnablementStatus.BLOCKED)
  self.assertEqual(ActiveStateResolver().resolve([1],ctx(vars={'tech_complete':False}),[r]).by_identity(1).enablement,EnablementStatus.BLOCKED)
if __name__=='__main__':unittest.main()
