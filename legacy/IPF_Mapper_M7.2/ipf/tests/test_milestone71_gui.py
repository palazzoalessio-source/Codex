import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from ipf.tests.test_milestone71 import DemoFixture
try:
    from PySide6.QtWidgets import QApplication,QComboBox
    from PySide6.QtGui import QFontDatabase
    from ipf.ui.main_window import MainWindow
    from ipf.ui.forms import ElementDialog,ElementFields,FlowDialog,ConnectDialog,RuleDialog,select
    QT=True
except ImportError:QT=False

@unittest.skipUnless(QT,'PySide6 non disponibile: test GUI non eseguiti')
class GuiWorkflow(DemoFixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass(); cls.app=QApplication.instance() or QApplication([])
        for name in ('segoeui.ttf','segoeuib.ttf'):
            p=Path('C:/Windows/Fonts')/name
            if p.exists():QFontDatabase.addApplicationFont(str(p))
    def setUp(self):
        super().setUp(); self.window=MainWindow(self.c); self.window.open_revision(self.r); self.window.show(); self.app.processEvents(); self.errors=[]
        import sys
        self.old_hook=sys.excepthook; sys.excepthook=lambda *args:self.errors.append(args)
    def tearDown(self):
        import sys
        self.window.close(); self.app.processEvents(); sys.excepthook=self.old_hook
        try:self.assertEqual(self.errors,[])
        finally:super().tearDown()
    def test_gui_type_specific_forms_save(self):
        f=ElementDialog(self.c,self.r,'INTERNAL_FUNCTION',self.window); self.assertIsNone(f.fields.performer); self.assertNotIn('TARGET_CYCLE_TIME',f.fields.props); f.fields.name.setText('Quality'); f.accept(); self.assertIsNotNone(f.identity_id)
        a=ElementDialog(self.c,self.r,'ACTION',self.window); a.fields.name.setText('Review'); select(a.fields.performer,f.identity_id); a.fields.props['TARGET_CYCLE_TIME'].setText('1h'); a.accept(); self.assertEqual(self.c.performers(self.r)[a.identity_id],f.identity_id)
        info=ElementFields(self.c,self.r,'INFORMATION'); self.assertIsNone(info.performer); self.assertIn('COST',info.props); self.assertNotIn('TARGET_CYCLE_TIME',info.props)
    def test_gui_inspector_edit_persist_refresh(self):
        w=self.window; iid=self.ids['SEND']; w.show_properties(self.c.entity(self.r,iid)); fields=w.inspector.fields; fields.name.setText('RFQ update'); fields.code.setText('RFQ-EDIT'); fields.desc.setPlainText('Edited'); fields.props['TARGET_CYCLE_TIME'].setText('4h'); fields.props['CRITICALITY'].setText('WAIT'); fields.props['CRITICALITY_NOTE'].setPlainText('Await supplier'); select(fields.props['CRITICALITY_SEVERITY'],'HIGH'); select(fields.performer,self.ids['ENG']); self.assertTrue(w.inspector.dirty); self.assertTrue(w.inspector.save_data()); self.assertEqual(self.c.entity(self.r,iid)['name'],'RFQ update'); self.assertEqual(self.c.entity(self.r,iid)['stable_code'],'RFQ-EDIT'); self.assertEqual(self.c.performers(self.r)[iid],self.ids['ENG'])
    def test_gui_flow_and_connection(self):
        d=FlowDialog(self.c,self.r); select(d.src,self.ids['RDA_PREP']); select(d.dst,self.ids['MONITOR']); select(d.info,self.ids['RDA']); d.lt.setText('9h'); d.accept(); self.assertEqual(d.result(),1); self.assertTrue(any(f['lead_time']=='9h' for f in self.c.flow_projections(self.r)))
        link=ConnectDialog(self.c,self.r); select(link.src,self.ids['RDA']); select(link.dst,self.ids['MONITOR']); self.assertEqual(link.semantic.currentData(),'INPUT'); link.accept(); self.assertEqual(link.result(),1)
    def test_gui_canvas_fit_reload_resize_and_collapse(self):
        w=self.window
        for width,height in ((1600,980),(1200,760),(1920,1080)):
            w.resize(width,height); w.refresh_canvas(); self.app.processEvents(); self.app.processEvents(); rect=w.canvas.mapFromScene(w.canvas.scene().itemsBoundingRect()).boundingRect(); viewport=w.canvas.viewport().rect(); self.assertLessEqual(rect.width(),viewport.width()+2); self.assertLessEqual(rect.height(),viewport.height()+2); self.assertGreater(max(rect.width()/viewport.width(),rect.height()/viewport.height()),.92)
        node=w.canvas.nodes[self.ids['SEND']]; self.assertGreaterEqual(len(node.childItems()),2)
        w.canvas.toggle_group(self.ids['GA']); self.assertNotIn(self.ids['A_QUOTE'],w.canvas.nodes); w.canvas.toggle_group(self.ids['GA']); self.assertIn(self.ids['A_QUOTE'],w.canvas.nodes)
        w.canvas.nodes[self.ids['SEND']].setPos(500,260); self.app.processEvents(); self.assertEqual(self.c.layout(self.r)[self.ids['SEND']]['x'],500)
    def test_gui_pages_policy_analysis_and_execution(self):
        w=self.window; w.show_page(w.rules_page); self.assertGreater(w.rules_page.rules.rowCount(),0)
        self.c.set_parameter(self.r,'MANAGEMENT_APPROVAL_THRESHOLD','Threshold','NUMBER',750000)
        w.show_page(w.execution_page); self.assertEqual(w.execution_page.instances.rowCount(),12)
        w.show_page(w.analysis_page); self.assertEqual(w.analysis_page.result['active'].by_identity(self.ids['APPROVE']).requirement.value,'OPTIONAL'); select(w.analysis_page.mode,'snapshot'); self.assertEqual(w.analysis_page.result['active'].by_identity(self.ids['APPROVE']).requirement.value,'REQUIRED')
    def test_gui_rule_form_roundtrip(self):
        original=next(r for r in self.c.configured_rules(self.r) if r['target_identity_id']==self.ids['APPROVE']); d=RuleDialog(self.c,self.r,data=original); d.name.setText('Edited approval'); d.accept(); self.assertEqual(d.result(),1); self.assertEqual(self.c.evaluate_states(self.r,self.ex)[0].by_identity(self.ids['APPROVE']).requirement.value,'REQUIRED')
    def test_gui_critical_marker_and_means_library(self):
        node=self.window.canvas.nodes[self.ids['TA']]; self.assertTrue(any(c.data(1)=='critical' for c in node.childItems()))
        d=ElementDialog(self.c,self.r,'MEANS'); self.assertEqual(d.library.count(),7); d.fields.name.setText('Courier custom'); d.accept(); self.assertEqual(self.c.entity(self.r,d.identity_id)['properties']['MEANS_ICON'],'Generic')
    def test_gui_sidebar_inspector_toggle(self):
        w=self.window; old=w.canvas.viewport().width(); w.toggle_sidebar(); self.app.processEvents(); self.assertFalse(w.sidebar.isVisible()); self.assertGreater(w.canvas.viewport().width(),old); w.toggle_inspector(); self.app.processEvents(); self.assertTrue(w.inspector.isVisible()); w.toggle_inspector(); self.app.processEvents(); self.assertFalse(w.inspector.isVisible())

    def test_gui_participant_flow_and_performer_lane(self):
        from ipf.ui.canvas import FlowItem
        self.c.create_information_flow(self.r,self.ids['ENG'],self.ids['PROC'],information_identity_id=self.ids['RDA'])
        self.window.refresh_canvas(); self.app.processEvents()
        rendered=[i for i in self.window.canvas.scene().items() if isinstance(i,FlowItem)]
        self.assertEqual(len(rendered),len(self.c.flow_projections(self.r)))
        e=self.c.entity(self.r,self.ids['SEND']); self.c.save_element(self.r,e['identity_id'],e['name'],e['stable_code'],'',{},self.ids['ENG']); self.assertEqual(self.c.layout(self.r)[e['identity_id']]['y'],120)

    def test_gui_parallel_branch_does_not_cross_other_supplier(self):
        from ipf.ui.canvas import FlowItem
        from PySide6.QtGui import QPainterPath
        edge=next(i for i in self.window.canvas.scene().items() if isinstance(i,FlowItem) and i.flow['source_action_id']==self.ids['SEND'] and i.flow['target_action_id']==self.ids['B_QUOTE'])
        obstacle=QPainterPath(); obstacle.addRect(self.window.canvas.nodes[self.ids['A_QUOTE']].sceneBoundingRect().adjusted(1,1,-1,-1))
        self.assertFalse(edge.path().intersects(obstacle))

if __name__=='__main__':unittest.main()
