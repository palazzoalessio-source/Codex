import json
from dataclasses import asdict,is_dataclass
from enum import Enum
from datetime import datetime,timedelta
from PySide6.QtWidgets import *
from .forms import FieldDialog,ParameterDialog,RuleDialog,combo,select

def table(headers):
    t=QTableWidget(0,len(headers)); t.setHorizontalHeaderLabels(headers); t.setSelectionBehavior(QAbstractItemView.SelectRows); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.verticalHeader().hide(); t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); t.horizontalHeader().setStretchLastSection(True); return t

def populate(t,rows):
    t.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,value in enumerate(row):t.setItem(i,j,QTableWidgetItem('—' if value is None else str(value)))

def button(layout,text,fn):
    b=QPushButton(text); b.clicked.connect(fn); layout.addWidget(b); return b

class Page(QWidget):
    def __init__(self,window,title):
        super().__init__(); self.w=window; self.root=QVBoxLayout(self); h=QLabel(title); h.setObjectName('H1'); self.root.addWidget(h); self.error=QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet('color:#b33131'); self.root.addWidget(self.error)
    @property
    def c(self):return self.w.c
    @property
    def rid(self):return self.w.revision_id
    def run(self,fn):
        try:result=fn(); self.error.clear(); return result
        except Exception as exc:self.error.setText(str(exc)); return None

class RulesPage(Page):
    def __init__(self,w):
        super().__init__(w,'Rules · parametri e regole'); self.root.addWidget(QLabel('Le modifiche appartengono alla revisione aperta. Le Execution conservano il proprio snapshot.'))
        bar=QHBoxLayout(); button(bar,'+ Parametro',self.add_parameter); button(bar,'Modifica parametro',self.edit_parameter); button(bar,'+ Regola',self.add_rule); button(bar,'Modifica regola',self.edit_rule); button(bar,'Rimuovi regola',self.remove_rule); self.root.addLayout(bar)
        self.parameters=table(['Codice','Tipo','Valore']); self.rules=table(['Regola','Scopo','Elemento','Vero','Falso']); self.root.addWidget(self.parameters,1); self.root.addWidget(self.rules,2)
        self.parameters.doubleClicked.connect(self.edit_parameter); self.rules.doubleClicked.connect(self.edit_rule)
    def refresh(self):
        if not self.rid:return
        self.ps=self.c.parameters(self.rid); self.rs=self.c.configured_rules(self.rid); values=self.c.parameter_values(self.rid); names={e['identity_id']:e['name'] for e in self.c.entities(self.rid)}
        populate(self.parameters,[(p['code'],p['value_type'],values.get(p['code'])) for p in self.ps]); populate(self.rules,[(r['name'],r['purpose'],names.get(r['target_identity_id'],'Regola M2'),r['true_state'],r['false_state']) for r in self.rs])
    def add_parameter(self):
        if ParameterDialog(self.c,self.rid,self).exec():self.refresh()
    def edit_parameter(self,*_):
        i=self.parameters.currentRow()
        if i>=0 and ParameterDialog(self.c,self.rid,self,self.ps[i]).exec():self.refresh()
    def add_rule(self):
        if RuleDialog(self.c,self.rid,self).exec():self.refresh()
    def edit_rule(self,*_):
        i=self.rules.currentRow()
        if i<0:return
        if not self.rs[i]['recipe']:self.error.setText('Regola esistente M2: visualizzabile e valutabile; crea una regola di stato per usare questo editor.'); return
        if RuleDialog(self.c,self.rid,self,self.rs[i]).exec():self.refresh()
    def remove_rule(self):
        i=self.rules.currentRow()
        if i>=0:self.run(lambda:self.c.delete_rule(self.rid,self.rs[i]['id'])); self.refresh()

class ObservationDialog(FieldDialog):
    def __init__(self,c,ex,instance,parent=None):
        super().__init__('Aggiungi osservazione',parent); self.c=c; self.ex=ex; self.instance=instance
        info=c.row('SELECT t.code FROM entity_instance i JOIN entity_definition d ON d.id=i.entity_definition_id JOIN entity_identity ei ON ei.id=d.entity_identity_id JOIN entity_type t ON t.id=ei.entity_type_id WHERE i.id=?',(instance,))
        self.prop=combo([(p['name']+' · '+p['value_type'],p['code']) for p in c.applicable_properties(info['code'],'INSTANCE')]); self.value=QLineEdit(); self.value.setPlaceholderText('Timestamp: 2026-09-01T09:00:00+00:00'); self.time=QLineEdit(datetime.now().astimezone().isoformat(timespec='seconds'))
        for label,w in [('Proprietà',self.prop),('Valore',self.value),('Osservato alle',self.time)]:self.form.addRow(label,w)
        self.form.addRow(QLabel('Per il completamento usa STATUS = COMPLETED.'))
    def accept(self):
        try:self.c.observe(self.ex,self.instance,self.prop.currentData(),self.value.text(),self.time.text())
        except Exception as exc:self.fail(exc); return
        super().accept()

class ExecutionPage(Page):
    def __init__(self,w):
        super().__init__(w,'Execution · istanze e osservazioni'); bar=QHBoxLayout(); self.executions=QComboBox(); bar.addWidget(self.executions,1); button(bar,'+ Execution da snapshot',self.new_execution); self.root.addLayout(bar)
        self.snapshot=QLabel(); self.root.addWidget(self.snapshot)
        bar=QHBoxLayout(); self.elements=QComboBox(); bar.addWidget(self.elements,1); button(bar,'+ Istanza',self.instantiate); button(bar,'+ Osservazione',self.observe); button(bar,'Registra rework',self.correction); self.root.addLayout(bar)
        self.instances=table(['Istanza','Elemento','Stato','Inizio','Fine','Abilitata alle']); self.root.addWidget(self.instances,2)
        self.history=table(['Proprietà','Valore','Osservato alle','Registrato alle']); self.root.addWidget(QLabel('Storico osservazioni dell’istanza selezionata')); self.root.addWidget(self.history,1)
        self.executions.currentIndexChanged.connect(self.refresh_instances); self.instances.itemSelectionChanged.connect(self.refresh_history)
    def refresh(self):
        ex=self.executions.currentData(); self.executions.blockSignals(True); self.executions.clear()
        for e in self.c.executions_for_revision(self.rid):self.executions.addItem(f"{e['context_name']} · {e['revision_code']}",e['id'])
        select(self.executions,ex); self.executions.blockSignals(False); self.refresh_instances()
    def refresh_instances(self):
        self.elements.clear(); ex=self.executions.currentData()
        if ex is None:populate(self.instances,[]); populate(self.history,[]); self.snapshot.setText('Crea una Execution per registrare osservazioni.'); return
        r=self.c.row('SELECT model_revision_id FROM model_execution WHERE id=?',(ex,))['model_revision_id']; self.snapshot.setText(f'Snapshot immutabile: revisione {r}. Gli orari richiedono un fuso esplicito.')
        for e in self.c.entities(r):
            if e['type_code'] in ('ACTION','INFORMATION','INFORMATION_FLOW'):self.elements.addItem(e['name'],e['definition_id'])
        self.items=self.c.execution_instances(ex); rows=[]
        for i in self.items:
            p=self.c.instance_values(i['instance_id']); rows.append((i['instance_id'],i['name'],p.get('STATUS'),p.get('ACTUAL_START'),p.get('ACTUAL_END'),p.get('ENABLED_AT')))
        populate(self.instances,rows); self.refresh_history()
    def refresh_history(self):
        i=self.instances.currentRow()
        if i<0 or i>=len(getattr(self,'items',[])):populate(self.history,[]); return
        rows=self.c.rows('SELECT o.*,p.code FROM property_observation o JOIN property_definition p ON p.id=o.property_definition_id WHERE entity_instance_id=? ORDER BY o.id DESC',(self.items[i]['instance_id'],))
        populate(self.history,[(x['code'],next((x[k] for k in ('value_text','value_integer','value_real','value_boolean') if x[k] is not None),None),x['observed_at'],x['recorded_at']) for x in rows])
    def new_execution(self):
        name,ok=QInputDialog.getText(self,'Execution','Nome progetto / contesto')
        if ok and name.strip():
            ex=self.run(lambda:self.c.create_execution_snapshot(self.rid,name)); self.refresh(); select(self.executions,ex)
    def instantiate(self):
        if self.executions.currentData() and self.elements.currentData():self.run(lambda:self.c.instantiate(self.executions.currentData(),self.elements.currentData())); self.refresh_instances()
    def observe(self):
        i=self.instances.currentRow()
        if i<0:return
        if ObservationDialog(self.c,self.executions.currentData(),self.items[i]['instance_id'],self).exec():self.refresh_instances()
    def correction(self):
        if not self.executions.currentData():return
        d=FieldDialog('Evidenza esplicita di rework',self); choices=[(str(i['instance_id'])+' · '+i['name'],i['instance_id']) for i in self.items]; newer=combo(choices); older=combo(choices); d.form.addRow('Istanza correttiva',newer); d.form.addRow('Istanza corretta',older)
        if d.exec():self.run(lambda:self.c.add_correction(self.executions.currentData(),newer.currentData(),older.currentData()))

def serial(value):
    if is_dataclass(value):return asdict(value)
    if isinstance(value,Enum):return value.value
    if isinstance(value,(datetime,timedelta)):return str(value)
    return str(value)

class AnalysisPage(Page):
    def __init__(self,w):
        super().__init__(w,'Analysis · evidenze e stato del processo'); bar=QHBoxLayout(); self.executions=QComboBox(); self.mode=combo([('Scenario: revisione aperta + osservazioni','scenario'),('Storico: regole dello snapshot','snapshot')]); bar.addWidget(self.executions,1); bar.addWidget(self.mode); button(bar,'Ricalcola',self.calculate); self.root.addLayout(bar)
        self.note=QLabel(); self.note.setWordWrap(True); self.root.addWidget(self.note); self.summary=QLabel(); self.root.addWidget(self.summary)
        filters=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('Cerca elemento, es. Approva PO'); self.all_types=QCheckBox('Mostra tutti i tipi'); filters.addWidget(self.search,1); filters.addWidget(self.all_types); self.root.addLayout(filters)
        self.tabs=QTabWidget(); self.root.addWidget(self.tabs,1)
        self.states=table(['Elemento','Applicabilità','Requisito','Abilitazione','Realizzazione']); self.tabs.addTab(self.states,'Stati'); self.findings=table(['Risultato','Elementi / istanze','Evidenza']); self.tabs.addTab(self.findings,'Processo'); self.rules=table(['Regola','Esito condizione','Valore']); self.tabs.addTab(self.rules,'Valutazioni'); self.details=QPlainTextEdit(); self.details.setReadOnly(True); self.tabs.addTab(self.details,'Dettagli'); self.result=None
        self.executions.currentIndexChanged.connect(self.calculate); self.mode.currentIndexChanged.connect(self.calculate)
        self.search.textChanged.connect(self.filter_states); self.all_types.toggled.connect(self.filter_states)
    def refresh(self):
        ex=self.executions.currentData(); self.executions.blockSignals(True); self.executions.clear(); self.executions.addItem('Solo modello · nessuna Execution',None)
        for e in self.c.executions_for_revision(self.rid):self.executions.addItem(e['context_name']+' · '+e['revision_code'],e['id'])
        if ex:select(self.executions,ex)
        elif self.executions.count()>1:self.executions.setCurrentIndex(1)
        self.executions.blockSignals(False); self.calculate()
    def calculate(self):
        if not self.rid:return
        rid=self.rid; ex=self.executions.currentData()
        if ex and self.mode.currentData()=='snapshot':rid=self.c.row('SELECT model_revision_id FROM model_execution WHERE id=?',(ex,))['model_revision_id']
        self.note.setText('Scenario: parametri e proprietà della revisione aperta applicati alle osservazioni selezionate. Lo storico della Execution resta consultabile scegliendo Snapshot.' if self.mode.currentData()=='scenario' else 'Storico: regole e parametri della revisione eseguita.')
        result=self.run(lambda:self.c.runtime_analysis(rid,ex))
        if result is None:return
        self.result=result; names={e['identity_id']:e['name'] for e in self.c.entities(rid)}; name=lambda i:names.get(i,str(i))
        self.state_types={e['identity_id']:e['type_code'] for e in self.c.entities(rid)}
        self.state_order=sorted(result['active'].elements,key=lambda s:(s.requirement.value!='REQUIRED',s.realization.value!='MULTIPLE',self.state_types.get(s.identity_id)!='ACTION',name(s.identity_id)))
        populate(self.states,[(name(s.identity_id),s.applicability.value,s.requirement.value,s.enablement.value,s.realization.value) for s in self.state_order]); self.filter_states()
        rows=[]
        for x in result['dependencies']:rows.append(('Dipendenza'+(' transitiva' if x.transitive else ''),name(x.prerequisite_identity_id)+' → '+name(x.dependent_identity_id),'Regola di abilitazione'))
        for x in result['branches']:rows.append(('Branch '+x.kind.value,name(x.prerequisite_identity_id),' / '.join(name(i) for i in x.dependent_identity_ids)))
        for x in result['parallelism']:
            if x.actual_overlap:rows.append(('Parallelismo osservato',name(x.left_identity_id)+' / '+name(x.right_identity_id),'Intervalli sovrapposti'))
            elif x.potential:rows.append(('Parallelismo candidato',name(x.left_identity_id)+' / '+name(x.right_identity_id),'Ambito: attività del modello; abilitate senza dipendenza'))
        for x in result['repeats']:
            if x.kind.value!='SINGLE':rows.append((x.kind.value,name(x.identity_id),'Istanze '+', '.join(map(str,x.instance_ids))))
        for x in result['waiting']:rows.append(('Attesa '+x.classification.value,'Istanza '+str(x.instance_id),str(x.observed_wait) if x.observed_wait is not None else 'Timestamp non sufficienti'))
        for x in result['cycles']:rows.append(('Ciclo di dipendenze',' / '.join(name(i) for i in x.identity_ids),'Struttura delle regole'))
        for x in result['sequence']:rows.append(('Sequenza '+x.kind.value,f'{x.left_instance_id} / {x.right_instance_id}',str(x.gap or '—')))
        populate(self.findings,rows); populate(self.rules,[(r['name'],r['result'],r.get('value',r.get('detail'))) for r in result['evaluations']]); self.details.setPlainText(json.dumps(result,default=serial,ensure_ascii=False,indent=2))
        g=result['graphs']; self.summary.setText(f"Potenziale: {g['potential_nodes']} elementi / {g['potential_edges']} relazioni   •   Attivo: {g['active_nodes']} elementi   •   Realizzato: {g['realized_nodes']} istanze / {g['realized_edges']} relazioni osservate")

    def filter_states(self,*_):
        text=self.search.text().casefold()
        for row,state in enumerate(getattr(self,'state_order',[])):
            hidden=(not self.all_types.isChecked() and self.state_types.get(state.identity_id) not in ('ACTION','INFORMATION')) or text not in self.states.item(row,0).text().casefold()
            self.states.setRowHidden(row,hidden)
