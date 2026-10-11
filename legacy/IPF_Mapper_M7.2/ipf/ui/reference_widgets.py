from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPainter,QPen,QColor,QFont,QPainterPath
from .glyphs import glyph
from .icons import means_pixmap
class Legend(QWidget):
    def __init__(self):super().__init__();self.setMinimumSize(230,125)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.scale(self.width()/320,self.height()/133);p.setFont(QFont('Segoe UI',7));p.setPen(QColor('#17365B'))
        labels=[('Azione','(attività)'),('Informazione','(documento/dato)'),('Decisione',''),('Flusso sequenziale',''),('Flusso informazione',''),('Flusso condizionale','')]
        for i,(a,b) in enumerate(labels):
            y=9+i*21;p.setPen(QPen(QColor('#3585CC'),1));p.setBrush(QColor('#EAF5FF') if i==0 else QColor('#F0E4FF'))
            if i<2:p.drawRoundedRect(QRectF(4,y,35,14),2,2)
            elif i==2:p.setPen(QColor('#EAA215'));p.setBrush(Qt.NoBrush);path=QPainterPath(QPointF(21,y));path.lineTo(28,y+8);path.lineTo(21,y+16);path.lineTo(14,y+8);path.closeSubpath();p.drawPath(path)
            else:
                p.setPen(QPen(QColor('#347CBA'),1,Qt.SolidLine if i==3 else Qt.DashLine));p.drawLine(4,y+8,39,y+8);p.drawLine(39,y+8,35,y+5);p.drawLine(39,y+8,35,y+11)
            p.setPen(QColor('#17365B'));p.drawText(QPointF(53,y+9),a)
            if b:p.setFont(QFont('Segoe UI',6));p.drawText(QPointF(53,y+18),b);p.setFont(QFont('Segoe UI',7))
        for i,text in enumerate(['Performer','Mezzo di scambio','Tempo ciclo (attività)','Lead time (flusso)','Criticità','Process group']):
            y=9+i*21
            if i==0:p.drawPixmap(192,int(y),14,14,glyph('people',20,'#128795'))
            elif i==1:p.drawPixmap(192,int(y),14,14,means_pixmap('Mail',20))
            elif i==4:p.setBrush(QColor('#F43638'));p.setPen(Qt.NoPen);p.drawEllipse(QRectF(195,y+2,10,10));p.setPen(QColor('white'));p.drawText(QPointF(198,y+10),'!')
            elif i==5:p.setPen(QPen(QColor('#566E89'),1,Qt.DashLine));p.setBrush(Qt.NoBrush);p.drawRect(QRectF(190,y-2,22,16))
            else:p.setPen(QColor('#17365B'));p.drawText(QPointF(193,y+10),'T/C' if i==2 else 'LT')
            p.setPen(QColor('#17365B'));p.drawText(QPointF(222,y+10),text)
        p.end()
