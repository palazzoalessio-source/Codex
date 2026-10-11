import tempfile,unittest
from pathlib import Path
from ipf.app.controller import AppController
class M7(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.c=AppController(Path(self.t.name)/'m.db'); self.w=self.c.create_workspace('W'); self.m,self.r=self.c.create_model(self.w,'Procurement')
 def tearDown(self): self.c.close(); self.t.cleanup()
 def test_visual_schema_and_layout(self):
  a=self.c.add_entity(self.r,'ACTION','A'); self.c.save_layout(self.r,a,321,222); self.assertEqual(self.c.layout(self.r)[a]['x'],321)
 def test_criticality_native_property(self):
  a=self.c.add_entity(self.r,'ACTION','A'); d=self.c.entities(self.r)[0]['definition_id']; self.c.set_definition_property(d,'CRITICALITY','HIGH'); self.c.set_definition_property(d,'CRITICALITY_NOTE','Bottleneck'); self.assertEqual(self.c.property_value(d,'CRITICALITY'),'HIGH'); self.assertEqual(self.c.property_value(d,'CRITICALITY_NOTE'),'Bottleneck')
 def test_information_flow_action_endpoints(self):
  fn=self.c.add_entity(self.r,'INTERNAL_FUNCTION','Procurement'); mail=self.c.add_entity(self.r,'MEANS','Mail'); a=self.c.add_action(self.r,'Prepare RDA',fn); b=self.c.add_action(self.r,'Send RDA',fn); self.c.create_information_flow(self.r,a,b,mail,'RDA','3 days'); f=self.c.flow_projections(self.r); self.assertEqual(len(f),1); self.assertEqual(f[0]['means'],'Mail'); self.assertEqual(f[0]['information'],'RDA'); self.assertEqual(f[0]['lead_time'],'3 days')
 def test_library(self):
  x=self.c.ipf_library(); self.assertEqual(x[0]['name'],'Procurement'); self.assertEqual(x[0]['element_count'],0)
if __name__=='__main__':unittest.main()

class M7CanvasWiringRegression(unittest.TestCase):
 def test_canvas_receives_controller_not_main_window(self):
  """Regression for AttributeError: MainWindow has no visual_entities."""
  import ast
  source=Path(__file__).parents[1]/'ui'/'main_window.py'
  tree=ast.parse(source.read_text(encoding='utf-8'))
  calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='IPFCanvas']
  self.assertEqual(len(calls),1)
  first=calls[0].args[0]
  self.assertIsInstance(first,ast.Attribute)
  self.assertEqual(first.attr,'c')

 def test_canvas_refresh_data_contract(self):
  """Every controller query used by IPFCanvas.refresh works on a real revision."""
  with tempfile.TemporaryDirectory() as td:
   c=AppController(Path(td)/'m.db')
   try:
    w=c.create_workspace('W'); _,r=c.create_model(w,'Visual smoke')
    fn=c.add_entity(r,'INTERNAL_FUNCTION','Engineering')
    mail=c.add_entity(r,'MEANS','Mail')
    a=c.add_action(r,'Prepare RDA',fn); b=c.add_action(r,'Send RDA',fn)
    c.create_information_flow(r,a,b,mail,'RDA','3 days')
    self.assertGreaterEqual(len(c.visual_entities(r)),4)
    self.assertIsInstance(c.layout(r),dict)
    self.assertIsInstance(c.performers(r),dict)
    self.assertIsInstance(c.containment(r),list)
    self.assertEqual(len(c.flow_projections(r)),1)
   finally:c.close()
