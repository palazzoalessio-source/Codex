from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QSize,QSignalBlocker
from PySide6.QtGui import QAction,QKeySequence
from PySide6.QtWidgets import *
from .canvas import IPFCanvas
from .forms import ElementFields,ElementDialog,FlowDialog,ConnectDialog,FieldDialog,LABELS,combo
from .pages import RulesPage,ExecutionPage,AnalysisPage,table,populate,button

class Inspector(QScrollArea):
    def __init__(self,window):
        super().__init__(); self.w=window; self.data=None; self.fields=None; self.dirty=False; self.setWidgetResizable(True); self.setObjectName('Inspector'); self.setMinimumWidth(290); self.setMaximumWidth(320); self.clear()
    def clear(self):
        self.data=None; self.fields=None; self.dirty=False; body=QWidget(); layout=QVBoxLayout(body); layout.addWidget(QLabel('PROPRIETÀ\n\nSeleziona un elemento o un flow.')); layout.addStretch(); self.setWidget(body)
    def show_data(self,data):
        if self.dirty and not self.save_data(refresh=False):return
        self.data=data; body=QWidget(); layout=QVBoxLayout(body); layout.setContentsMargins(9,8,9,8); layout.setSpacing(8); head=QLabel('Proprietà'); head.setObjectName('InspectorTitle'); layout.addWidget(head)
        self.fields=ElementFields(self.w.c,self.w.revision_id,data['type_code'],data); form=self.fields.form
        # Recompose existing widgets, keeping all original values, signals and saves.
        while form.rowCount():
            row=form.takeRow(0)
            if row.labelItem and row.labelItem.widget():row.labelItem.widget().hide()
        tabs=QTabWidget(); tabs.setObjectName('InspectorTabs'); tabs.addTab(self.fields,'Generale'); advanced=QWidget(); advanced.setLayout(QFormLayout()); notes=QWidget(); notes.setLayout(QVBoxLayout()); tabs.addTab(advanced,'Avanzate'); tabs.addTab(notes,'Note'); layout.addWidget(tabs)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow); form.setLabelAlignment(Qt.AlignLeft|Qt.AlignVCenter); form.setContentsMargins(0,8,0,0); form.setVerticalSpacing(6); form.setHorizontalSpacing(9)
        name=QLabel('Azione' if data['type_code']=='ACTION' else LABELS.get(data['type_code'],data['type_name'])); name.setObjectName('FieldSection'); form.addRow(name)
        form.addRow('Nome',self.fields.name); form.addRow('Codice',self.fields.code)
        if self.fields.performer:
            selected=self.fields.performer.currentText(); function=QLabel(selected); function.setObjectName('ReadonlyField'); form.addRow('Funzione',function); form.addRow('Performer',self.fields.performer)
        if 'TARGET_CYCLE_TIME' in self.fields.props:form.addRow('Tempo ciclo (T/C)',self.fields.props['TARGET_CYCLE_TIME'])
        self.fields.desc.setFixedHeight(61); form.addRow('Descrizione',self.fields.desc)
        for key,widget in self.fields.props.items():
            if key=='TARGET_CYCLE_TIME':continue
            if key=='CRITICALITY_SEVERITY':form.addRow('Criticità',widget)
            elif key=='CRITICALITY_NOTE':widget.setFixedHeight(58)
            else:advanced.layout().addRow(LABELS.get(key,key),widget)
        if 'CRITICALITY_NOTE' in self.fields.props:form.addRow('Nota criticità',self.fields.props['CRITICALITY_NOTE'])
        note_source=self.fields.props.get('CRITICALITY_NOTE',self.fields.desc); note_editor=QPlainTextEdit(note_source.toPlainText()); note_editor.setMaximumWidth(280); notes.layout().addWidget(QLabel('Nota criticità' if 'CRITICALITY_NOTE' in self.fields.props else 'Descrizione')); notes.layout().addWidget(note_editor)
        def sync_note(source,target):
            with QSignalBlocker(target):target.setPlainText(source.toPlainText())
        note_editor.textChanged.connect(lambda:(sync_note(note_editor,note_source),self.mark_dirty())); note_source.textChanged.connect(lambda:sync_note(note_source,note_editor)); notes.layout().addStretch()
        severity=self.fields.props.get('CRITICALITY_SEVERITY')
        if severity:
            names={'LOW':'Bassa','MEDIUM':'Media','HIGH':'Alta','CRITICAL':'Critica'}
            for i in range(severity.count()):severity.setItemText(i,names.get(severity.itemData(i),'—'))
        connections=QVBoxLayout(); label=QLabel('Collegamenti');label.setObjectName('FieldSection');connections.addWidget(label)
        iid=data['identity_id']; all_entities={e['identity_id']:e for e in self.w.c.visual_entities(self.w.revision_id)}
        for code,title in [('INPUT','Input'),('OUTPUT','Output')]:
            relations=[r for r in self.w.c.relations(self.w.revision_id) if r['semantic_code']==code and r['source_identity_id']==iid];connections.addWidget(QLabel(title+' ('+str(len(relations))+')'))
            for r in relations:
                target=all_entities.get(r['target_identity_id'],{}); item=QLabel(target.get('name',''));item.setObjectName('ConnectionRow');connections.addWidget(item)
        flows=[f for f in self.w.c.flow_projections(self.w.revision_id) if f['source_action_id']==iid and f.get('means')]; connections.addWidget(QLabel('Mezzi ('+str(len(flows))+')'))
        for f in flows:
            item=QLabel(f['means']+'    LT '+str(f.get('lead_time') or '—'));item.setObjectName('ConnectionRow');connections.addWidget(item)
        form.addRow(connections)
        for row in range(form.rowCount()):
            item=form.itemAt(row,QFormLayout.LabelRole)
            if item and item.widget():item.widget().setFixedWidth(90); item.widget().setWordWrap(True)
        for widget in (self.fields.name,self.fields.code,self.fields.desc,self.fields.performer,*self.fields.props.values()):
            if widget:widget.setMinimumWidth(0); widget.setMaximumWidth(188);widget.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.fields.setMinimumWidth(0); self.fields.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); tabs.setMinimumWidth(0);tabs.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); self.status=QLabel('Salvato'); self.status.setObjectName('SaveStatus'); layout.addWidget(self.status); self.fields.changed.connect(self.mark_dirty); self.dirty=False; self.save=QPushButton('Salva modifiche'); self.save.clicked.connect(self.save_data); layout.addWidget(self.save)
        if data['type_code']=='INFORMATION_FLOW':button(layout,'Modifica endpoint, information, means',lambda:self.w.edit_flow(data['identity_id']))
        if data['type_code']=='PROCESS_GROUP':button(layout,'Espandi / collassa',lambda:self.w.canvas.toggle_group(data['identity_id']))
        layout.addStretch(); self.setWidget(body)
    def mark_dirty(self):self.dirty=True; self.status.setText('Modifiche non salvate')
    def save_data(self,*_,refresh=True):
        if not self.data or not self.fields:return True
        try:self.fields.save(self.data['identity_id']); self.dirty=False; self.status.setText('Salvato')
        except Exception as exc:self.status.setText(str(exc)); return False
        if refresh:self.w.refresh_canvas()
        return True

class MainWindow(QMainWindow):
    def __init__(self,controller,demo_store=None):
        super().__init__(); self.user_controller=controller; self.c=controller; self.demo_store=demo_store; self.revision_id=None; self.workspace_id=None; self.model_id=None
        self.setWindowTitle('IPF Mapper · M7.2'); self.resize(1760,832); self.setMinimumSize(1050,680); self._build(); self.setStyleSheet(Path(__file__).with_name('style.qss').read_text(encoding='utf-8'))
        if demo_store:
            self.c=demo_store.controller or demo_store.open(); self.open_revision(self.c.ipf_library()[0]['revision_id']); self.inspector.show(); es=self.c.visual_entities(self.revision_id); initial=next((e for e in es if e.get('stable_code')=='ANALYZE'),None)
            if initial:self.show_properties(initial)
        else:self.show_library()
    def _build(self):
        from .glyphs import icon
        root=QWidget(); self.setCentralWidget(root); outer=QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        self.sidebar=QFrame(); self.sidebar.setObjectName('Sidebar'); self.sidebar.setFixedWidth(142); nav=QVBoxLayout(self.sidebar); nav.setContentsMargins(6,10,6,10); nav.setSpacing(5)
        brand=QHBoxLayout(); logo=QLabel(); logo.setPixmap(icon('brand',28).pixmap(28,28)); brand.addWidget(logo); label=QLabel('IPF Mapper'); label.setObjectName('SidebarBrand'); brand.addWidget(label); brand.addStretch(); nav.addLayout(brand); nav.addSpacing(14)
        self.nav_buttons={}
        for label,kind,fn in [('Libreria IPF','library',self.show_library),('Canvas','canvas',self.show_canvas),('Rules','rules',lambda:self.show_page(self.rules_page)),('Execution','execution',lambda:self.show_page(self.execution_page)),('Analysis','analysis',lambda:self.show_page(self.analysis_page))]:
            b=QPushButton(label); b.setIcon(icon(kind,18,'#EAF3FF')); b.setObjectName('NavButton'); b.setCheckable(True); b.setAutoExclusive(True); b.clicked.connect(fn); nav.addWidget(b); self.nav_buttons[label]=b
        nav.addStretch(); self.reset_button=button(nav,'Reset Demo',self.reset_demo); self.reset_button.setObjectName('ResetButton'); outer.addWidget(self.sidebar)
        content=QWidget(); col=QVBoxLayout(content); col.setContentsMargins(0,0,0,0); col.setSpacing(0); outer.addWidget(content,1)
        top=QFrame(); top.setObjectName('Breadcrumb'); tl=QHBoxLayout(top); tl.setContentsMargins(12,3,12,3); self.ipf_title=QLabel('Libreria'); tl.addWidget(self.ipf_title,1); self.sidebar_toggle=QToolButton(); self.sidebar_toggle.setIcon(icon('library',16)); self.sidebar_toggle.setToolTip('Menu'); self.sidebar_toggle.clicked.connect(self.toggle_sidebar); tl.addWidget(self.sidebar_toggle); self.inspector_toggle=QToolButton(); self.inspector_toggle.setIcon(icon('document',16)); self.inspector_toggle.setToolTip('Proprietà'); self.inspector_toggle.clicked.connect(self.toggle_inspector); tl.addWidget(self.inspector_toggle); col.addWidget(top)
        self.stack=QStackedWidget(); col.addWidget(self.stack,1)
        self.library=QWidget(); lib=QVBoxLayout(self.library); header=QHBoxLayout(); label=QLabel('Libreria IPF'); label.setObjectName('H1'); header.addWidget(label,1); button(header,'+ Nuovo IPF',self.new_ipf); button(header,'Apri selezionato',self.open_selected); lib.addLayout(header); lib.addWidget(QLabel('Demo sintetico e IPF utente sono conservati in database separati.'))
        self.lib_table=table(['Origine','IPF','Revisione','Stato']); self.lib_table.doubleClicked.connect(self.open_selected); lib.addWidget(self.lib_table); self.stack.addWidget(self.library)
        self.workspace=QWidget(); space=QVBoxLayout(self.workspace); space.setContentsMargins(6,0,6,6); space.setSpacing(4)
        bar=QFrame(); bar.setObjectName('Toolbar'); tools=QHBoxLayout(bar); tools.setContentsMargins(6,4,6,4); tools.setSpacing(7)
        create=QToolButton(); create.setObjectName('CreateAction'); create.setText('+  Azione'); create.setPopupMode(QToolButton.InstantPopup); menu=QMenu(create)
        for code in ('ACTION','INFORMATION','INTERNAL_FUNCTION','MEANS','PROCESS_GROUP'):
            action=menu.addAction(LABELS[code]); action.triggered.connect(lambda checked=False,t=code:self.add_element(t))
        create.setMenu(menu); tools.addWidget(create)
        def tool(text,kind,fn,tip=None):
            b=QToolButton(); b.setText(text); b.setIcon(icon(kind,18)); b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if text else Qt.ToolButtonIconOnly); b.setToolTip(tip or text); b.clicked.connect(fn); tools.addWidget(b); return b
        for title,kind,code in [('Informazione','plus','INFORMATION'),('Funzione','people','INTERNAL_FUNCTION'),('Mezzo','canvas','MEANS'),('Gruppo','group','PROCESS_GROUP')]:tool(title,kind,lambda checked=False,t=code:self.add_element(t))
        tool('Collega','connect',self.add_relation); self.flow_button=tool('','document',self.add_flow,'Information Flow'); separator=QFrame(); separator.setFrameShape(QFrame.VLine); tools.addWidget(separator); tool('Adatta','fit',lambda:self.canvas.fit_workspace())
        zoom=QFrame(); zoom.setObjectName('ZoomControls'); zl=QHBoxLayout(zoom); zl.setContentsMargins(0,0,0,0); zl.setSpacing(0)
        for text,fn in [('−',lambda:self.canvas.zoom_by(1/1.2)),('100%',lambda:self.canvas.set_zoom(1)),('+',lambda:self.canvas.zoom_by(1.2))]:
            b=QToolButton(); b.setText(text); b.clicked.connect(fn); zl.addWidget(b)
        tools.addWidget(zoom); self.pan_button=tool('','pan',self.toggle_pan,'Pan'); self.pan_button.setCheckable(True); tool('','refresh',self.refresh_canvas,'Ricarica'); tool('','rules',self.validate,'Valida modello'); tool('','document',self.clone_revision,'Copia revisione')
        self.search=QLineEdit(); self.search.setObjectName('CanvasSearch'); self.search.setPlaceholderText('Cerca nel canvas…'); self.search.addAction(icon('search',16),QLineEdit.LeadingPosition); self.search.returnPressed.connect(lambda:self.canvas.search(self.search.text())); tools.addWidget(self.search,1)
        more=QToolButton(); more.setText('+'); more.setPopupMode(QToolButton.InstantPopup); extra=QMenu(more); labels=extra.addAction('Mostra label mezzi'); labels.setCheckable(True); labels.setChecked(True); labels.toggled.connect(self.toggle_labels); extra.addAction('Seleziona elemento…',self.pick_from_dialog); more.setMenu(extra); tools.addWidget(more); self.means_labels=labels; space.addWidget(bar)
        self.split=QSplitter(); left=QWidget(); left.setObjectName('CanvasColumn'); leftcol=QVBoxLayout(left); leftcol.setContentsMargins(0,0,0,0); leftcol.setSpacing(5)
        titlebar=QFrame(); titlebar.setObjectName('CanvasHeader'); th=QHBoxLayout(titlebar); th.setContentsMargins(8,4,8,4); self.canvas_title=QLabel(); self.canvas_title.setObjectName('CanvasTitle'); th.addWidget(self.canvas_title); self.revision_badge=QLabel(); self.revision_badge.setObjectName('RevisionBadge'); th.addWidget(self.revision_badge); self.state_badge=QLabel(); self.state_badge.setObjectName('StateBadge'); th.addWidget(self.state_badge); th.addStretch(); self.saved_badge=QLabel('✓  Salvato'); self.saved_badge.setObjectName('SavedBadge'); th.addWidget(self.saved_badge); leftcol.addWidget(titlebar)
        self.canvas=IPFCanvas(self.c,on_select=self.show_properties); leftcol.addWidget(self.canvas,1); self.build_footer(leftcol); self.split.addWidget(left); self.inspector=Inspector(self); self.split.addWidget(self.inspector); self.split.setSizes([1270,310]); self.inspector.hide(); space.addWidget(self.split,1)
        self.entity_picker=QComboBox(); self.entity_picker.activated.connect(self.pick_entity); self.entity_picker.hide(); self.stack.addWidget(self.workspace)
        self.rules_page=RulesPage(self); self.execution_page=ExecutionPage(self); self.analysis_page=AnalysisPage(self)
        for page in (self.rules_page,self.execution_page,self.analysis_page):self.stack.addWidget(page)
        self.statusBar().hide()
        for sequence,fn in [('Ctrl+B',self.toggle_sidebar),('Ctrl+I',self.toggle_inspector),('Ctrl+0',lambda:self.canvas.fit_workspace()),('Ctrl+S',self.inspector.save_data),('F5',self.refresh_canvas)]:
            action=QAction(self); action.setShortcut(QKeySequence(sequence)); action.triggered.connect(fn); self.addAction(action)
    def pick_from_dialog(self):
        names=[self.entity_picker.itemText(i) for i in range(1,self.entity_picker.count())]; text,ok=QInputDialog.getItem(self,'Seleziona elemento','Elemento',names,0,False)
        if ok and text:self.entity_picker.setCurrentIndex(self.entity_picker.findText(text)); self.pick_entity()
    def toggle_pan(self):
        self.canvas.setDragMode(QGraphicsView.ScrollHandDrag if self.canvas.dragMode()!=QGraphicsView.ScrollHandDrag else QGraphicsView.RubberBandDrag)
    def build_footer(self,space):
        from .overview import Overview
        from .icons import means_icon
        from .glyphs import icon
        row=QHBoxLayout(); row.setSpacing(5); frame=QWidget(); frame.setObjectName('Footer'); frame.setLayout(row); row.setContentsMargins(0,0,0,0); frame.setFixedHeight(178)
        library=QGroupBox('Libreria elementi'); ll=QVBoxLayout(library); ll.setContentsMargins(5,6,5,4); tabs=QTabWidget(); ll.addWidget(tabs)
        for title,code in [('Funzioni','INTERNAL_FUNCTION'),('Azioni','ACTION'),('Informazioni','INFORMATION'),('Mezzi','MEANS'),('Gruppi','PROCESS_GROUP')]:
            page=QWidget(); grid=QGridLayout(page); grid.setContentsMargins(0,5,0,0); grid.setHorizontalSpacing(4); grid.setVerticalSpacing(4); tabs.addTab(page,title)
            if code=='MEANS':
                choices=[('Mail','Mail'),('ERP','ERP'),('Telefono','Phone'),('Teams','Teams'),('Portale','Web Portal'),('Lettera','letter'),('Cloud','cloud'),('Corriere','courier'),('Cartella','folder'),('Altro','other'),('Nuovo mezzo','plus')]
                for i,(label,kind) in enumerate(choices):
                    b=QToolButton(); b.setObjectName('MeansTile'); b.setText(label); b.setIcon(means_icon(kind) if kind in ('Mail','ERP','Phone','Teams','Web Portal') else icon(kind,24,'#168B98' if kind not in ('folder','courier') else '#C48218')); b.setIconSize(QSize(22,22)); b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); b.setFixedHeight(47); b.clicked.connect(lambda checked=False,k=kind,l=label:self.add_reference_means(k,l)); grid.addWidget(b,i//7,i%7)
                for i in range(7):grid.setColumnStretch(i,1)
            else:
                b=QPushButton('+ '+title); b.clicked.connect(lambda checked=False,t=code:self.add_element(t)); grid.addWidget(b,0,0)
        tabs.setCurrentIndex(3); row.addWidget(library,36)
        panel=QGroupBox('Panoramica'); pl=QVBoxLayout(panel); pl.setContentsMargins(7,8,7,6); self.minimap=Overview(self.canvas); pl.addWidget(self.minimap); row.addWidget(panel,24)
        from .reference_widgets import Legend
        legend=QGroupBox('Legenda'); vl=QVBoxLayout(legend); vl.setContentsMargins(6,6,6,6); vl.addWidget(Legend()); row.addWidget(legend,27)
        stats=QGroupBox('Statistiche'); sl=QGridLayout(stats); sl.setContentsMargins(10,10,5,8); self.stat_labels={}
        for i,(code,label) in enumerate([('ACTION','Azioni'),('INFORMATION','Informazioni'),('INTERNAL_FUNCTION','Funzioni'),('MEANS','Mezzi'),('INFORMATION_FLOW','Flussi'),('CRITICAL','Criticità')]):
            pair=QWidget(); lay=QVBoxLayout(pair); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0); number=QLabel('0'); number.setObjectName('StatNumber'); number.setProperty('tone','red' if code=='CRITICAL' else 'green' if code=='INFORMATION_FLOW' else 'blue'); caption=QLabel(label); caption.setObjectName('StatCaption'); lay.addWidget(number); lay.addWidget(caption); sl.addWidget(pair,i//2,i%2); self.stat_labels[code]=number
        row.addWidget(stats,11); space.addWidget(frame)
    def add_reference_means(self,kind,label):
        if kind=='plus':self.add_element('MEANS'); return
        from ..app.workspace import ICONS
        from .forms import select
        if not self.revision_id or not self.flush():return
        d=ElementDialog(self.c,self.revision_id,'MEANS',self); d.fields.name.setText(label); select(d.fields.props['MEANS_ICON'],kind if kind in ICONS else 'Generic')
        if d.exec():self.refresh_canvas()
    def add_means(self,icon):
        from .forms import select
        if not self.revision_id or not self.flush():return
        d=ElementDialog(self.c,self.revision_id,'MEANS',self); d.fields.name.setText(icon); select(d.fields.props['MEANS_ICON'],icon)
        if d.exec():self.refresh_canvas()
    def flush(self):return not self.inspector.dirty or self.inspector.save_data(refresh=False)
    def toggle_sidebar(self):self.sidebar.setVisible(not self.sidebar.isVisible()); QTimer.singleShot(0,self.canvas.fit_workspace)
    def toggle_inspector(self):self.inspector.setVisible(not self.inspector.isVisible()); QTimer.singleShot(0,self.canvas.fit_workspace)
    def toggle_labels(self,visible):self.canvas.show_means_labels=visible; self.refresh_canvas()
    def show_properties(self,data):
        self.inspector.show(); self.inspector.show_data(data)
        if self.canvas.auto_fit:QTimer.singleShot(0,self.canvas.fit_workspace)
    def pick_entity(self):
        iid=self.entity_picker.currentData()
        if iid:self.show_properties(self.c.entity(self.revision_id,iid))
    def show_library(self):
        if not self.flush():return
        self._lib_rows=[]
        for source,c in [('I tuoi IPF',self.user_controller),('DEMO',self.demo_store.controller if self.demo_store else None)]:
            if c:
                for row in c.ipf_library():self._lib_rows.append((source,c,row))
        populate(self.lib_table,[(s,r['name'],r['revision_code'],r['status']) for s,c,r in self._lib_rows]); self.stack.setCurrentWidget(self.library); self.nav_buttons['Libreria IPF'].setChecked(True)
    def open_selected(self,*_):
        i=self.lib_table.currentRow()
        if i>=0 and self.flush():_,self.c,r=self._lib_rows[i]; self.open_revision(r['revision_id'])
    def open_revision(self,rid):
        self.revision_id=rid; self.canvas.c=self.c; self.inspector.clear(); overview=self.c.overview(rid); self.ipf_title.setText('Libreria / '+overview['model_name']); self.canvas_title.setText(overview['model_name']); self.revision_badge.setText(overview['revision_code']); self.state_badge.setText(overview.get('status','DRAFT')); self.model_id=overview['process_model_id']; self.workspace_id=self.c.uow.models.model(self.model_id).workspace_id; self.stack.setCurrentWidget(self.workspace); self.nav_buttons['Canvas'].setChecked(True); self.refresh_canvas()
    def show_canvas(self):
        if self.revision_id and self.flush():self.stack.setCurrentWidget(self.workspace); self.nav_buttons['Canvas'].setChecked(True); self.refresh_canvas()
        else:self.show_library()
    def show_page(self,page):
        if not self.revision_id:self.show_library(); return
        if self.flush():page.refresh(); self.stack.setCurrentWidget(page)
    def refresh_canvas(self,*_):
        if not self.revision_id or not self.flush():return
        self.canvas.refresh(self.revision_id); es=self.c.visual_entities(self.revision_id); 
        for code,label in self.stat_labels.items():label.setText(str(sum(e.get('properties',{}).get('CRITICALITY') not in (None,'','NONE','NO','0',0) for e in es)) if code=='CRITICAL' else str(sum(e['type_code']==code for e in es)))
        self.minimap.update(); previous=self.entity_picker.currentData(); self.entity_picker.clear(); self.entity_picker.addItem('Seleziona un elemento per modificarlo…',None)
        for e in self.c.visual_entities(self.revision_id):self.entity_picker.addItem(LABELS.get(e['type_code'],e['type_name'])+' · '+e['name'],e['identity_id'])
        i=self.entity_picker.findData(previous)
        if i>=0:self.entity_picker.setCurrentIndex(i)
    def new_ipf(self):
        d=FieldDialog('Nuovo IPF',self); workspace=QLineEdit(); name=QLineEdit(); d.form.addRow('Workspace',workspace); d.form.addRow('Nome IPF',name)
        if d.exec() and name.text().strip() and workspace.text().strip():
            try:self.c=self.user_controller; wid=self.c.create_workspace(workspace.text()); _,rid=self.c.create_model(wid,name.text()); self.open_revision(rid)
            except Exception as exc:self.statusBar().showMessage(str(exc))
    def add_element(self,type_code):
        if not self.revision_id or not self.flush():return
        d=ElementDialog(self.c,self.revision_id,type_code,self)
        if d.exec():self.refresh_canvas(); self.show_properties(self.c.entity(self.revision_id,d.identity_id))
    def add_relation(self):
        if self.revision_id and self.flush() and ConnectDialog(self.c,self.revision_id,self).exec():self.refresh_canvas()
    def add_flow(self):
        if self.revision_id and self.flush() and FlowDialog(self.c,self.revision_id,self).exec():self.refresh_canvas()
    def edit_flow(self,iid):
        if not self.flush():return
        flow=next(f for f in self.c.flow_projections(self.revision_id) if f['flow_identity_id']==iid)
        if FlowDialog(self.c,self.revision_id,self,flow).exec():self.refresh_canvas(); self.show_properties(self.c.entity(self.revision_id,iid))
    def validate(self):
        if self.revision_id:
            report=self.c.validate_revision(self.revision_id); fk=self.c.rows('PRAGMA foreign_key_check'); self.statusBar().showMessage('Modello valido · Foreign key OK' if report.is_valid and not fk else '; '.join(x.message for x in report.issues)+str(fk))
    def clone_revision(self):
        if not self.flush():return
        code,ok=QInputDialog.getText(self,'Copia modificabile','Codice nuova revisione')
        if ok and code.strip():
            try:self.open_revision(self.c.clone_revision(self.revision_id,code.strip()))
            except Exception as exc:self.statusBar().showMessage(str(exc))
    def reset_demo(self):
        if not self.demo_store:return
        if QMessageBox.question(self,'Reset Demo','Ripristinare il solo workspace DEMO? Le modifiche al demo saranno sostituite dai dati iniziali.',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        try:
            self.inspector.clear(); self.c=self.demo_store.reset(); self.open_revision(self.c.ipf_library()[0]['revision_id']); self.statusBar().showMessage('Demo ripristinato. IPF utente conservati.')
        except Exception as exc:self.statusBar().showMessage(str(exc))
    def closeEvent(self,event):
        if not self.flush():event.ignore(); return
        event.accept()
