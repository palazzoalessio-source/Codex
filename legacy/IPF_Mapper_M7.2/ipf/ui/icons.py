"""Monochrome glyphs shared by Means library and canvas; no emoji/font dependency."""
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPixmap,QPainter,QPen,QColor,QIcon,QPainterPath

def means_pixmap(kind,size=32):
    pm=QPixmap(size,size); pm.fill(Qt.transparent)
    p=QPainter(pm); p.setRenderHint(QPainter.Antialiasing); p.scale(size/32,size/32)
    p.setPen(QPen(QColor('#126777'),1.8)); p.setBrush(QColor('#e7f4f4'))
    if kind=='Mail':
        p.drawRoundedRect(QRectF(3,6,26,20),3,3); p.drawLine(3,7,16,17); p.drawLine(16,17,29,7)
    elif kind in ('Database','ERP'):
        p.drawRect(QRectF(5,7,22,18)); p.drawEllipse(QRectF(5,3,22,8)); p.drawArc(QRectF(5,13,22,8),180*16,180*16); p.drawArc(QRectF(5,21,22,8),180*16,180*16)
    elif kind=='Phone':
        path=QPainterPath(QPointF(6,4)); path.cubicTo(1,19,15,31,27,26); path.lineTo(28,20); path.lineTo(20,17); path.lineTo(17,22); path.lineTo(10,14); path.lineTo(15,11); path.lineTo(11,4); path.closeSubpath(); p.drawPath(path)
    elif kind=='Web Portal':
        p.drawEllipse(QRectF(3,3,26,26)); p.drawEllipse(QRectF(10,3,12,26)); p.drawLine(3,16,29,16); p.drawLine(6,9,26,9); p.drawLine(6,23,26,23)
    elif kind=='Teams':
        p.drawEllipse(QRectF(6,3,8,8)); p.drawEllipse(QRectF(20,6,7,7)); p.drawRoundedRect(QRectF(3,14,15,14),3,3); p.drawRoundedRect(QRectF(20,16,9,11),2,2)
    elif kind=='ERP':
        for x,y in ((3,3),(18,3),(3,18),(18,18)): p.drawRoundedRect(QRectF(x,y,11,11),2,2)
    else:
        p.drawRoundedRect(QRectF(3,6,26,20),4,4); p.drawLine(8,12,24,12); p.drawLine(8,19,19,19)
    p.end(); return pm

def means_icon(kind):return QIcon(means_pixmap(kind,48))
