import unittest
from datetime import datetime,timedelta,timezone
from ipf.engines.analysis_engine import AnalysisEngine
from ipf.domain.process_analysis import *
from ipf.domain.active import *
from ipf.domain.expressions import EvaluationContext

T=lambda h: datetime(2026,1,1,h,tzinfo=timezone.utc)
def ctx(inst=None): return EvaluationContext({}, {}, {}, {}, inst or {}, {}, None)
def projection(states): return ActiveProjection(None,tuple(states))
def state(i,app=ApplicabilityStatus.APPLICABLE,req=RequirementStatus.REQUIRED,en=EnablementStatus.ENABLED):
 return ElementState(i,ModelPresence.MODELED,app,req,en,RealizationStatus.NOT_REALIZED)

class M5(unittest.TestCase):
 def setUp(self): self.e=AnalysisEngine()
 def test_direct_and_transitive_dependency(self):
  ds=self.e.dependencies([DependencyConstraint(1,2,10),DependencyConstraint(2,3,11)])
  self.assertTrue(any(x.prerequisite_identity_id==1 and x.dependent_identity_id==3 and x.transitive for x in ds))
 def test_observed_sequence_is_not_dependency(self):
  r=self.e.sequence(InstanceInterval(1,10,T(8),T(9)),InstanceInterval(2,20,T(10),T(11)))
  self.assertEqual(r.kind,SequenceKind.BEFORE); self.assertEqual(r.gap,timedelta(hours=1))
  self.assertEqual(self.e.dependencies([]),())
 def test_actual_overlap(self):
  r=self.e.sequence(InstanceInterval(1,10,T(8),T(10)),InstanceInterval(2,20,T(9),T(11)))
  self.assertEqual(r.kind,SequenceKind.OVERLAP)
 def test_and_branch_requires_all_required(self):
  cs=[DependencyConstraint(1,2),DependencyConstraint(1,3)]
  b=self.e.branches(cs,projection([state(1),state(2),state(3)]))[0]
  self.assertEqual(b.kind,BranchKind.AND)
 def test_conditional_branch_from_applicability(self):
  cs=[DependencyConstraint(1,2),DependencyConstraint(1,3)]
  b=self.e.branches(cs,projection([state(1),state(2),state(3,ApplicabilityStatus.NOT_APPLICABLE,RequirementStatus.NOT_APPLICABLE,EnablementStatus.NOT_APPLICABLE)]))[0]
  self.assertEqual(b.kind,BranchKind.CONDITIONAL)
 def test_geometry_free_fanout_does_not_claim_xor_or_or(self):
  b=self.e.branches([DependencyConstraint(1,2),DependencyConstraint(1,3)])[0]
  self.assertEqual(b.kind,BranchKind.FAN_OUT)
 def test_potential_parallel_requires_scope_enablement_and_no_dependency(self):
  p=projection([state(2),state(3)])
  rs=self.e.potential_parallelism([2,3],[],p)
  self.assertEqual(len(rs),1); self.assertTrue(rs[0].potential)
  self.assertEqual(self.e.potential_parallelism([2,3],[DependencyConstraint(2,3)],p),())
 def test_actual_parallelism_from_intervals(self):
  p=projection([state(2),state(3)])
  rs=self.e.potential_parallelism([2,3],[],p,[InstanceInterval(20,2,T(8),T(10)),InstanceInterval(30,3,T(9),T(11))])
  self.assertTrue(rs[0].actual_overlap)
 def test_waiting_is_observed_not_automatically_waste(self):
  w=self.e.waiting(InstanceInterval(1,1,T(10),T(11)),T(8))
  self.assertEqual(w.observed_wait,timedelta(hours=2)); self.assertEqual(w.classification,Confidence.OBSERVED)
 def test_cycle_is_topological_only(self):
  c=self.e.cycles([DependencyConstraint(1,2),DependencyConstraint(2,3),DependencyConstraint(3,1)])
  self.assertTrue(c); self.assertEqual(c[0].identity_ids,(1,2,3))
 def test_multiple_instances_are_iteration_not_rework_without_evidence(self):
  xs=[InstanceInterval(10,1,T(8),T(9)),InstanceInterval(11,1,T(10),T(11))]
  self.assertEqual(self.e.repeats(xs)[0].kind,RepeatKind.ITERATION)
 def test_rework_requires_correction_evidence(self):
  xs=[InstanceInterval(10,1,T(8),T(9)),InstanceInterval(11,1,T(10),T(11))]
  r=self.e.repeats(xs,[CorrectionEvidence(11,10)])[0]
  self.assertEqual(r.kind,RepeatKind.REWORK)
 def test_business_agnostic(self):
  # IDs and configured constraints are data. The engine has no PO/CEO/RFQ vocabulary.
  a=self.e.dependencies([DependencyConstraint(9001,8123,77)])
  self.assertEqual((a[0].prerequisite_identity_id,a[0].dependent_identity_id),(9001,8123))
if __name__=='__main__': unittest.main()
