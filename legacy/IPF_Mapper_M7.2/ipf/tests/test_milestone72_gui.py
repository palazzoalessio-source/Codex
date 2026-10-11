import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from ipf.tests import test_milestone71_gui as gui
from PySide6.QtCore import QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt,QEvent

class VisualControls(gui.DemoFixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass(); cls.app=gui.QApplication.instance() or gui.QApplication([])
    def setUp(self):
        super().setUp(); self.window=gui.MainWindow(self.c); self.window.open_revision(self.r); self.window.show(); self.app.processEvents()
    def tearDown(self):
        self.window.close(); self.app.processEvents(); super().tearDown()
    def test_zoom_search_and_minimap_navigation(self):
        canvas=self.window.canvas; canvas.set_zoom(1); self.assertAlmostEqual(canvas.transform().m11(),1)
        canvas.zoom_by(1.2); self.assertAlmostEqual(canvas.transform().m11(),1.2)
        canvas.search('Prepara RDA'); self.app.processEvents(); self.assertFalse(canvas.auto_fit)
        self.assertTrue(canvas.nodes[self.ids['RDA_PREP']].isSelected())
        overview=self.window.minimap; overview.repaint(); self.app.processEvents(); self.assertFalse(overview.target.isEmpty())
        point=overview.target.center(); event=QMouseEvent(QEvent.MouseButtonPress,point,point,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier); overview.mousePressEvent(event)
        canvas.fit_workspace(); self.assertTrue(canvas.auto_fit)


    def test_reference_projection_does_not_modify_model_layout(self):
        before=self.c.layout(self.r); self.window.refresh_canvas(); self.app.processEvents(); self.assertEqual(self.c.layout(self.r),before)
        node=self.window.canvas.nodes[self.ids['A_QUOTE']]; other=self.window.canvas.nodes[self.ids['B_QUOTE']]
        self.assertEqual(node.x(),other.x()); self.assertLess(node.y(),other.y()); self.assertTrue(self.window.canvas.reference)
        node.setPos(500,260); self.app.processEvents(); self.window.refresh_canvas(); self.app.processEvents(); self.assertEqual(self.window.canvas.nodes[self.ids['A_QUOTE']].pos(),QPointF(500,260))
    def test_inspector_and_means_tiles_fit_reference_panels(self):
        from PySide6.QtWidgets import QToolButton,QTabWidget
        w=self.window;w.show_properties(self.c.entity(self.r,self.ids['ANALYZE']));self.app.processEvents();self.app.processEvents()
        fields=w.inspector.fields
        for widget in (fields.name,fields.code,fields.desc,fields.performer):
            self.assertTrue(widget.isVisible()); self.assertGreater(widget.width(),50); self.assertLessEqual(widget.geometry().right(),fields.width())
        tiles=[b for b in w.findChildren(QToolButton) if b.objectName()=='MeansTile'];self.assertEqual(len(tiles),11);self.assertTrue(all(b.height()==47 for b in tiles));self.assertEqual(len({b.y() for b in tiles}),2)
        tabs=w.inspector.findChild(QTabWidget);self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],['Generale','Avanzate','Note'])
