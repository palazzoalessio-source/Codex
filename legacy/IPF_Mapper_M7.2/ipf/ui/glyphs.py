"""Small vector glyphs for the reference UI, independent of installed symbol fonts."""
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPixmap,QPainter,QPen,QColor,QIcon,QPainterPath

def glyph(kind,size=24,color='#17365B'):
    pm=QPixmap(size,size); pm.fill(Qt.transparent); p=QPainter(pm); p.setRenderHint(QPainter.Antialiasing); p.scale(size/24,size/24); p.setPen(QPen(QColor(color),1.5)); p.setBrush(Qt.NoBrush)
    if kind in ('people','function','group'):
        p.drawEllipse(QRectF(7,2,5,5)); p.drawRoundedRect(QRectF(5,9,9,10),2,2); p.drawEllipse(QRectF(16,5,4,4)); p.drawRoundedRect(QRectF(16,11,5,8),1,1)
    elif kind in ('document','information','letter'):
        path=QPainterPath(QPointF(5,2)); path.lineTo(14,2); path.lineTo(19,7); path.lineTo(19,22); path.lineTo(5,22); path.closeSubpath(); p.drawPath(path); p.drawLine(14,2,14,7);p.drawLine(14,7,19,7);p.drawLine(8,12,16,12);p.drawLine(8,16,16,16)
    elif kind in ('canvas','library'):
        p.drawRoundedRect(QRectF(3,3,18,18),2,2); p.drawRect(QRectF(6,6,5,5));p.drawRect(QRectF(14,14,4,4));p.drawLine(11,9,16,9);p.drawLine(16,9,16,14)
    elif kind=='search':p.drawEllipse(QRectF(3,3,12,12));p.drawLine(14,14,21,21)
    elif kind=='connect':
        p.rotate(-35);p.drawRoundedRect(QRectF(-1,8,11,6),3,3);p.drawRoundedRect(QRectF(7,8,11,6),3,3)
    elif kind=='fit':
        for x,y in ((3,3),(14,3),(3,14),(14,14)):p.drawRect(QRectF(x,y,7,7))
    elif kind in ('rules','execution','analysis'):
        p.drawRoundedRect(QRectF(4,3,16,18),3,3)
        if kind=='analysis':p.drawLine(7,17,7,12);p.drawLine(12,17,12,8);p.drawLine(17,17,17,5)
        elif kind=='execution':p.drawLine(9,7,16,12);p.drawLine(16,12,9,17);p.drawLine(9,17,9,7)
        else:p.drawLine(8,7,16,7);p.drawLine(8,12,16,12);p.drawLine(8,17,13,17)
    elif kind=='pan':p.drawLine(12,2,12,22);p.drawLine(2,12,22,12);p.drawLine(12,2,9,5);p.drawLine(12,2,15,5);p.drawLine(22,12,19,9);p.drawLine(22,12,19,15)
    elif kind=='refresh':p.drawArc(QRectF(4,4,16,16),30*16,285*16);p.drawLine(20,4,20,10);p.drawLine(20,10,14,10)
    elif kind=='cloud':
        path=QPainterPath(QPointF(6,19));path.cubicTo(-1,19,1,10,7,10);path.cubicTo(7,1,18,1,18,9);path.cubicTo(25,8,25,19,18,19);path.closeSubpath();p.drawPath(path)
    elif kind=='folder':
        path=QPainterPath(QPointF(2,5));path.lineTo(9,5);path.lineTo(12,8);path.lineTo(22,8);path.lineTo(19,20);path.lineTo(2,20);path.closeSubpath();p.drawPath(path)
    elif kind=='courier':p.drawRect(QRectF(2,5,13,12));p.drawRect(QRectF(15,10,7,7));p.drawEllipse(QRectF(4,16,5,5));p.drawEllipse(QRectF(16,16,5,5))
    elif kind=='other':
        p.drawEllipse(QRectF(6,6,12,12));p.drawEllipse(QRectF(10,10,4,4))
        for a in range(0,360,45):p.save();p.translate(12,12);p.rotate(a);p.drawLine(0,-10,0,-7);p.restore()
    elif kind=='plus':p.drawLine(12,4,12,20);p.drawLine(4,12,20,12)
    elif kind=='brand':
        p.setPen(Qt.NoPen);p.setBrush(QColor('#F1F7FF'));path=QPainterPath(QPointF(3,3));path.lineTo(20,1);path.lineTo(16,21);path.lineTo(8,23);path.closeSubpath();p.drawPath(path);p.setBrush(QColor('#419AE5'));p.drawRoundedRect(QRectF(10,7,10,8),2,2)
    p.end();return pm

def icon(kind,size=24,color='#17365B'):return QIcon(glyph(kind,size,color))
