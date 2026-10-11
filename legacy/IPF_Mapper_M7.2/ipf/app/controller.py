from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
import sqlite3

from ..database.connection import connect, initialize
from ..repositories.uow import UnitOfWork
from ..services.revision_service import RevisionService
from ..services.execution_service import ExecutionService

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'database' / 'migrations' / '0002_active_semantics_v1_1.sql'
VISUAL_MIGRATION = ROOT / 'database' / 'migrations' / '0003_visual_ipf_v1_2.sql'

def _now(): return datetime.now(timezone.utc).isoformat()
def _uid(prefix): return f'{prefix}:{uuid4()}'

@dataclass(frozen=True)
class Selection:
    workspace_id: int | None = None
    model_id: int | None = None
    revision_id: int | None = None
    execution_id: int | None = None

class LegacyController:
    """Thin application/query facade for the desktop UI. No Qt dependency."""
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.db_path.exists() or self.db_path.stat().st_size == 0
        self.con = connect(str(self.db_path))
        if new:
            initialize(self.con)
        self._ensure_v11()
        self._ensure_visual_v12()
        self.uow = UnitOfWork(self.con)
        self.revisions = RevisionService(self.uow)
        self.executions = ExecutionService(self.uow)

    def close(self):
        self.con.close()

    def _ensure_v11(self):
        cols={r['name'] for r in self.con.execute('PRAGMA table_info(rule_definition)')}
        if 'purpose' not in cols:
            self.con.executescript(MIGRATION.read_text(encoding='utf-8'))
            self.con.commit()

    def _ensure_visual_v12(self):
        exists=self.con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='entity_view_layout'").fetchone()
        if not exists:
            self.con.executescript(VISUAL_MIGRATION.read_text(encoding='utf-8')); self.con.commit()

    def rows(self, sql, params=()): return [dict(r) for r in self.con.execute(sql,params).fetchall()]
    def row(self, sql, params=()):
        r=self.con.execute(sql,params).fetchone(); return dict(r) if r else None

    # ----- workspace / model -----
    def workspaces(self): return self.rows('SELECT id,name,description FROM workspace ORDER BY name')
    def create_workspace(self,name,description=''):
        with self.uow as u:
            w=u.workspaces.insert(name.strip(),description.strip() or None); u.commit(); return w.id
    def models(self,workspace_id): return self.rows('SELECT id,name,description FROM process_model WHERE workspace_id=? AND retired_at IS NULL ORDER BY name',(workspace_id,))
    def revisions_for_model(self,model_id): return self.rows('SELECT id,revision_code,purpose,status,created_at FROM model_revision WHERE process_model_id=? ORDER BY id DESC',(model_id,))
    def create_model(self,workspace_id,name,revision_code='v1',purpose='AS_IS'):
        m,r=self.revisions.create_model(workspace_id,name.strip(),revision_code.strip() or 'v1',purpose); return m.id,r.id
    def clone_revision(self,revision_id,new_code,purpose=None): return self.revisions.clone_revision(revision_id,new_code,purpose).id
    def validate_revision(self,revision_id): return self.revisions.validate(revision_id)
    def publish_revision(self,revision_id): return self.revisions.publish(revision_id)

    # ----- model elements -----
    def entity_types(self): return self.rows('SELECT code,name FROM entity_type ORDER BY id')
    def entities(self,revision_id):
        return self.rows('''SELECT ei.id identity_id, ed.id definition_id, et.code type_code, et.name type_name,
            ed.name, ei.stable_code, ed.description
            FROM model_revision_entity mre
            JOIN entity_definition ed ON ed.id=mre.entity_definition_id
            JOIN entity_identity ei ON ei.id=ed.entity_identity_id
            JOIN entity_type et ON et.id=ei.entity_type_id
            WHERE mre.model_revision_id=? ORDER BY et.id, ed.name''',(revision_id,))
    def add_entity(self,revision_id,type_code,name,stable_code='',description=''):
        return self.revisions.add_entity(revision_id,type_code,name.strip(),stable_code.strip() or None,description.strip() or None)[0].id
    def relations(self,revision_id):
        return self.rows('''SELECT rd.id, rs.code semantic_code, rs.name semantic_name,
            s.id source_identity_id, sd.name source_name, t.id target_identity_id, td.name target_name
            FROM model_revision_relation mrr JOIN relation_definition rd ON rd.id=mrr.relation_definition_id
            JOIN relation_semantic rs ON rs.id=rd.semantic_id
            JOIN entity_identity s ON s.id=rd.source_entity_identity_id
            JOIN entity_identity t ON t.id=rd.target_entity_identity_id
            JOIN model_revision_entity ms ON ms.model_revision_id=mrr.model_revision_id
            JOIN entity_definition sd ON sd.id=ms.entity_definition_id AND sd.entity_identity_id=s.id
            JOIN model_revision_entity mt ON mt.model_revision_id=mrr.model_revision_id
            JOIN entity_definition td ON td.id=mt.entity_definition_id AND td.entity_identity_id=t.id
            WHERE mrr.model_revision_id=? ORDER BY rd.id''',(revision_id,))
    def relation_semantics(self): return self.rows('SELECT code,name FROM relation_semantic ORDER BY id')
    def add_relation(self,revision_id,semantic_code,source_identity_id,target_identity_id): return self.revisions.add_relation(revision_id,semantic_code,source_identity_id,target_identity_id).id

    # ----- configurable business parameters -----
    def parameters(self,revision_id):
        return self.rows('''SELECT mpd.id,mpd.code,mpd.name,mpd.value_type,mpd.description,
          mrv.value_text,mrv.value_integer,mrv.value_real,mrv.value_boolean
          FROM model_parameter_definition mpd
          JOIN model_revision mr ON mr.id=? JOIN process_model pm ON pm.id=mr.process_model_id
          LEFT JOIN model_revision_parameter_value mrv ON mrv.parameter_definition_id=mpd.id AND mrv.model_revision_id=mr.id
          WHERE mpd.workspace_id=pm.workspace_id AND mpd.retired_at IS NULL ORDER BY mpd.name''',(revision_id,))
    def set_parameter(self,revision_id,code,name,value_type,value,description=''):
        rv=self.row('SELECT mr.status,pm.workspace_id FROM model_revision mr JOIN process_model pm ON pm.id=mr.process_model_id WHERE mr.id=?',(revision_id,))
        if not rv: raise ValueError('Revision not found')
        if rv['status']!='DRAFT': raise ValueError('Published/archived revisions are immutable. Clone the revision first.')
        with self.con:
            p=self.row('SELECT id FROM model_parameter_definition WHERE workspace_id=? AND code=?',(rv['workspace_id'],code.strip()))
            if p: pid=p['id']
            else:
                cur=self.con.execute('INSERT INTO model_parameter_definition(uid,workspace_id,code,name,value_type,description,created_at) VALUES(?,?,?,?,?,?,?)',(_uid('parameter'),rv['workspace_id'],code.strip(),name.strip(),value_type,description.strip() or None,_now())); pid=cur.lastrowid
            cols={'value_text':None,'value_integer':None,'value_real':None,'value_boolean':None}
            if value_type in ('TEXT','ENUM','DATE','DATETIME','DURATION'): cols['value_text']=str(value)
            elif value_type=='INTEGER': cols['value_integer']=int(value)
            elif value_type=='NUMBER': cols['value_real']=float(value)
            elif value_type=='BOOLEAN': cols['value_boolean']=1 if str(value).lower() in ('1','true','yes','y') else 0
            self.con.execute('''INSERT INTO model_revision_parameter_value(model_revision_id,parameter_definition_id,value_text,value_integer,value_real,value_boolean)
              VALUES(?,?,?,?,?,?) ON CONFLICT(model_revision_id,parameter_definition_id) DO UPDATE SET value_text=excluded.value_text,value_integer=excluded.value_integer,value_real=excluded.value_real,value_boolean=excluded.value_boolean''',(revision_id,pid,cols['value_text'],cols['value_integer'],cols['value_real'],cols['value_boolean']))
        return pid
    def rules(self,revision_id):
        return self.rows('''SELECT rd.id,rd.name,rd.semantic,rd.purpose,rd.severity FROM model_revision_rule mrr JOIN rule_definition rd ON rd.id=mrr.rule_definition_id WHERE mrr.model_revision_id=? ORDER BY rd.name''',(revision_id,))

    # ----- execution -----
    def contexts(self,workspace_id): return self.rows('SELECT id,name,started_at,closed_at FROM execution_context WHERE workspace_id=? ORDER BY id DESC',(workspace_id,))
    def create_context(self,workspace_id,name): return self.executions.create_context(workspace_id,name.strip()).id
    def executions_for_revision(self,revision_id):
        return self.rows('''SELECT me.id,ec.name context_name,me.created_at FROM model_execution me JOIN execution_context ec ON ec.id=me.execution_context_id WHERE me.model_revision_id=? ORDER BY me.id DESC''',(revision_id,))
    def start_execution(self,context_id,revision_id): return self.executions.start_execution(context_id,revision_id).id
    def execution_instances(self,execution_id):
        return self.rows('''SELECT ei.id instance_id,ed.name,et.name type_name,ei.created_at,ed.entity_identity_id identity_id
          FROM model_execution_entity mee JOIN entity_instance ei ON ei.id=mee.entity_instance_id
          JOIN entity_definition ed ON ed.id=ei.entity_definition_id JOIN entity_identity ident ON ident.id=ed.entity_identity_id JOIN entity_type et ON et.id=ident.entity_type_id
          WHERE mee.model_execution_id=? ORDER BY ei.id''',(execution_id,))
    def instantiate(self,execution_id,definition_id):
        ex=self.row('SELECT execution_context_id FROM model_execution WHERE id=?',(execution_id,));
        if not ex: raise ValueError('Execution not found')
        inst=self.executions.instantiate_entity(ex['execution_context_id'],definition_id); self.executions.attach_entity(execution_id,inst.id); return inst.id

    def add_action(self,revision_id,name,participant_identity_id=None,stable_code='',description=''):
        iid=self.add_entity(revision_id,'ACTION',name,stable_code,description)
        if participant_identity_id:
            self.add_relation(revision_id,'PERFORMER',iid,participant_identity_id)
        return iid
    def create_information_flow(self,revision_id,source_action_id,target_action_id,means_identity_id=None,information_name='',lead_time=''):
        flow_id=self.add_entity(revision_id,'INFORMATION_FLOW',f'Flow {source_action_id} → {target_action_id}')
        self.add_relation(revision_id,'SOURCE',flow_id,source_action_id)
        self.add_relation(revision_id,'TARGET',flow_id,target_action_id)
        if means_identity_id:self.add_relation(revision_id,'VIA',flow_id,means_identity_id)
        if information_name.strip():
            info_id=self.add_entity(revision_id,'INFORMATION',information_name.strip())
            self.add_relation(revision_id,'CARRIES',flow_id,info_id)
        if lead_time.strip():
            did=self.row('''SELECT ed.id FROM model_revision_entity mre JOIN entity_definition ed ON ed.id=mre.entity_definition_id WHERE mre.model_revision_id=? AND ed.entity_identity_id=?''',(revision_id,flow_id))['id']
            self.set_definition_property(did,'TARGET_LEAD_TIME',lead_time.strip())
        return flow_id
    def flow_projections(self,revision_id):
        flows=[]; entities={e['identity_id']:e for e in self.visual_entities(revision_id)}; rels=self.relations(revision_id)
        by={}
        for r in rels: by.setdefault(r['source_identity_id'],[]).append(r)
        for fid,e in entities.items():
            if e['type_code']!='INFORMATION_FLOW': continue
            x={'flow_identity_id':fid,'flow_definition_id':e['definition_id'],'source_action_id':None,'target_action_id':None,'means':None,'information':None,'lead_time':e['properties'].get('TARGET_LEAD_TIME')}
            for r in by.get(fid,[]):
                if r['semantic_code']=='SOURCE' and entities.get(r['target_identity_id'],{}).get('type_code')=='ACTION':x['source_action_id']=r['target_identity_id']
                elif r['semantic_code']=='TARGET' and entities.get(r['target_identity_id'],{}).get('type_code')=='ACTION':x['target_action_id']=r['target_identity_id']
                elif r['semantic_code']=='VIA':x['means']=r['target_name']
                elif r['semantic_code']=='CARRIES':x['information']=r['target_name']
            if x['source_action_id'] and x['target_action_id']:flows.append(x)
        return flows
    def performers(self,revision_id):
        return {r['source_identity_id']:r['target_identity_id'] for r in self.relations(revision_id) if r['semantic_code']=='PERFORMER'}
    def containment(self,revision_id):
        return [(r['source_identity_id'],r['target_identity_id']) for r in self.relations(revision_id) if r['semantic_code']=='CONTAINS']

    # ----- visual IPF / presentation -----
    def ipf_library(self):
        return self.rows('''SELECT pm.id model_id,pm.name,pm.description,w.name workspace_name,
          mr.id revision_id,mr.revision_code,mr.purpose,mr.status,mr.created_at,
          (SELECT COUNT(*) FROM model_revision_entity x WHERE x.model_revision_id=mr.id) element_count,
          (SELECT COUNT(*) FROM model_revision_relation x WHERE x.model_revision_id=mr.id) relation_count
          FROM process_model pm JOIN workspace w ON w.id=pm.workspace_id
          JOIN model_revision mr ON mr.id=(SELECT r2.id FROM model_revision r2 WHERE r2.process_model_id=pm.id ORDER BY r2.id DESC LIMIT 1)
          WHERE pm.retired_at IS NULL ORDER BY pm.name''')

    def layout(self,revision_id):
        return {r['entity_identity_id']:r for r in self.rows('SELECT * FROM entity_view_layout WHERE model_revision_id=?',(revision_id,))}
    def save_layout(self,revision_id,identity_id,x,y,width=None,height=None,collapsed=0,z_index=0):
        with self.con:
            self.con.execute('''INSERT INTO entity_view_layout(model_revision_id,entity_identity_id,x,y,width,height,collapsed,z_index)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(model_revision_id,entity_identity_id) DO UPDATE SET
              x=excluded.x,y=excluded.y,width=COALESCE(excluded.width,width),height=COALESCE(excluded.height,height),collapsed=excluded.collapsed,z_index=excluded.z_index''',
              (revision_id,identity_id,float(x),float(y),width,height,1 if collapsed else 0,float(z_index)))

    def definition_properties(self,definition_id):
        return self.rows('''SELECT pd.code,pd.name,pd.value_type,pd.unit,v.value_text,v.value_integer,v.value_real,v.value_boolean
          FROM definition_property_value v JOIN property_definition pd ON pd.id=v.property_definition_id WHERE v.entity_definition_id=?''',(definition_id,))
    def property_value(self,definition_id,code):
        r=self.row('''SELECT pd.value_type,v.value_text,v.value_integer,v.value_real,v.value_boolean FROM property_definition pd
          LEFT JOIN definition_property_value v ON v.property_definition_id=pd.id AND v.entity_definition_id=? WHERE pd.code=? AND pd.workspace_id IS NULL''',(definition_id,code))
        if not r:return None
        for k in ('value_text','value_integer','value_real','value_boolean'):
            if r.get(k) is not None:return r[k]
        return None
    def set_definition_property(self,definition_id,code,value):
        d=self.row('''SELECT ed.id,ei.workspace_id FROM entity_definition ed JOIN entity_identity ei ON ei.id=ed.entity_identity_id WHERE ed.id=?''',(definition_id,))
        if not d: raise ValueError('Definition not found')
        pd=self.row('SELECT id,value_type FROM property_definition WHERE code=? AND (workspace_id IS NULL OR workspace_id=?) ORDER BY workspace_id DESC LIMIT 1',(code,d['workspace_id']))
        if not pd: raise ValueError(f'Unknown property {code}')
        if value is None or str(value).strip()=='':
            with self.con:self.con.execute('DELETE FROM definition_property_value WHERE entity_definition_id=? AND property_definition_id=?',(definition_id,pd['id']))
            return
        cols={'value_text':None,'value_integer':None,'value_real':None,'value_boolean':None}; typ=pd['value_type']
        if typ in ('TEXT','ENUM','DATE','DATETIME','DURATION'): cols['value_text']=str(value)
        elif typ=='INTEGER': cols['value_integer']=int(value)
        elif typ=='NUMBER': cols['value_real']=float(value)
        elif typ=='BOOLEAN': cols['value_boolean']=1 if str(value).lower() in ('1','true','yes','y','critical') else 0
        with self.con:
            self.con.execute('''INSERT INTO definition_property_value(entity_definition_id,property_definition_id,value_text,value_integer,value_real,value_boolean)
              VALUES(?,?,?,?,?,?) ON CONFLICT(entity_definition_id,property_definition_id) DO UPDATE SET value_text=excluded.value_text,value_integer=excluded.value_integer,value_real=excluded.value_real,value_boolean=excluded.value_boolean''',
              (definition_id,pd['id'],cols['value_text'],cols['value_integer'],cols['value_real'],cols['value_boolean']))

    def visual_entities(self,revision_id):
        es=self.entities(revision_id)
        for e in es:
            e['properties']={p['code']:next((p[k] for k in ('value_text','value_integer','value_real','value_boolean') if p.get(k) is not None),None) for p in self.definition_properties(e['definition_id'])}
        return es
    def visual_relations(self,revision_id): return self.relations(revision_id)

    def update_entity_text(self,definition_id,name,description=''):
        r=self.row('''SELECT mr.status FROM model_revision_entity mre JOIN model_revision mr ON mr.id=mre.model_revision_id WHERE mre.entity_definition_id=? ORDER BY mr.id DESC LIMIT 1''',(definition_id,))
        if r and r['status']!='DRAFT': raise ValueError('Clone the published revision before editing.')
        with self.con:self.con.execute('UPDATE entity_definition SET name=?,description=? WHERE id=?',(name.strip(),description.strip() or None,definition_id))

    # ----- overview / analysis read models -----
    def overview(self,revision_id):
        rv=self.row('''SELECT mr.*,pm.name model_name,w.name workspace_name FROM model_revision mr JOIN process_model pm ON pm.id=mr.process_model_id JOIN workspace w ON w.id=pm.workspace_id WHERE mr.id=?''',(revision_id,)) or {}
        rv['entities']=self.row('SELECT COUNT(*) n FROM model_revision_entity WHERE model_revision_id=?',(revision_id,))['n']
        rv['relations']=self.row('SELECT COUNT(*) n FROM model_revision_relation WHERE model_revision_id=?',(revision_id,))['n']
        rv['rules']=self.row('SELECT COUNT(*) n FROM model_revision_rule WHERE model_revision_id=?',(revision_id,))['n']
        rv['parameters']=self.row('SELECT COUNT(*) n FROM model_revision_parameter_value WHERE model_revision_id=?',(revision_id,))['n']
        return rv
    def analysis_summary(self,revision_id):
        entities=self.entities(revision_id); rels=self.relations(revision_id); executions=self.executions_for_revision(revision_id)
        by_type={}
        for e in entities: by_type[e['type_name']]=by_type.get(e['type_name'],0)+1
        return {'entity_count':len(entities),'relation_count':len(rels),'execution_count':len(executions),'by_type':by_type,'rules':len(self.rules(revision_id)),'parameters':len(self.parameters(revision_id))}

from .workspace import WorkspaceFeatures

class AppController(WorkspaceFeatures, LegacyController):
    pass
