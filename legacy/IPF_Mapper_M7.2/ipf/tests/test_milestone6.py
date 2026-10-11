import tempfile, unittest
from pathlib import Path
from ipf.app.controller import AppController

class Milestone6ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.c=AppController(Path(self.tmp.name)/'ui.db')
    def tearDown(self): self.c.close(); self.tmp.cleanup()
    def test_end_to_end_model_parameter_publish_execution(self):
        w=self.c.create_workspace('Demo'); m,r=self.c.create_model(w,'Procurement')
        pg=self.c.add_entity(r,'PROCESS_GROUP','Procurement Flow')
        a=self.c.add_entity(r,'ACTION','Prepare RFQ')
        info=self.c.add_entity(r,'INFORMATION','Technical Specification')
        self.c.add_relation(r,'CONTAINS',pg,a)
        self.c.add_relation(r,'CONTAINS',pg,info)
        self.c.add_relation(r,'INPUT',a,info)
        self.c.set_parameter(r,'APPROVAL_THRESHOLD','Approval threshold','NUMBER','500000')
        self.assertEqual(self.c.overview(r)['entities'],3)
        self.assertEqual(self.c.parameters(r)[0]['value_real'],500000.0)
        report=self.c.validate_revision(r); self.assertTrue(report.is_valid,report.issues)
        self.c.publish_revision(r)
        ctx=self.c.create_context(w,'Project A'); ex=self.c.start_execution(ctx,r)
        definition=next(x['definition_id'] for x in self.c.entities(r) if x['name']=='Prepare RFQ')
        self.c.instantiate(ex,definition)
        self.assertEqual(len(self.c.execution_instances(ex)),1)
    def test_policy_change_is_data_in_cloned_revision(self):
        w=self.c.create_workspace('Demo'); _,r1=self.c.create_model(w,'Policy Model'); self.c.set_parameter(r1,'LIMIT','Limit','NUMBER','500000'); self.c.publish_revision(r1)
        r2=self.c.clone_revision(r1,'v2'); self.c.set_parameter(r2,'LIMIT','Limit','NUMBER','750000')
        self.assertEqual(self.c.parameters(r1)[0]['value_real'],500000.0); self.assertEqual(self.c.parameters(r2)[0]['value_real'],750000.0)

if __name__=='__main__': unittest.main()
