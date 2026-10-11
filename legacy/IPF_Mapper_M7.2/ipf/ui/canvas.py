from __future__ import annotations
from math import sin,cos,pi
import json
from pathlib import Path
from .glyphs import glyph
from PySide6.QtCore import Qt,QPointF,QTimer,QRectF
from PySide6.QtGui import QColor,QPen,QBrush,QPainter,QPainterPath,QFont,QPolygonF
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsItem,QGraphicsRectItem,QGraphicsPathItem,QGraphicsTextItem
from .icons import means_pixmap
from ..app.workspace import PARTICIPANTS

NODE_W=135; NODE_H=50
PALETTE={'ACTION':'#E8F0FF','INFORMATION':'#F3ECFA','PROCESS_GROUP':'#E4F5EB'}

class CriticalBadge(QGraphicsRectItem):
    def __init__(self,parent,width):
        super().__init__(0,0,16,16,parent);self.setPos(width-9,-7);self.setData(1,'critical');self.setZValue(8)
    def paint(self,painter,option,widget=None):
        painter.setPen(QPen(QColor('white'),1));painter.setBrush(QColor('#F53939'));painter.drawEllipse(self.rect());painter.setPen(QColor('white'));painter.setFont(QFont('Segoe UI',9,QFont.Bold));painter.drawText(self.rect(),Qt.AlignCenter,'!')

class NodeItem(QGraphicsRectItem):
    def __init__(self,canvas,data,x,y,width=NODE_W,height=NODE_H):
        super().__init__(0,0,width,height); self.canvas=canvas; self.entity_data=data
        self.parts=[]; self.setPos(x,y); self.setFlags(QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemSendsGeometryChanges)
        self.setPen(QPen(QColor('#388BFF') if data['type_code']=='ACTION' else QColor('#A176D4'),1.2)); self.setBrush(QColor(PALETTE.get(data['type_code'],'#eef2f6'))); self.setZValue(4)
        title=QGraphicsTextItem(self); title.document().setDocumentMargin(0); title.setPlainText(canvas.display_label(data,width)); title.setTextWidth(width-16 if width>=60 else width-8); title.setPos(4,12) if width<60 else None; title.setDefaultTextColor(QColor('#17314B')); title.setFont(QFont('Segoe UI',9,QFont.Bold)); title.setPos(9 if width>=60 else 4,6 if width>=60 else 16); self.parts.append(title)
        label=data.get('stable_code') or data['type_name']
        if data['type_code']=='ACTION': label='     T/C '+str(data['properties'].get('TARGET_CYCLE_TIME','—'))
        if data['type_code']=='PROCESS_GROUP':label=('Espandi' if canvas.layouts.get(data['identity_id'],{}).get('collapsed') else 'Collassa')+' · doppio clic'
        sub=QGraphicsTextItem(label,self); sub.setDefaultTextColor(QColor('#566D83')); sub.setFont(QFont('Segoe UI',8)); sub.setPos(5,height-24); self.parts.append(sub)
        if data['type_code']=='INFORMATION':sub.hide()
        props=data.get('properties',{})
        if props.get('CRITICALITY') not in (None,'','NONE','NO','0',0):
            star=CriticalBadge(self,width);star.setToolTip(str(props.get('CRITICALITY_NOTE','')));self.parts.append(star)
        self.setToolTip(data['name']+'\n'+(data.get('description') or ''))
    def paint(self,painter,option,widget=None):
        painter.setPen(self.pen()); painter.setBrush(self.brush()); r=self.rect()
        if self.entity_data['type_code']=='INFORMATION':
            path=QPainterPath(); path.moveTo(0,0); path.lineTo(r.width()-15,0); path.lineTo(r.width(),15); path.lineTo(r.width(),r.height()); path.lineTo(0,r.height()); path.closeSubpath(); painter.drawPath(path); painter.drawLine(QPointF(r.width()-15,0),QPointF(r.width()-15,15)); painter.drawLine(QPointF(r.width()-15,15),QPointF(r.width(),15))
        else:painter.drawRoundedRect(r,4,4)
        if self.entity_data['type_code']=='ACTION':
            painter.setBrush(QColor('#173E69')); painter.setPen(Qt.NoPen); painter.drawEllipse(QRectF(10,r.height()-20,5,5)); painter.drawRoundedRect(QRectF(8,r.height()-14,9,6),2,2)
        if self.isSelected():painter.setBrush(Qt.NoBrush); painter.setPen(QPen(QColor('#125ACA'),2)); painter.drawRoundedRect(r.adjusted(-2,-2,2,2),4,4)
    def mouseDoubleClickEvent(self,event):
        if self.entity_data['type_code']=='PROCESS_GROUP':
            canvas=self.canvas; iid=self.entity_data['identity_id']; QTimer.singleShot(0,lambda:canvas.toggle_group(iid)); event.accept(); return
        super().mouseDoubleClickEvent(event)
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionHasChanged and self.scene() and not self.canvas.loading:self.canvas.node_moved(self)
        if change==QGraphicsItem.ItemSelectedHasChanged and value and not self.canvas.loading:self.canvas.select_node(self.entity_data)
        return super().itemChange(change,value)

class FlowItem(QGraphicsPathItem):
    def __init__(self,path,canvas,flow):
        super().__init__(path); self.canvas=canvas; self.flow=flow; self.setFlag(QGraphicsItem.ItemIsSelectable); self.setData(0,'edge')
    def mousePressEvent(self,event):
        self.canvas.select_node(self.canvas.c.entity(self.canvas.revision_id,self.flow['flow_identity_id'])); super().mousePressEvent(event)

class LaneItem(QGraphicsRectItem):
    def __init__(self,canvas,entity,y):
        super().__init__(0,y,172,70); self.canvas=canvas; self.entity_data=entity
        self.setPen(QPen(Qt.NoPen)); self.setBrush(QBrush(Qt.NoBrush)); self.setZValue(0); self.setToolTip('Seleziona la funzione')
    def mousePressEvent(self,event):
        self.canvas.select_node(self.entity_data); event.accept()

class IPFCanvas(QGraphicsView):
    def __init__(self,controller,parent=None,on_select=None):
        super().__init__(parent); self.c=controller; self.on_select=on_select; self.revision_id=None; self.loading=False; self.nodes={}; self.layouts={}; self.auto_fit=True; self._pan=False; self._fitting=False; self.show_means_labels=True; self.reference_preset=json.loads(Path(__file__).with_name('reference_layout.json').read_text(encoding='utf-8')); self.reference=False
        self.setScene(QGraphicsScene(self)); self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.RubberBandDrag); self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setBackgroundBrush(QColor('#FBFCFE')); self.setMinimumSize(300,200)
    def fit_workspace(self):
        if self._fitting or not self.scene().items():return
        self._fitting=True
        try:
            self.auto_fit=True; rect=self.scene().itemsBoundingRect().adjusted(-5,-5,5,5); self.scene().setSceneRect(rect); self.resetTransform(); self.fitInView(rect,Qt.KeepAspectRatio)
        finally:self._fitting=False
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.auto_fit:QTimer.singleShot(0,lambda:self.fit_workspace() if self.auto_fit else None)
    def showEvent(self,event):
        super().showEvent(event)
        if self.auto_fit:QTimer.singleShot(0,lambda:self.fit_workspace() if self.auto_fit else None)
    def set_zoom(self,value):
        self.auto_fit=False; self.resetTransform(); self.scale(max(.08,min(5,value)),max(.08,min(5,value)))
    def zoom_by(self,factor):self.set_zoom(self.transform().m11()*factor)
    def search(self,text):
        matches=[n for n in self.nodes.values() if text.strip() and text.casefold() in n.entity_data['name'].casefold()]
        self.scene().clearSelection()
        if matches:
            self.auto_fit=False; self.centerOn(matches[0]); matches[0].setSelected(True)
    def wheelEvent(self,event):
        self.auto_fit=False; scale=1.12 if event.angleDelta().y()>0 else 1/1.12
        if .08<self.transform().m11()*scale<5:self.scale(scale,scale)
    def mousePressEvent(self,event):
        if event.button()==Qt.MiddleButton:self.auto_fit=False; self._pan=True; self._last=event.position(); self.setCursor(Qt.ClosedHandCursor); event.accept(); return
        if self.dragMode()==QGraphicsView.ScrollHandDrag:self.auto_fit=False
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._pan:
            delta=event.position()-self._last; self._last=event.position(); self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-int(delta.x())); self.verticalScrollBar().setValue(self.verticalScrollBar().value()-int(delta.y())); event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MiddleButton:self._pan=False; self.unsetCursor(); event.accept(); return
        super().mouseReleaseEvent(event)
    def select_node(self,data):
        if self.on_select:self.on_select(data)
    def toggle_group(self,iid):self.c.toggle_group(self.revision_id,iid); self.refresh(self.revision_id)
    def node_moved(self,item):
        pos=item.pos(); old=self.layouts.get(item.entity_data['identity_id'],{}); self.c.save_layout(self.revision_id,item.entity_data['identity_id'],pos.x(),pos.y(),collapsed=old.get('collapsed',0)); self._redraw_edges_only()
    def display_label(self,data,width):
        if self.reference and data['type_code']=='INFORMATION' and width<45:return data.get('stable_code') or data['name']
        return data['name']
    def refresh(self,rid):
        self.revision_id=rid; self.loading=True; self.scene().clear(); self.nodes={}; self.reference_placed=set()
        if not rid:self.loading=False;return
        entities=self.c.visual_entities(rid); self.layouts=self.c.layout(rid); self.hidden=self.c.hidden_elements(rid); performers=self.c.performers(rid)
        codes={e.get('stable_code') for e in entities}; preset=self.reference_preset; self.reference=set(preset['nodes']).issubset(codes)
        functions=sorted([e for e in entities if e['type_code'] in PARTICIPANTS],key=lambda e:(self.layouts.get(e['identity_id'],{}).get('y',9999),e['name']))
        lane={}; lane_heights={}
        for i,e in enumerate(functions):
            code=e.get('stable_code'); lo=self.layouts.get(e['identity_id'],{}); y=lo.get('y',110+i*150)
            if self.reference and code in preset['lanes'] and y==preset['baseline_functions'][code]:y,h=preset['lanes'][code];lane_heights[e['identity_id']]=h
            lane[e['identity_id']]=y
        counts={}
        for e in entities:
            if e['type_code'] not in ('ACTION','INFORMATION','PROCESS_GROUP') or e['identity_id'] in self.hidden:continue
            lo=self.layouts.get(e['identity_id']); owner=performers.get(e['identity_id']); n=counts.get(owner,0); counts[owner]=n+1
            x=lo['x'] if lo else 185+(n%6)*180; y=lo['y'] if lo else lane.get(owner,110+len(functions)*150)+(n//6)*100; width,height=NODE_W,NODE_H
            view=preset['nodes'].get(e.get('stable_code')) if self.reference else None
            if view:
                width,height=view['rect'][2:];width=width or NODE_W;height=height or NODE_H
                if lo and [lo['x'],lo['y']]==view['baseline']:x,y=view['rect'][:2];self.reference_placed.add(e['identity_id'])
            node=NodeItem(self,e,x,y,width,height); self.scene().addItem(node); self.nodes[e['identity_id']]=node
        maxx=max([n.x()+n.rect().width()+12 for n in self.nodes.values()]+[1270 if self.reference else 800]); maxy=max([n.y()+n.rect().height()+12 for n in self.nodes.values()]+[517 if self.reference else 300])
        colors=('#EDF5FF','#ECF9F0','#F3EDFC','#FCF6E8','#F9ECEF','#EBF2F8')
        for idx,f in enumerate(functions):
            y=lane[f['identity_id']]; nexty=lane[functions[idx+1]['identity_id']] if idx+1<len(functions) else maxy; h=lane_heights.get(f['identity_id'],max(80,nexty-y)); top=y if self.reference else y-10
            rect=self.scene().addRect(0,top,maxx,h,QPen(QColor('#DCE5EF')),QBrush(QColor(colors[idx%6])));rect.setZValue(-3)
            divider=self.scene().addLine(155,top,155,top+h,QPen(QColor('#D9E3EF')));divider.setZValue(-2)
            text=self.scene().addText(f['name'].upper(),QFont('Segoe UI',9,QFont.Bold));text.setDefaultTextColor(QColor('#142C4C'));text.setPos(43,y+25);text.setZValue(-1)
            icon=self.scene().addPixmap(glyph('people',23,('#168CEE','#139D54','#8D43C7','#B68A14','#CF6874','#85A3C5')[idx%6]));icon.setPos(15,y+28);icon.setZValue(-1)
            anchor=LaneItem(self,f,y);self.scene().addItem(anchor);self.nodes[f['identity_id']]=anchor
        for f in functions:
            members=[n for iid,n in self.nodes.items() if performers.get(iid)==f['identity_id'] and isinstance(n,NodeItem) and n.entity_data['type_code']=='ACTION'];groups=[self.nodes[g] for g,c in self.c.containment(rid) if c in {n.entity_data['identity_id'] for n in members} and g in self.nodes];unique={g.entity_data['identity_id']:g for g in groups}
            if len(unique)==2:
                ordered=sorted(unique.values(),key=lambda n:n.y());ys=[min(self.nodes[c].y() for g,c in self.c.containment(rid) if g==group.entity_data['identity_id'] and c in self.nodes) for group in ordered]
                if len(ys)>=2:
                    middle=252 if self.reference else (ys[0]+NODE_H+ys[1])/2;self.scene().addLine(0,middle,maxx,middle,QPen(QColor('#DED2F5')))
                    for item in self.scene().items():
                        if isinstance(item,QGraphicsTextItem) and item.toPlainText()==f['name'].upper():item.hide()
                    for j,g in enumerate(ordered):
                        text=self.scene().addText(g.entity_data['name'].split('·')[0].strip().upper(),QFont('Segoe UI',9,QFont.Bold));text.setDefaultTextColor(QColor('#142C4C'));text.setPos(43,ys[j]+9);icon=self.scene().addPixmap(glyph('people',23,'#8D43C7'));icon.setPos(15,ys[j]+12)
        for gid in {g for g,c in self.c.containment(rid)}:
            group=self.nodes.get(gid);children=[self.nodes[c] for g,c in self.c.containment(rid) if g==gid and c in self.nodes]
            if group and children and not self.layouts.get(gid,{}).get('collapsed'):
                rect=children[0].sceneBoundingRect()
                for child in children[1:]:rect=rect.united(child.sceneBoundingRect())
                group.setPos(rect.left()-9,rect.top()-9);group.setRect(0,0,rect.width()+18,rect.height()+18);group.setBrush(Qt.NoBrush);group.setPen(QPen(Qt.NoPen) if self.reference else QPen(QColor('#7084A5'),1,Qt.DashLine));group.setZValue(-1)
                for part in group.parts:part.setVisible(False)
        if self.reference:
            expanded=[self.nodes[g] for g in {g for g,c in self.c.containment(rid)} if g in self.nodes and not self.layouts.get(g,{}).get('collapsed')]
            actions=[self.nodes[c] for g,c in self.c.containment(rid) if g in {n.entity_data['identity_id'] for n in expanded} and c in self.nodes and self.nodes[c].entity_data['type_code']=='ACTION']
            if actions:
                box=actions[0].sceneBoundingRect()
                for item in actions[1:]:box=box.united(item.sceneBoundingRect())
                frame=self.scene().addRect(box.adjusted(-10,-9,10,9),QPen(QColor('#7084A5'),1,Qt.DashLine),QBrush(Qt.NoBrush));frame.setZValue(-1);frame.setToolTip('Raggruppamento visivo dei rami paralleli; i gruppi del modello restano distinti.')
                label=self.scene().addText('Esecuzione in parallelo',QFont('Segoe UI',8));label.setPos(box.center().x()-75,box.bottom()+7)
            # The diamond is a view annotation from the reference, not a rule/decision entity.
            if all(code in {self.nodes[i].entity_data.get('stable_code') for i in self.reference_placed} for code in ('ANALYZE','NEGOTIATE')):
                diamond=QPainterPath(QPointF(830,101));diamond.lineTo(857,131);diamond.lineTo(830,161);diamond.lineTo(803,131);diamond.closeSubpath();item=self.scene().addPath(diamond,QPen(QColor('#409C75'),1),QBrush(QColor('#E2F5E9')));item.setZValue(3);item.setToolTip('Annotazione visiva del mockup: non è una nuova regola del modello.');text=self.scene().addText('Offerta ok?',QFont('Segoe UI',7));text.setPos(799,120);text.setZValue(4)
        self._draw_edges();self.loading=False;self.auto_fit=True;QTimer.singleShot(0,lambda:self.fit_workspace() if self.auto_fit else None)
    def _visible(self,iid):return self.nodes.get(self.hidden.get(iid,iid))
    def _draw_edges(self):
        for index,fl in enumerate(self.c.flow_projections(self.revision_id)):
            a=self._visible(fl['source_action_id']); b=self._visible(fl['target_action_id'])
            if not a or not b or a is b:continue
            ra=a.sceneBoundingRect(); rb=b.sceneBoundingRect(); start=QPointF(ra.right(),ra.center().y()); end=QPointF(rb.left(),rb.center().y()); path=QPainterPath(start)
            if abs(ra.center().x()-rb.center().x())<NODE_W:
                down=rb.center().y()>ra.center().y(); start=QPointF(ra.center().x(),ra.bottom() if down else ra.top()); end=QPointF(rb.center().x(),rb.top() if down else rb.bottom())
                low,high=sorted((start.y(),end.y()))
                obstructed=any(n is not a and n is not b and n.sceneBoundingRect().left()<start.x()<n.sceneBoundingRect().right() and n.sceneBoundingRect().top()<high and n.sceneBoundingRect().bottom()>low for n in self.nodes.values())
                if obstructed:
                    start=QPointF(ra.left(),ra.center().y()); end=QPointF(rb.left(),rb.center().y()); route=min(ra.left(),rb.left())-30
                    path=QPainterPath(QPointF(route,start.y())); path.lineTo(start); path.lineTo(route,start.y()); path.lineTo(route,end.y()); path.lineTo(end); badge=QPointF(route-10,start.y()+40 if down else end.y()+40)
                else:
                    path=QPainterPath(start); midy=(start.y()+end.y())/2; path.lineTo(start.x(),midy); path.lineTo(end.x(),midy); path.lineTo(end); badge=QPointF(start.x()+12,midy-18)
            elif end.x()>start.x()+15:
                mid=(start.x()+end.x())/2; path.lineTo(mid,start.y()); path.lineTo(mid,end.y()); path.lineTo(end); badge=QPointF(mid-10,max(ra.bottom(),rb.bottom())+6)
            else:
                top=min(ra.top(),rb.top())-35-(index%3)*18; path.lineTo(start.x()+18,start.y()); path.lineTo(start.x()+18,top); path.lineTo(end.x()-18,top); path.lineTo(end.x()-18,end.y()); path.lineTo(end); badge=QPointF((start.x()+end.x())/2,top-32)
            edge=FlowItem(path,self,fl); edge.setPen(QPen(QColor('#42728A'),1.7)); edge.setZValue(1); self.scene().addItem(edge)
            last=path.elementAt(path.elementCount()-2); dx=end.x()-last.x; dy=end.y()-last.y; norm=max(1,(dx*dx+dy*dy)**.5); ux,uy=dx/norm,dy/norm
            arrow=self.scene().addPolygon(QPolygonF([end,QPointF(end.x()-7*ux-4*uy,end.y()-7*uy+4*ux),QPointF(end.x()-7*ux+4*uy,end.y()-7*uy-4*ux)]),QPen(Qt.NoPen),QBrush(QColor('#42728A'))); arrow.setData(0,'edge'); arrow.setZValue(2)
            key=a.entity_data.get('stable_code','')+'|'+b.entity_data.get('stable_code','')
            if self.reference and fl['source_action_id'] in self.reference_placed and fl['target_action_id'] in self.reference_placed and key in self.reference_preset.get('badges',{}):badge=QPointF(*self.reference_preset['badges'][key])
            if fl['means']:
                icon=self.scene().addPixmap(means_pixmap(fl['means_icon'],26)); icon.setPos(badge); icon.setData(0,'edge'); icon.setZValue(3); icon.setToolTip(fl['means'])
                if self.show_means_labels:
                    label=self.scene().addText(fl['means'],QFont('Segoe UI',7)); label.setPos(badge.x()+28,badge.y()-7); label.setData(0,'edge'); label.setZValue(3)
            if fl['lead_time']:
                label=self.scene().addText('LT '+str(fl['lead_time']),QFont('Segoe UI',8)); label.setPos(badge.x()+29,badge.y()+10); label.setData(0,'edge'); label.setZValue(3); label.setDefaultTextColor(QColor('#32576B'))
            edge.setToolTip(f"{fl['information'] or 'Nessuna informazione'} · {fl['means'] or 'Nessun mezzo'} · LT {fl['lead_time'] or '—'}\nClic: modifica transizione")
        for rel in self.c.relations(self.revision_id):
            if rel['semantic_code'] not in ('INPUT','OUTPUT'):continue
            source,target=rel['source_identity_id'],rel['target_identity_id']
            if rel['semantic_code']=='INPUT':source,target=target,source
            a,b=self._visible(source),self._visible(target)
            if not a or not b or a is b:continue
            pa,pb=a.sceneBoundingRect().center(),b.sceneBoundingRect().center(); line=self.scene().addLine(pa.x(),pa.y(),pb.x(),pb.y(),QPen(QColor('#A090B7'),1,Qt.DashLine)); line.setZValue(0); line.setData(0,'edge'); line.setToolTip(rel['semantic_code'])
    def _redraw_edges_only(self):
        for item in list(self.scene().items()):
            if item.data(0)=='edge':self.scene().removeItem(item)
        self._draw_edges()
