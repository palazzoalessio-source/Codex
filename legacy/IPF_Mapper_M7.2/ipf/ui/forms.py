import json
from PySide6.QtCore import Qt,QSize,Signal
from PySide6.QtWidgets import *
from .icons import means_icon
from ..app.workspace import PARTICIPANTS,ICONS,STATES

LABELS={'ACTION':'Attività','INFORMATION':'Informazione','INTERNAL_FUNCTION':'Funzione','MEANS':'Mezzo','PROCESS_GROUP':'Gruppo','INFORMATION_FLOW':'Information Flow','TARGET_CYCLE_TIME':'T/C previsto','TARGET_LEAD_TIME':'Lead Time','CRITICALITY':'Criticità (tipo)','CRITICALITY_SEVERITY':'Severità','CRITICALITY_NOTE':'Nota criticità','MEANS_ICON':'Icona','COST':'Valore / costo'}

def combo(items,blank=False):
    box=QComboBox()
    if blank:box.addItem('— Non assegnato —',None)
    for label,value in items:box.addItem(label,value)
    return box

def select(box,value):
    i=box.findData(value)
    if i>=0:box.setCurrentIndex(i)

class FieldDialog(QDialog):
    def __init__(self,title,parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.resize(700,580); self.root=QVBoxLayout(self)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); content=QWidget(); self.form=QFormLayout(content); self.scroll.setWidget(content); self.root.addWidget(self.scroll,1)
        self.error=QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet('color:#b33131'); self.root.addWidget(self.error)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); self.root.addWidget(self.buttons)
    def fail(self,exc):self.error.setText(str(exc))

class ElementFields(QWidget):
    changed=Signal()
    def __init__(self,c,rid,type_code,data=None,parent=None):
        super().__init__(parent); self.c=c; self.rid=rid; self.type_code=type_code; self.data=data or {}; self.props={}; self.form=QFormLayout(self)
        self.name=QLineEdit(self.data.get('name','')); self.code=QLineEdit(self.data.get('stable_code') or ''); self.desc=QPlainTextEdit(self.data.get('description') or ''); self.desc.setMaximumHeight(80)
        self.form.addRow('Nome *',self.name); self.form.addRow('Codice',self.code); self.form.addRow('Descrizione',self.desc)
        self.performer=None
        if type_code=='ACTION':
            self.performer=combo([(e['name'],e['identity_id']) for e in c.entities(rid) if e['type_code'] in PARTICIPANTS],True); select(self.performer,c.performers(rid).get(self.data.get('identity_id'))); self.form.addRow('Performer',self.performer); self.performer.currentIndexChanged.connect(self.changed)
        for p in c.applicable_properties(type_code):
            key=p['code']
            if key=='ENTITY_CODE':continue
            value=self.data.get('properties',{}).get(key,'')
            if key=='MEANS_ICON':
                widget=QComboBox()
                for icon in ICONS:widget.addItem(means_icon(icon),icon,icon)
                select(widget,value or 'Generic'); widget.currentIndexChanged.connect(self.changed)
            elif key=='CRITICALITY_SEVERITY':
                widget=combo([(x,x) for x in ('','LOW','MEDIUM','HIGH','CRITICAL')]); select(widget,value); widget.currentIndexChanged.connect(self.changed)
            elif key=='CRITICALITY_NOTE':
                widget=QPlainTextEdit(str(value or '')); widget.setMaximumHeight(80); widget.textChanged.connect(self.changed)
            else:
                widget=QLineEdit(str(value) if value is not None else ''); widget.textChanged.connect(self.changed)
                if p['value_type']=='DURATION':widget.setPlaceholderText('es. 2h, 30 min, 1d')
            self.props[key]=widget; self.form.addRow(LABELS.get(key,p['name']),widget)
        self.name.textChanged.connect(self.changed); self.code.textChanged.connect(self.changed); self.desc.textChanged.connect(self.changed)
    def values(self):
        return {k:(w.currentData() if isinstance(w,QComboBox) else w.toPlainText() if isinstance(w,QPlainTextEdit) else w.text()) for k,w in self.props.items()}
    def save(self,iid=None):
        with self.c.atomic():
            if iid is None:iid=self.c.add_entity(self.rid,self.type_code,self.name.text(),self.code.text(),self.desc.toPlainText())
            self.c.save_element(self.rid,iid,self.name.text(),self.code.text(),self.desc.toPlainText(),self.values(),self.performer.currentData() if self.performer else None)
        return iid

class ElementDialog(FieldDialog):
    def __init__(self,c,rid,type_code,parent=None,data=None):
        super().__init__('Modifica '+LABELS.get(type_code,type_code) if data else 'Aggiungi '+LABELS.get(type_code,type_code),parent); self.fields=ElementFields(c,rid,type_code,data); self.form.addRow(self.fields); self.identity_id=None; self.data=data
        if type_code=='MEANS' and not data:
            self.library=QListWidget(); self.library.setViewMode(QListView.IconMode); self.library.setIconSize(QSize(36,36)); self.library.setMaximumHeight(130); self.library.setGridSize(QSize(85,72))
            for icon in ICONS:self.library.addItem(QListWidgetItem(means_icon(icon),icon))
            self.library.itemClicked.connect(self.pick); self.form.insertRow(0,'Libreria mezzi',self.library)
    def pick(self,item):self.fields.name.setText(item.text()); select(self.fields.props['MEANS_ICON'],item.text())
    def accept(self):
        try:self.identity_id=self.fields.save(self.data['identity_id'] if self.data else None)
        except Exception as exc:self.fail(exc); return
        super().accept()

class FlowDialog(FieldDialog):
    def __init__(self,c,rid,parent=None,flow=None):
        super().__init__('Information Flow',parent); self.c=c; self.rid=rid; self.flow=flow; es=c.entities(rid)
        endpoints=[(e['name'],e['identity_id']) for e in es if e['type_code'] in PARTICIPANTS|{'ACTION'}]
        self.src=combo(endpoints); self.dst=combo(endpoints); self.info=combo([(e['name'],e['identity_id']) for e in es if e['type_code']=='INFORMATION'],True); self.means=combo([(e['name'],e['identity_id']) for e in es if e['type_code']=='MEANS'],True); self.lt=QLineEdit(); self.lt.setPlaceholderText('es. 2h, 1d')
        for label,widget in [('Source',self.src),('Target',self.dst),('Information',self.info),('Means',self.means),('Lead Time',self.lt)]:self.form.addRow(label,widget)
        if flow:
            select(self.src,flow['source_action_id']); select(self.dst,flow['target_action_id']); select(self.info,flow['information_id']); select(self.means,flow['means_id']); self.lt.setText(flow['lead_time'] or '')
    def accept(self):
        try:
            if self.flow:self.c.update_flow(self.rid,self.flow['flow_identity_id'],self.src.currentData(),self.dst.currentData(),self.info.currentData(),self.means.currentData(),self.lt.text())
            else:self.c.create_information_flow(self.rid,self.src.currentData(),self.dst.currentData(),self.means.currentData(),lead_time=self.lt.text(),information_identity_id=self.info.currentData())
        except Exception as exc:self.fail(exc); return
        super().accept()

class ConnectDialog(FieldDialog):
    def __init__(self,c,rid,parent=None):
        super().__init__('Collega elementi',parent); self.c=c; self.rid=rid; es=[(e['name']+' · '+e['type_name'],e['identity_id']) for e in c.entities(rid)]; self.src=combo(es); self.dst=combo(es); self.semantic=QComboBox()
        for label,w in [('Da',self.src),('A',self.dst),('Relazione',self.semantic)]:self.form.addRow(label,w)
        note=QLabel('Information → Action = INPUT; Action → Information = OUTPUT. Per una transizione con mezzo e Lead Time usa Information Flow.'); note.setWordWrap(True); self.form.addRow(note)
        self.src.currentIndexChanged.connect(self.update_semantics); self.dst.currentIndexChanged.connect(self.update_semantics); self.update_semantics()
    def update_semantics(self):
        self.semantic.clear(); s,t=self.src.currentData(),self.dst.currentData()
        if s is None or t is None:return
        for sem in self.c.allowed_semantics(self.rid,s,t):
            if sem!='MEANS':self.semantic.addItem(sem,sem)
        if self.c.entity(self.rid,s)['type_code']=='INFORMATION' and self.c.entity(self.rid,t)['type_code']=='ACTION':self.semantic.addItem('INPUT','INPUT')
        endpoints=PARTICIPANTS|{'ACTION'}
        if s!=t and self.c.entity(self.rid,s)['type_code'] in endpoints and self.c.entity(self.rid,t)['type_code'] in endpoints:self.semantic.addItem('Information Flow (mezzo / LT)','FLOW')
        self.buttons.button(QDialogButtonBox.Save).setEnabled(self.semantic.count()>0)
    def accept(self):
        try:
            if self.semantic.currentData()=='FLOW':
                dialog=FlowDialog(self.c,self.rid,self); select(dialog.src,self.src.currentData()); select(dialog.dst,self.dst.currentData())
                if not dialog.exec():return
            else:self.c.connect_elements(self.rid,self.src.currentData(),self.dst.currentData(),self.semantic.currentData())
        except Exception as exc:self.fail(exc); return
        super().accept()

class ParameterDialog(FieldDialog):
    def __init__(self,c,rid,parent=None,data=None):
        super().__init__('Parametro di revisione',parent); self.c=c; self.rid=rid; data=data or {}; self.code=QLineEdit(data.get('code','')); self.name=QLineEdit(data.get('name','')); self.type=combo([(x,x) for x in ('NUMBER','BOOLEAN','TEXT','INTEGER')]); select(self.type,data.get('value_type','NUMBER')); self.value=QLineEdit(str(c.parameter_values(rid).get(data.get('code'),'')))
        self.code.setReadOnly(bool(data)); self.type.setEnabled(not bool(data))
        for label,w in [('Codice',self.code),('Nome',self.name),('Tipo',self.type),('Valore',self.value)]:self.form.addRow(label,w)
    def accept(self):
        try:self.c.set_parameter(self.rid,self.code.text(),self.name.text(),self.type.currentData(),self.value.text())
        except Exception as exc:self.fail(exc); return
        super().accept()

class RuleDialog(FieldDialog):
    def __init__(self,c,rid,parent=None,data=None):
        super().__init__('Regola di stato',parent); self.c=c; self.rid=rid; self.data=data or {}; es=c.entities(rid)
        self.name=QLineEdit(self.data.get('name','')); self.target=combo([(e['name'],e['identity_id']) for e in es]); self.purpose=combo([(x,x) for x in STATES]); self.kind=combo([('Confronta proprietà / parametri','compare'),('Prerequisito completato','completed')]); self.prerequisite=combo([(e['name'],e['identity_id']) for e in es if e['type_code']=='ACTION'])
        operands=[('Parametro · '+p['code'],{'kind':'parameter','code':p['code']}) for p in c.parameters(rid)]
        for e in es:
            for p in c.applicable_properties(e['type_code']):
                if p['code'] not in ('ENTITY_CODE','MEANS_ICON'):operands.append((e['name']+' · '+p['code'],{'kind':'property','identity_id':e['identity_id'],'code':p['code']}))
        operands.append(('Valore costante',{'kind':'literal'})); self.left=combo(operands); self.right=combo(operands); self.left_value=QLineEdit('true'); self.right_value=QLineEdit('true'); self.op=combo([(x,x) for x in ('EQ','NEQ','GTE','GT','LTE','LT')]); self.true=QComboBox(); self.false=QComboBox()
        for label,w in [('Nome',self.name),('Elemento',self.target),('Scopo',self.purpose),('Condizione',self.kind),('Prerequisito',self.prerequisite),('Sinistra',self.left),('Costante sinistra',self.left_value),('Confronto',self.op),('Destra',self.right),('Costante destra',self.right_value),('Se vero',self.true),('Se falso',self.false)]:self.form.addRow(label,w)
        self.purpose.currentIndexChanged.connect(self.states); self.states(); self.kind.currentIndexChanged.connect(self.visibility); self.left.currentIndexChanged.connect(self.visibility); self.right.currentIndexChanged.connect(self.visibility)
        if self.data:
            select(self.target,self.data['target_identity_id']); select(self.purpose,self.data['purpose']); select(self.true,self.data['true_state']); select(self.false,self.data['false_state']); recipe=json.loads(self.data['recipe'])
            if recipe.get('kind')=='completed':select(self.kind,'completed'); select(self.prerequisite,recipe['identity_id'])
            else:
                select(self.op,recipe['op'])
                for box,field,side in [(self.left,self.left_value,'left'),(self.right,self.right_value,'right')]:
                    spec=recipe[side]; select(box,{'kind':'literal'} if spec['kind']=='literal' else spec)
                    if spec['kind']=='literal':field.setText(json.dumps(spec['value']))
        self.visibility()
    def states(self):
        self.true.clear(); self.false.clear()
        for value in STATES[self.purpose.currentData()]:self.true.addItem(value,value); self.false.addItem(value,value)
        self.false.setCurrentIndex(1)
    def visibility(self):
        completed=self.kind.currentData()=='completed'; self.form.setRowVisible(self.prerequisite,completed)
        for w in (self.left,self.op,self.right):self.form.setRowVisible(w,not completed)
        self.form.setRowVisible(self.left_value,not completed and self.left.currentData().get('kind')=='literal'); self.form.setRowVisible(self.right_value,not completed and self.right.currentData().get('kind')=='literal')
    def accept(self):
        try:
            if not self.name.text().strip():raise ValueError('Nome obbligatorio.')
            def operand(box,field):
                spec=dict(box.currentData())
                if spec['kind']=='literal':
                    try:spec['value']=json.loads(field.text())
                    except ValueError:spec['value']=field.text()
                return spec
            recipe={'kind':'completed','identity_id':self.prerequisite.currentData()} if self.kind.currentData()=='completed' else {'op':self.op.currentData(),'left':operand(self.left,self.left_value),'right':operand(self.right,self.right_value)}
            self.c.save_state_rule(self.rid,self.name.text(),self.target.currentData(),self.purpose.currentData(),recipe,self.true.currentData(),self.false.currentData(),self.data.get('id'))
        except Exception as exc:self.fail(exc); return
        super().accept()
