from PySide6.QtCore import Qt,QRectF,QTimer
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget

class Overview(QWidget):
    """Read-only scene projection; clicking navigates the main viewport."""
    def __init__(self,canvas):
        super().__init__(); self.canvas=canvas; self.setMinimumSize(170,100); self.target=QRectF(); self.source=QRectF(); self.timer=QTimer(self); self.timer.timeout.connect(self.update); self.timer.start(300)
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing); self.source=self.canvas.scene().itemsBoundingRect()
        if self.source.isEmpty():return
        scale=min(self.width()/self.source.width(),self.height()/self.source.height()); self.target=QRectF((self.width()-self.source.width()*scale)/2,(self.height()-self.source.height()*scale)/2,self.source.width()*scale,self.source.height()*scale)
        self.canvas.scene().render(painter,self.target,self.source)
        visible=self.canvas.mapToScene(self.canvas.viewport().rect()).boundingRect().intersected(self.source)
        rect=QRectF(self.target.x()+(visible.x()-self.source.x())*scale,self.target.y()+(visible.y()-self.source.y())*scale,visible.width()*scale,visible.height()*scale)
        painter.setPen(QPen(QColor('#2687F7'),1.4)); painter.setBrush(QColor(38,135,247,20)); painter.drawRect(rect)
    def mousePressEvent(self,event):
        if self.target.isEmpty() or not self.target.contains(event.position()):return
        p=event.position(); self.canvas.auto_fit=False; self.canvas.centerOn(self.source.x()+(p.x()-self.target.x())*self.source.width()/self.target.width(),self.source.y()+(p.y()-self.target.y())*self.source.height()/self.target.height()); self.update()
