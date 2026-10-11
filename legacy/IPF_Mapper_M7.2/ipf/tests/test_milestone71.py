import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from ipf.app.controller import AppController
from ipf.app.demo import DemoStore,seed_demo

class DemoFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_dir=tempfile.TemporaryDirectory(); cls.seed_path=Path(cls.seed_dir.name)/'seed.db'; c=AppController(cls.seed_path)
        try:seed_demo(c)
        finally:c.close()
    @classmethod
    def tearDownClass(cls):cls.seed_dir.cleanup()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'demo.db'
        src=sqlite3.connect(self.seed_path); dst=sqlite3.connect(self.path)
        try:src.backup(dst)
        finally:src.close(); dst.close()
        self.c=AppController(self.path); self.r=self.c.ipf_library()[0]['revision_id']; self.ex=self.c.executions_for_revision(self.r)[0]['id']; self.ids={e['stable_code']:e['identity_id'] for e in self.c.entities(self.r) if e['stable_code']}
    def tearDown(self):self.c.close(); self.tmp.cleanup()

class DemoCase(DemoFixture):
    def test_seed_idempotence_and_reopen(self):
        counts=[len(self.c.entities(self.r)),len(self.c.relations(self.r)),len(self.c.execution_instances(self.ex))]
        self.assertEqual(seed_demo(self.c),self.r); self.assertEqual(counts,[len(self.c.entities(self.r)),len(self.c.relations(self.r)),len(self.c.execution_instances(self.ex))]); self.assertEqual(self.c.rows('PRAGMA foreign_key_check'),[])
        self.assertTrue(self.c.validate_revision(self.r).is_valid)
    def test_policy_500k_to_750k_preserves_execution_snapshot(self):
        approve=self.ids['APPROVE']; state=lambda r:self.c.evaluate_states(r,self.ex)[0].by_identity(approve).requirement.value
        self.assertEqual(state(self.r),'REQUIRED')
        self.c.set_parameter(self.r,'MANAGEMENT_APPROVAL_THRESHOLD','Soglia','NUMBER',750000)
        self.assertEqual(state(self.r),'OPTIONAL')
        snapshot=self.c.row('SELECT model_revision_id FROM model_execution WHERE id=?',(self.ex,))['model_revision_id']
        self.assertEqual(state(snapshot),'REQUIRED'); self.assertEqual(self.c.parameter_values(snapshot)['MANAGEMENT_APPROVAL_THRESHOLD'],500000)
        cloned=self.c.clone_revision(self.r,'750k-copy'); self.assertEqual(self.c.parameter_values(cloned)['MANAGEMENT_APPROVAL_THRESHOLD'],750000)
    def test_technical_alignment_conditional(self):
        self.c.set_parameter(self.r,'TECHNICAL_ISSUE','Issue','BOOLEAN',False)
        state=self.c.evaluate_states(self.r,self.ex)[0].by_identity(self.ids['TA']); self.assertEqual(state.applicability.value,'NOT_APPLICABLE')
        branches=self.c.runtime_analysis(self.r,self.ex)['branches']; self.assertTrue(any(b.kind.value=='CONDITIONAL' for b in branches))
    def test_runtime_analysis_ground_truth(self):
        result=self.c.runtime_analysis(self.r,self.ex)
        pair=next(p for p in result['parallelism'] if {p.left_identity_id,p.right_identity_id}=={self.ids['A_QUOTE'],self.ids['B_QUOTE']}); self.assertTrue(pair.actual_overlap); self.assertTrue(pair.potential)
        repeat={r.identity_id:r.kind.value for r in result['repeats']}; self.assertEqual(repeat[self.ids['A_QUOTE']],'REWORK'); self.assertEqual(repeat[self.ids['ANALYZE']],'ITERATION')
        self.assertTrue(any(w.observed_wait and w.observed_wait.total_seconds()==21*3600 for w in result['waiting'])); self.assertTrue(any(w.classification.value=='UNKNOWN' for w in result['waiting']))
        self.assertEqual(result['graphs']['realized_nodes'],12); self.assertEqual(result['graphs']['realized_edges'],1)
        self.assertTrue(any(b.kind.value=='AND' for b in result['branches']))
    def test_flow_grammar_roundtrip_and_atomic_failure(self):
        before=len(self.c.entities(self.r))
        with self.assertRaises(ValueError):self.c.create_information_flow(self.r,self.ids['RDA'],self.ids['SEND'])
        self.assertEqual(len(self.c.entities(self.r)),before)
        f=self.c.create_information_flow(self.r,self.ids['SEND'],self.ids['APPROVE'],information_identity_id=self.ids['PO'],lead_time='4h')
        self.c.update_flow(self.r,f,self.ids['SEND'],self.ids['NEGOTIATE'],self.ids['PO'],None,'5h')
        flow=next(x for x in self.c.flow_projections(self.r) if x['flow_identity_id']==f); self.assertEqual(flow['lead_time'],'5h'); self.assertEqual(flow['information_id'],self.ids['PO'])
        self.c.connect_elements(self.r,self.ids['RDA'],self.ids['SEND'])
        self.assertTrue(any(x['semantic_code']=='INPUT' and x['source_identity_id']==self.ids['SEND'] and x['target_identity_id']==self.ids['RDA'] for x in self.c.relations(self.r)))
        with self.assertRaises(ValueError):self.c.connect_elements(self.r,self.ids['RDA'],self.ids['PO'])
        with self.assertRaises(ValueError):self.c.set_definition_property(self.c.entity(self.r,self.ids['SEND'])['definition_id'],'TARGET_LEAD_TIME','2h')
        with self.assertRaises(ValueError):self.c.set_definition_property(self.c.entity(self.r,f)['definition_id'],'TARGET_CYCLE_TIME','2h')
    def test_cross_workspace_link_and_instance_rejected(self):
        w=self.c.create_workspace('Other'); _,r=self.c.create_model(w,'Other'); a=self.c.add_entity(r,'ACTION','Other')
        with self.assertRaises(ValueError):self.c.add_relation(self.r,'PERFORMER',self.ids['SEND'],a)
        with self.assertRaises(Exception):self.c.instantiate(self.ex,self.c.entity(r,a)['definition_id'])
    def test_collapse_nested_projection_persisted(self):
        top=self.c.add_entity(self.r,'PROCESS_GROUP','All suppliers'); self.c.add_relation(self.r,'CONTAINS',top,self.ids['GA']); self.c.toggle_group(self.r,self.ids['GA']); self.assertEqual(self.c.hidden_elements(self.r)[self.ids['A_QUOTE']],self.ids['GA'])
        self.c.toggle_group(self.r,top); self.assertEqual(self.c.hidden_elements(self.r)[self.ids['A_QUOTE']],top)
        self.c.toggle_group(self.r,top); self.assertEqual(self.c.hidden_elements(self.r)[self.ids['A_QUOTE']],self.ids['GA'])
        with self.assertRaises(ValueError):self.c.add_relation(self.r,'CONTAINS',self.ids['GA'],top)
        self.assertTrue(self.c.layout(self.r)[self.ids['GA']]['collapsed'])
    def test_inspector_properties_performer_and_copy_isolation(self):
        action=self.ids['SEND']; props={'TARGET_CYCLE_TIME':'90 min','CRITICALITY':'BOTTLENECK','CRITICALITY_SEVERITY':'HIGH','CRITICALITY_NOTE':'Changed in inspector'}
        self.c.save_element(self.r,action,'Invia RFQ modificata','SEND-NEW','Descrizione',props,self.ids['ENG'])
        e=self.c.entity(self.r,action); self.assertEqual(e['stable_code'],'SEND-NEW'); self.assertEqual(e['properties']['TARGET_CYCLE_TIME'],'90 min'); self.assertEqual(self.c.performers(self.r)[action],self.ids['ENG'])
        snap=self.c.row('SELECT model_revision_id FROM model_execution WHERE id=?',(self.ex,))['model_revision_id']; old=self.c.entity(snap,action); self.assertEqual(old['name'],'Invia RFQ'); self.assertEqual(old['stable_code'],'SEND')
        with self.assertRaises(ValueError):self.c.set_definition_property(old['definition_id'],'TARGET_CYCLE_TIME','0h')
    def test_custom_means_default_generic(self):
        m=self.c.add_entity(self.r,'MEANS','Custom courier'); self.assertEqual(self.c.entity(self.r,m)['properties']['MEANS_ICON'],'Generic')
    def test_observations_history_latest_and_validation(self):
        instance=next(x['instance_id'] for x in self.c.execution_instances(self.ex) if x['identity_id']==self.ids['MONITOR'])
        self.c.observe(self.ex,instance,'STATUS','COMPLETED','2026-10-02T10:00:00+00:00'); self.c.observe(self.ex,instance,'STATUS','PLANNED','2026-09-01T10:00:00+00:00'); self.assertEqual(self.c.instance_values(instance)['STATUS'],'COMPLETED')
        with self.assertRaises(ValueError):self.c.observe(self.ex,instance,'ACTUAL_START','2026-10-02T10:00:00')
        self.c.observe(self.ex,instance,'ACTUAL_START','2026-10-02T10:00:00+00:00')
        with self.assertRaises(ValueError):self.c.observe(self.ex,instance,'ACTUAL_END','2026-10-01T10:00:00+00:00')
    def test_unknown_and_conflict_are_preserved(self):
        recipe={'op':'GT','left':{'kind':'property','identity_id':self.ids['SEND'],'code':'COST'},'right':{'kind':'literal','value':0}}
        self.c.save_state_rule(self.r,'Missing data',self.ids['SEND'],'REQUIREMENT',recipe,'REQUIRED','OPTIONAL'); self.assertEqual(self.c.evaluate_states(self.r)[0].by_identity(self.ids['SEND']).requirement.value,'UNKNOWN')
        fixed={'op':'EQ','left':{'kind':'literal','value':True},'right':{'kind':'literal','value':True}}
        self.c.save_state_rule(self.r,'Conflicting requirement',self.ids['APPROVE'],'REQUIREMENT',fixed,'FORBIDDEN','OPTIONAL'); self.assertEqual(self.c.evaluate_states(self.r)[0].by_identity(self.ids['APPROVE']).requirement.value,'CONFLICT')
    def test_reset_demo_does_not_touch_user_db(self):
        userpath=Path(self.tmp.name)/'ipf_mapper.db'; user=AppController(userpath); user.create_workspace('Important'); user.close(); before=hashlib.sha256(userpath.read_bytes()).digest()
        store=DemoStore(self.tmp.name); store.path=self.path; store.controller=self.c
        self.c.set_parameter(self.r,'MANAGEMENT_APPROVAL_THRESHOLD','Threshold','NUMBER',750000)
        self.c=store.reset(); self.assertEqual(self.c.parameter_values(self.c.ipf_library()[0]['revision_id'])['MANAGEMENT_APPROVAL_THRESHOLD'],500000); self.assertEqual(hashlib.sha256(userpath.read_bytes()).digest(),before); self.assertEqual(self.c.rows('PRAGMA foreign_key_check'),[])

if __name__=='__main__':unittest.main()
