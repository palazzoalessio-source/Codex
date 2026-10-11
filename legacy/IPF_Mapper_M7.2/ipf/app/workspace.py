"""M7.1 application workflows. All business policies are persisted configuration."""
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import asdict
import json
import math
from uuid import uuid4

from ..domain.validation import TypeSystem
from ..domain.expressions import *
from ..domain.active import ActiveStateResolver, StateRule, RulePurpose
from ..domain.rules import AssertionRuleDefinition
from ..domain.process_analysis import DependencyConstraint, InstanceInterval, CorrectionEvidence
from ..engines.expression_engine import ExpressionEngine
from ..engines.rule_engine import RuleEngine
from ..engines.binding_engine import BindingEngine
from ..engines.graph_engine import GraphEngine
from ..engines.analysis_engine import AnalysisEngine

PARTICIPANTS = {'PARTICIPANT','INTERNAL_FUNCTION','EXTERNAL_PARTY','ROLE','PERSON'}
ICONS = ('Mail','ERP','Database','Phone','Teams','Web Portal','Generic')
STATES = {'APPLICABILITY':('APPLICABLE','NOT_APPLICABLE'),
          'REQUIREMENT':('REQUIRED','OPTIONAL','FORBIDDEN'),
          'ENABLEMENT':('ENABLED','BLOCKED')}

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid4())

class WorkspaceFeatures:
    def __init__(self, db_path):
        super().__init__(db_path)
        self._depth = 0
        self.con.executescript('''
        CREATE TABLE IF NOT EXISTS state_rule_config (
          rule_definition_id INTEGER PRIMARY KEY REFERENCES rule_definition(id) ON DELETE CASCADE,
          target_identity_id INTEGER NOT NULL REFERENCES entity_identity(id),
          true_state TEXT NOT NULL, false_state TEXT NOT NULL,
          recipe TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runtime_correction (
          execution_id INTEGER NOT NULL REFERENCES model_execution(id),
          correcting_instance_id INTEGER NOT NULL REFERENCES entity_instance(id),
          corrected_instance_id INTEGER NOT NULL REFERENCES entity_instance(id),
          PRIMARY KEY(execution_id,correcting_instance_id,corrected_instance_id));
        CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        with self.atomic():
            specs = [('MEANS_ICON','ENUM','DEFINITION',('MEANS',)),
                     ('ENTITY_CODE','TEXT','DEFINITION',None),
                     ('ENABLED_AT','DATETIME','INSTANCE',('ACTION',)),
                     ('CRITICALITY_SEVERITY','ENUM','DEFINITION',('ACTION','INFORMATION'))]
            for code,typ,scope,types in specs:
                if not self.row('SELECT id FROM property_definition WHERE code=? AND workspace_id IS NULL',(code,)):
                    p=self.con.execute('INSERT INTO property_definition(uid,code,name,value_type,scope,is_core) VALUES(?,?,?,?,?,1)',('m71:'+code,code,code,typ,scope)).lastrowid
                    for t in types or [x['code'] for x in self.entity_types()]:
                        self.con.execute('INSERT INTO property_applicability VALUES(?,?)',(p,self.uow.catalogs.entity_type(t).id))

    @contextmanager
    def atomic(self):
        outer = self._depth == 0
        if outer: self.con.execute('BEGIN')
        self._depth += 1
        try:
            yield
            if outer: self.con.commit()
        except BaseException:
            if outer: self.con.rollback()
            raise
        finally: self._depth -= 1

    def editable(self,rid):
        r=self.uow.models.revision(rid)
        if not r.is_editable: raise ValueError('Revisione pubblicata: crea una copia modificabile.')
        return self.uow.models.model(r.process_model_id)

    def definition_editable(self,did):
        if self.row("SELECT 1 FROM model_revision_entity m JOIN model_revision r ON r.id=m.model_revision_id WHERE m.entity_definition_id=? AND r.status!='DRAFT'",(did,)):
            raise ValueError('Definizione pubblicata: modifica una copia della revisione.')

    def entity(self,rid,iid):
        e=next((e for e in self.visual_entities(rid) if e['identity_id']==iid),None)
        if not e: raise ValueError('Elemento non presente nella revisione.')
        return e

    def add_entity(self,rid,type_code,name,stable_code='',description=''):
        if not name.strip(): raise ValueError('Inserisci un nome.')
        with self.atomic():
            model=self.editable(rid); t=self.uow.catalogs.entity_type(type_code,model.workspace_id)
            i=self.uow.entities.insert_identity(model.workspace_id,t.id,stable_code.strip() or None)
            d=self.uow.entities.insert_definition(i.id,name.strip(),description.strip() or None)
            self.uow.models.add_entity(rid,d.id)
            if type_code=='MEANS': self.set_definition_property(d.id,'MEANS_ICON',name if name in ICONS else 'Generic')
            return i.id

    def add_action(self,rid,name,participant_identity_id=None,stable_code='',description=''):
        with self.atomic():
            iid=self.add_entity(rid,'ACTION',name,stable_code,description)
            if participant_identity_id: self.add_relation(rid,'PERFORMER',iid,participant_identity_id)
            return iid

    def allowed_semantics(self,rid,source,target):
        es={i.id:i for i,_ in self.uow.models.entities(rid)}
        if source not in es or target not in es or source==target: return []
        ts=TypeSystem(self.uow.catalogs.all_types()); result=[]
        for sem in self.relation_semantics():
            sid=self.uow.catalogs.semantic(sem['code'])['id']
            if any(ts.is_same_or_subtype(es[source].entity_type_id,s['source_entity_type_id']) and ts.is_same_or_subtype(es[target].entity_type_id,s['target_entity_type_id']) for s in self.uow.catalogs.signatures(sid)):
                result.append(sem['code'])
        return result

    def add_relation(self,rid,semantic_code,source_identity_id,target_identity_id):
        with self.atomic():
            model=self.editable(rid)
            if semantic_code not in self.allowed_semantics(rid,source_identity_id,target_identity_id):
                raise ValueError('Collegamento non ammesso dalla grammatica del dominio.')
            rels=self.relations(rid)
            for r in rels:
                if (r['semantic_code'],r['source_identity_id'],r['target_identity_id'])==(semantic_code,source_identity_id,target_identity_id): return r['id']
            if semantic_code in ('SOURCE','TARGET','VIA','CARRIES','PERFORMER') and any(r['semantic_code']==semantic_code and r['source_identity_id']==source_identity_id for r in rels):
                raise ValueError('Assegnazione già presente; modifica quella esistente.')
            if semantic_code=='CONTAINS':
                parent={c:g for g,c in self.containment(rid)}
                if target_identity_id in parent: raise ValueError('Elemento già assegnato a un gruppo.')
                x=source_identity_id
                while x in parent:
                    x=parent[x]
                    if x==target_identity_id: raise ValueError('Un gruppo non può contenere un proprio antenato.')
            sem=self.uow.catalogs.semantic(semantic_code,model.workspace_id)
            r=self.uow.relations.insert(model.workspace_id,sem['id'],source_identity_id,target_identity_id)
            self.uow.models.add_relation(rid,r.id); return r.id

    def remove_relation(self,rid,relation_id):
        with self.atomic():
            self.editable(rid); self.uow.models.remove_relation(rid,relation_id)

    def connect_elements(self,rid,source,target,semantic=None):
        """Canvas INPUT is drawn Information -> Action; the catalog stores Action INPUT Information."""
        s=self.entity(rid,source); t=self.entity(rid,target)
        if s['type_code']=='INFORMATION' and t['type_code']=='ACTION':
            return self.add_relation(rid,'INPUT',target,source)
        if semantic: return self.add_relation(rid,semantic,source,target)
        if s['type_code']=='ACTION' and t['type_code']=='INFORMATION': return self.add_relation(rid,'OUTPUT',source,target)
        raise ValueError('Seleziona una relazione ammessa o crea un Information Flow.')

    def create_information_flow(self,rid,source_action_id,target_action_id,means_identity_id=None,information_name='',lead_time='',information_identity_id=None):
        with self.atomic():
            for iid in (source_action_id,target_action_id):
                if self.entity(rid,iid)['type_code'] not in PARTICIPANTS|{'ACTION'}: raise ValueError('Gli endpoint di un flow devono essere attività o partecipanti.')
            if source_action_id==target_action_id: raise ValueError('Seleziona due endpoint diversi.')
            if means_identity_id and self.entity(rid,means_identity_id)['type_code']!='MEANS': raise ValueError('Mezzo non valido.')
            if information_identity_id and self.entity(rid,information_identity_id)['type_code']!='INFORMATION': raise ValueError('Informazione non valida.')
            f=self.add_entity(rid,'INFORMATION_FLOW',f"{self.entity(rid,source_action_id)['name']} → {self.entity(rid,target_action_id)['name']}")
            self.add_relation(rid,'SOURCE',f,source_action_id); self.add_relation(rid,'TARGET',f,target_action_id)
            if means_identity_id: self.add_relation(rid,'VIA',f,means_identity_id)
            info=information_identity_id
            if not info and information_name.strip(): info=self.add_entity(rid,'INFORMATION',information_name)
            if info: self.add_relation(rid,'CARRIES',f,info)
            if lead_time: self.set_definition_property(self.entity(rid,f)['definition_id'],'TARGET_LEAD_TIME',lead_time)
            return f

    def update_flow(self,rid,fid,source,target,information=None,means=None,lead_time=''):
        with self.atomic():
            self.editable(rid); f=self.entity(rid,fid)
            if f['type_code']!='INFORMATION_FLOW': raise ValueError('Non è un flow.')
            if source==target: raise ValueError('Endpoint uguali.')
            for r in self.relations(rid):
                if r['source_identity_id']==fid and r['semantic_code'] in ('SOURCE','TARGET','VIA','CARRIES'): self.uow.models.remove_relation(rid,r['id'])
            for sem,target_id in [('SOURCE',source),('TARGET',target),('CARRIES',information),('VIA',means)]:
                if target_id: self.add_relation(rid,sem,fid,target_id)
            self.set_definition_property(f['definition_id'],'TARGET_LEAD_TIME',lead_time)

    def flow_projections(self,rid):
        es={e['identity_id']:e for e in self.visual_entities(rid)}; rels=self.relations(rid); out=[]
        for fid,e in es.items():
            if e['type_code']!='INFORMATION_FLOW': continue
            links={r['semantic_code']:r['target_identity_id'] for r in rels if r['source_identity_id']==fid}
            m=es.get(links.get('VIA'),{}); info=es.get(links.get('CARRIES'),{})
            out.append(dict(flow_identity_id=fid,flow_definition_id=e['definition_id'],source_action_id=links.get('SOURCE'),target_action_id=links.get('TARGET'),means=m.get('name'),means_id=links.get('VIA'),means_icon=m.get('properties',{}).get('MEANS_ICON','Generic'),information=info.get('name'),information_id=links.get('CARRIES'),lead_time=e['properties'].get('TARGET_LEAD_TIME')))
        return out

    def applicable_properties(self,type_code,scope='DEFINITION'):
        ts=TypeSystem(self.uow.catalogs.all_types()); t=self.uow.catalogs.entity_type(type_code).id
        return [p for p in self.rows('SELECT * FROM property_definition WHERE scope IN (?,\'BOTH\')',(scope,)) if any(ts.is_same_or_subtype(t,a['entity_type_id']) for a in self.rows('SELECT entity_type_id FROM property_applicability WHERE property_definition_id=?',(p['id'],)))]

    def typed_columns(self,typ,value):
        cols=[None,None,None,None]
        if typ=='BOOLEAN':
            if str(value).lower() not in ('1','0','true','false','yes','no'): raise ValueError('Usa true o false.')
            cols[3]=int(str(value).lower() in ('1','true','yes'))
        elif typ in ('INTEGER','NUMBER'):
            n=int(value) if typ=='INTEGER' else float(value)
            if not math.isfinite(n): raise ValueError('Numero non finito.')
            cols[1 if typ=='INTEGER' else 2]=n
        else:
            if typ=='DATETIME':
                d=datetime.fromisoformat(str(value))
                if d.tzinfo is None: raise ValueError('Timestamp con fuso orario richiesto, es. +00:00.')
            cols[0]=str(value)
        return cols

    def set_definition_property(self,did,code,value):
        self.definition_editable(did)
        e=self.row('SELECT et.code FROM entity_definition d JOIN entity_identity i ON i.id=d.entity_identity_id JOIN entity_type et ON et.id=i.entity_type_id WHERE d.id=?',(did,))
        p=next((p for p in self.applicable_properties(e['code']) if p['code']==code),None)
        if not p: raise ValueError('Proprietà non pertinente a questo tipo.')
        if code=='MEANS_ICON' and value not in ICONS: raise ValueError('Icona non valida.')
        with self.atomic():
            if value is None or (str(value).strip()=='' and code!='ENTITY_CODE'): self.con.execute('DELETE FROM definition_property_value WHERE entity_definition_id=? AND property_definition_id=?',(did,p['id']))
            else: self.con.execute('INSERT INTO definition_property_value VALUES(?,?,?,?,?,?) ON CONFLICT(entity_definition_id,property_definition_id) DO UPDATE SET value_text=excluded.value_text,value_integer=excluded.value_integer,value_real=excluded.value_real,value_boolean=excluded.value_boolean',(did,p['id'],*self.typed_columns(p['value_type'],value)))

    def update_entity_text(self,did,name,description=''):
        if not name.strip(): raise ValueError('Nome obbligatorio.')
        self.definition_editable(did)
        with self.atomic(): self.con.execute('UPDATE entity_definition SET name=?,description=? WHERE id=?',(name.strip(),description.strip(),did))

    def save_element(self,rid,iid,name,code,description,properties,performer=None):
        with self.atomic():
            self.editable(rid); e=self.entity(rid,iid); did=e['definition_id']
            self.update_entity_text(did,name,description)
            self.set_definition_property(did,'ENTITY_CODE',code)
            for k,v in properties.items(): self.set_definition_property(did,k,v)
            if e['type_code']=='ACTION':
                old_performer=self.performers(rid).get(iid)
                for r in self.relations(rid):
                    if r['source_identity_id']==iid and r['semantic_code']=='PERFORMER': self.uow.models.remove_relation(rid,r['id'])
                if performer: self.add_relation(rid,'PERFORMER',iid,performer)
                if performer and old_performer!=performer:
                    layouts=self.layout(rid); functions=sorted([x for x in self.entities(rid) if x['type_code'] in PARTICIPANTS],key=lambda x:(layouts.get(x['identity_id'],{}).get('y',9999),x['name']))
                    lane_y=layouts.get(performer,{}).get('y',110+next(i for i,x in enumerate(functions) if x['identity_id']==performer)*150)
                    self.con.execute('UPDATE entity_view_layout SET y=? WHERE model_revision_id=? AND entity_identity_id=?',(lane_y+10,rid,iid))

    def visual_entities(self,rid):
        es=super().visual_entities(rid)
        for e in es: e['stable_code']=e['properties'].get('ENTITY_CODE',e['stable_code'])
        return es

    def clone_revision(self,rid,new_code,purpose=None):
        with self.atomic():
            src=self.uow.models.revision(rid); dst=self.uow.models.insert_revision(src.process_model_id,new_code,purpose or src.purpose,rid)
            for i,d in self.uow.models.entities(rid):
                nd=self.uow.entities.insert_definition(i.id,d.name,d.description,d.origin); self.uow.models.add_entity(dst.id,nd.id)
                self.con.execute('INSERT INTO definition_property_value SELECT ?,property_definition_id,value_text,value_integer,value_real,value_boolean FROM definition_property_value WHERE entity_definition_id=?',(nd.id,d.id))
            for r in self.uow.models.relations(rid): self.uow.models.add_relation(dst.id,r.id)
            self.con.execute('INSERT INTO model_revision_rule SELECT ?,rule_definition_id FROM model_revision_rule WHERE model_revision_id=?',(dst.id,rid))
            self.con.execute('INSERT INTO model_revision_parameter_value SELECT ?,parameter_definition_id,value_text,value_integer,value_real,value_boolean FROM model_revision_parameter_value WHERE model_revision_id=?',(dst.id,rid))
            self.con.execute('INSERT INTO entity_view_layout SELECT ?,entity_identity_id,x,y,width,height,collapsed,z_index FROM entity_view_layout WHERE model_revision_id=?',(dst.id,rid))
            return dst.id

    def set_parameter(self,rid,code,name,value_type,value,description=''):
        with self.atomic():
            model=self.editable(rid)
            if not code.strip() or not name.strip(): raise ValueError('Codice e nome obbligatori.')
            cols=self.typed_columns(value_type,value)
            p=self.row('SELECT * FROM model_parameter_definition WHERE workspace_id=? AND code=?',(model.workspace_id,code))
            if p and p['value_type']!=value_type: raise ValueError('Il tipo del parametro esistente non può cambiare.')
            pid=p['id'] if p else self.con.execute('INSERT INTO model_parameter_definition(uid,workspace_id,code,name,value_type,description,created_at) VALUES(?,?,?,?,?,?,?)',(uid(),model.workspace_id,code,name,value_type,description,now())).lastrowid
            self.con.execute('INSERT INTO model_revision_parameter_value VALUES(?,?,?,?,?,?) ON CONFLICT(model_revision_id,parameter_definition_id) DO UPDATE SET value_text=excluded.value_text,value_integer=excluded.value_integer,value_real=excluded.value_real,value_boolean=excluded.value_boolean',(rid,pid,*cols)); return pid

    def parameter_values(self,rid):
        return {p['code']:BindingEngine._decode(p) for p in self.parameters(rid) if any(p[k] is not None for k in ('value_text','value_integer','value_real','value_boolean'))}

    def save_state_rule(self,rid,name,target,purpose,recipe,true_state,false_state,replace_id=None):
        if purpose not in STATES or true_state not in STATES[purpose] or false_state not in STATES[purpose]: raise ValueError('Stato non valido per lo scopo della regola.')
        self.entity(rid,target)
        def operand(spec):
            if spec['kind']=='parameter':
                if spec['code'] not in self.parameter_values(rid): raise ValueError('Parametro mancante: '+spec['code'])
                return ReferenceNode(ReferenceKind.CONTEXT,ReferenceScope.CONTEXT,variable_name=spec['code'])
            if spec['kind']=='literal':
                v=spec['value']; typ=ValueType.BOOLEAN if isinstance(v,bool) else ValueType.NUMBER if isinstance(v,(int,float)) else ValueType.TEXT
                return LiteralNode(TypedValue(typ,v))
            if spec['kind']=='property':
                self.entity(rid,spec['identity_id']); p=self.row('SELECT id FROM property_definition WHERE code=?',(spec['code'],))
                if not p: raise ValueError('Proprietà sconosciuta.')
                return ReferenceNode(ReferenceKind.PROPERTY,ReferenceScope.DEFINITION,spec['identity_id'],p['id'])
            raise ValueError('Operando non valido.')
        if recipe.get('kind')=='completed':
            pre=recipe['identity_id']; self.entity(rid,pre)
            p=self.row("SELECT id FROM property_definition WHERE code='STATUS'")['id']
            root=OperationNode('ANY',(ReferenceNode(ReferenceKind.ENTITY,ReferenceScope.INSTANCE,pre),OperationNode('EQ',(ReferenceNode(ReferenceKind.PROPERTY,ReferenceScope.INSTANCE,pre,p),LiteralNode(TypedValue(ValueType.ENUM,'COMPLETED'))))))
        else:
            if recipe['op'] not in ('EQ','NEQ','GT','GTE','LT','LTE'): raise ValueError('Confronto non valido.')
            root=OperationNode(recipe['op'],(operand(recipe['left']),operand(recipe['right'])))
        with self.atomic():
            model=self.editable(rid)
            identity=self.uow.rules.insert_identity(model.workspace_id)
            expr=self.uow.expressions.insert(Expression(None,'',root))
            rule=AssertionRuleDefinition(None,'',identity.id,name,expr)
            did=self.uow.rules.insert_definition(rule)
            self.con.execute('UPDATE rule_definition SET purpose=? WHERE id=?',(purpose,did))
            self.con.execute('INSERT INTO state_rule_config VALUES(?,?,?,?,?)',(did,target,true_state,false_state,json.dumps(recipe)))
            if replace_id: self.con.execute('DELETE FROM model_revision_rule WHERE model_revision_id=? AND rule_definition_id=?',(rid,replace_id))
            self.uow.rules.add_to_revision(rid,did); return did

    def configured_rules(self,rid):
        return self.rows('SELECT r.*,s.target_identity_id,s.true_state,s.false_state,s.recipe FROM model_revision_rule m JOIN rule_definition r ON r.id=m.rule_definition_id LEFT JOIN state_rule_config s ON s.rule_definition_id=r.id WHERE m.model_revision_id=? ORDER BY r.id',(rid,))

    def delete_rule(self,rid,rule_id):
        with self.atomic(): self.editable(rid); self.con.execute('DELETE FROM model_revision_rule WHERE model_revision_id=? AND rule_definition_id=?',(rid,rule_id))

    def evaluation_context(self,rid,execution_id=None):
        props={(e['identity_id'],p['id']):BindingEngine._decode(p) for e in self.entities(rid) for p in self.rows('SELECT v.*,d.id,d.value_type FROM definition_property_value v JOIN property_definition d ON d.id=v.property_definition_id WHERE v.entity_definition_id=?',(e['definition_id'],))}
        graph=GraphEngine().potential(self.uow.models.snapshot(rid))
        if execution_id:
            ex=self.row('SELECT r.process_model_id FROM model_execution e JOIN model_revision r ON r.id=e.model_revision_id WHERE e.id=?',(execution_id,))
            if not ex or ex['process_model_id']!=self.uow.models.revision(rid).process_model_id: raise ValueError('Execution di un altro modello.')
            ctx=BindingEngine(self.con).for_execution(execution_id,context_values=self.parameter_values(rid),graph=graph)
            from dataclasses import replace
            return replace(ctx,definition_properties=props)
        return EvaluationContext(props,{},self.parameter_values(rid),{},{},{},graph=graph)

    def evaluate_states(self,rid,execution_id=None):
        ctx=self.evaluation_context(rid,execution_id); engine=RuleEngine(ExpressionEngine()); rules=[]; evaluations=[]
        for r in self.configured_rules(rid):
            rule=self.uow.rules.get_definition(r['id'],self.uow.expressions)
            try: evaluation=engine.evaluate(rule,ctx)
            except (TypeError,ValueError,KeyError) as exc:
                evaluations.append({'id':r['id'],'name':r['name'],'result':'UNKNOWN','detail':str(exc)})
                if r['target_identity_id']:rules.append(StateRule(r['target_identity_id'],RulePurpose(r['purpose']),lambda c:None,r['id']))
                continue
            display_result=('TRUE' if evaluation.value==TruthValue.TRUE else 'FALSE' if evaluation.value==TruthValue.FALSE else 'UNKNOWN') if r['target_identity_id'] else evaluation.status.value
            evaluations.append({'id':r['id'],'name':r['name'],'result':display_result,'engine_status':evaluation.status.value,'value':str(evaluation.value)})
            if r['target_identity_id']:
                state=r['true_state'] if evaluation.value==TruthValue.TRUE else r['false_state'] if evaluation.value==TruthValue.FALSE else None
                rules.append(StateRule(r['target_identity_id'],RulePurpose(r['purpose']),lambda c,s=state:s,r['id']))
        return ActiveStateResolver().resolve([e['identity_id'] for e in self.entities(rid)],ctx,rules),evaluations

    def executions_for_revision(self,rid):
        return self.rows('SELECT e.id,c.name context_name,e.model_revision_id,r.revision_code,e.created_at FROM model_execution e JOIN execution_context c ON c.id=e.execution_context_id JOIN model_revision r ON r.id=e.model_revision_id WHERE r.process_model_id=(SELECT process_model_id FROM model_revision WHERE id=?) ORDER BY e.id DESC',(rid,))

    def create_execution_snapshot(self,rid,name):
        if not name.strip():raise ValueError('Nome Execution obbligatorio.')
        report=self.validate_revision(rid)
        if not report.is_valid:raise ValueError('; '.join(x.message for x in report.issues))
        snapshot=self.clone_revision(rid,'RUN-'+uid()[:8]); self.publish_revision(snapshot)
        wid=self.uow.models.model(self.uow.models.revision(rid).process_model_id).workspace_id
        return self.start_execution(self.create_context(wid,name),snapshot)

    def instantiate(self,execution_id,definition_id):
        ex=self.row('SELECT * FROM model_execution WHERE id=?',(execution_id,))
        d=self.row('SELECT entity_identity_id FROM entity_definition WHERE id=?',(definition_id,))
        if not ex or not d: raise ValueError('Execution o definizione assente.')
        actual=self.uow.models.definition_for_identity(ex['model_revision_id'],d['entity_identity_id'])
        with self.atomic():
            i=self.uow.executions.insert_instance(ex['execution_context_id'],actual.id); self.uow.executions.attach_entity(execution_id,i.id); return i.id

    def observe(self,execution_id,instance_id,code,value,observed_at=None):
        if not self.row('SELECT 1 FROM model_execution_entity WHERE model_execution_id=? AND entity_instance_id=?',(execution_id,instance_id)): raise ValueError('Istanza non appartenente alla Execution.')
        e=self.row('SELECT t.code FROM entity_instance i JOIN entity_definition d ON d.id=i.entity_definition_id JOIN entity_identity ei ON ei.id=d.entity_identity_id JOIN entity_type t ON t.id=ei.entity_type_id WHERE i.id=?',(instance_id,))
        p=next((p for p in self.applicable_properties(e['code'],'INSTANCE') if p['code']==code),None)
        if not p: raise ValueError('Osservazione non pertinente al tipo.')
        cols=self.typed_columns(p['value_type'],value); timestamp=observed_at or now(); self.typed_columns('DATETIME',timestamp)
        if code in ('ACTUAL_START','ACTUAL_END','ENABLED_AT'):
            vals=self.instance_values(instance_id); vals[code]=value
            if vals.get('ACTUAL_START') and vals.get('ACTUAL_END') and datetime.fromisoformat(vals['ACTUAL_END'])<datetime.fromisoformat(vals['ACTUAL_START']): raise ValueError('La fine precede l’inizio.')
        with self.atomic():
            self.con.execute('INSERT INTO property_observation(entity_instance_id,property_definition_id,value_text,value_integer,value_real,value_boolean,observed_at,recorded_at) VALUES(?,?,?,?,?,?,?,?)',(instance_id,p['id'],*cols,timestamp,now()))
            latest=self.row('SELECT * FROM property_observation WHERE entity_instance_id=? AND property_definition_id=? ORDER BY julianday(observed_at) DESC,id DESC LIMIT 1',(instance_id,p['id']))
            self.con.execute('INSERT INTO instance_property_value(entity_instance_id,property_definition_id,value_text,value_integer,value_real,value_boolean) VALUES(?,?,?,?,?,?) ON CONFLICT(entity_instance_id,property_definition_id) DO UPDATE SET value_text=excluded.value_text,value_integer=excluded.value_integer,value_real=excluded.value_real,value_boolean=excluded.value_boolean',(instance_id,p['id'],*(latest[k] for k in ('value_text','value_integer','value_real','value_boolean'))))

    def instance_values(self,iid):
        return {p['code']:next((p[k] for k in ('value_text','value_integer','value_real','value_boolean') if p[k] is not None),None) for p in self.rows('SELECT v.*,p.code FROM instance_property_value v JOIN property_definition p ON p.id=v.property_definition_id WHERE entity_instance_id=?',(iid,))}

    def add_correction(self,execution_id,new,old):
        members={x['instance_id']:x for x in self.execution_instances(execution_id)}
        if new==old or new not in members or old not in members or members[new]['identity_id']!=members[old]['identity_id']: raise ValueError('Il rework deve correggere un’altra istanza dello stesso elemento nella stessa Execution.')
        with self.atomic(): self.con.execute('INSERT OR IGNORE INTO runtime_correction VALUES(?,?,?)',(execution_id,new,old))

    def runtime_analysis(self,rid,execution_id=None):
        active,evaluations=self.evaluate_states(rid,execution_id); engine=AnalysisEngine(); constraints=[]
        for r in self.configured_rules(rid):
            recipe=json.loads(r['recipe']) if r['recipe'] else {}
            if r['purpose']=='ENABLEMENT' and recipe.get('kind')=='completed': constraints.append(DependencyConstraint(recipe['identity_id'],r['target_identity_id'],r['id'],'COMPLETED'))
        intervals=[]; waits=[]; corrections=[]
        if execution_id:
            for i in self.execution_instances(execution_id):
                if self.entity(rid,i['identity_id'])['type_code']!='ACTION': continue
                p=self.instance_values(i['instance_id']); dt=lambda k:datetime.fromisoformat(p[k]) if p.get(k) else None
                iv=InstanceInterval(i['instance_id'],i['identity_id'],dt('ACTUAL_START'),dt('ACTUAL_END')); intervals.append(iv); waits.append(engine.waiting(iv,dt('ENABLED_AT')))
            corrections=[CorrectionEvidence(r['correcting_instance_id'],r['corrected_instance_id']) for r in self.rows('SELECT * FROM runtime_correction WHERE execution_id=?',(execution_id,))]
        actions=[e['identity_id'] for e in self.entities(rid) if e['type_code']=='ACTION']
        potential=GraphEngine().potential(self.uow.models.snapshot(rid)); ag=GraphEngine().active(potential,[s.identity_id for s in active.actionable])
        realized=GraphEngine().realized(self.uow.executions.execution_entities(execution_id),self.uow.executions.execution_relations(execution_id)) if execution_id else None
        return dict(active=active,evaluations=evaluations,dependencies=engine.dependencies(constraints),branches=engine.branches(constraints,active),parallelism=engine.potential_parallelism(actions,constraints,active,intervals),cycles=engine.cycles(constraints),repeats=engine.repeats(intervals,corrections),waiting=tuple(waits),sequence=tuple(engine.sequence(a,b) for a,b in zip(sorted(intervals,key=lambda i:(i.start is None,i.start,i.instance_id)),sorted(intervals,key=lambda i:(i.start is None,i.start,i.instance_id))[1:])),graphs={'potential_nodes':len(potential.nodes),'potential_edges':len(potential.edges),'active_nodes':len(ag.nodes),'realized_nodes':len(realized.nodes) if realized else 0,'realized_edges':len(realized.edges) if realized else 0})

    def ipf_library(self):
        rows=super().ipf_library()
        # Execution snapshots are immutable history; keep the most recent draft as the editing entry.
        for row in rows:
            draft=self.row("SELECT id,revision_code,purpose,status FROM model_revision WHERE process_model_id=? AND status='DRAFT' ORDER BY id DESC LIMIT 1",(row['model_id'],))
            if draft: row.update(revision_id=draft['id'],revision_code=draft['revision_code'],purpose=draft['purpose'],status=draft['status'])
        return rows

    def hidden_elements(self,rid):
        parent={c:g for g,c in self.containment(rid)}; collapsed={i for i,p in self.layout(rid).items() if p['collapsed']}; hidden={}
        for child in parent:
            x=child; seen=set()
            while x in parent and x not in seen:
                seen.add(x); x=parent[x]
                if x in collapsed: hidden[child]=x
        return hidden

    def toggle_group(self,rid,iid):
        if self.entity(rid,iid)['type_code']!='PROCESS_GROUP': raise ValueError('Non è un gruppo.')
        lo=self.layout(rid).get(iid,{})
        self.save_layout(rid,iid,lo.get('x',0),lo.get('y',0),collapsed=not lo.get('collapsed',0))
