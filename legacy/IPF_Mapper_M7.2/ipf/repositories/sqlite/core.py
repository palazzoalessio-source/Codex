from __future__ import annotations
from uuid import uuid4
from datetime import datetime, timezone
from ...domain.models import *
from ...domain.exceptions import NotFoundError

def now(): return datetime.now(timezone.utc).isoformat()
def uid(prefix): return f'{prefix}:{uuid4()}'

class Repo:
    def __init__(self, con): self.con = con
    def one(self, sql, p=()):
        r=self.con.execute(sql,p).fetchone()
        if not r: raise NotFoundError(sql)
        return r

class WorkspaceRepository(Repo):
    def insert(self,name,description=None):
        u=uid('workspace'); c=self.con.execute('INSERT INTO workspace(uid,name,description,created_at) VALUES(?,?,?,?)',(u,name,description,now()))
        return Workspace(c.lastrowid,u,name,description)
    def get(self,id):
        r=self.one('SELECT * FROM workspace WHERE id=?',(id,)); return Workspace(r['id'],r['uid'],r['name'],r['description'])

class CatalogRepository(Repo):
    def entity_type(self, code, workspace_id=None):
        r=self.con.execute('SELECT id,code,parent_type_id FROM entity_type WHERE code=? AND (workspace_id IS NULL OR workspace_id=?) ORDER BY workspace_id DESC LIMIT 1',(code,workspace_id)).fetchone()
        if not r: raise NotFoundError(code)
        return EntityType(r['id'],r['code'],r['parent_type_id'])
    def semantic(self,code,workspace_id=None):
        r=self.con.execute('SELECT * FROM relation_semantic WHERE code=? AND (workspace_id IS NULL OR workspace_id=?) ORDER BY workspace_id DESC LIMIT 1',(code,workspace_id)).fetchone()
        if not r: raise NotFoundError(code)
        return r
    def signatures(self,semantic_id): return self.con.execute('SELECT * FROM relation_signature WHERE relation_semantic_id=?',(semantic_id,)).fetchall()
    def all_types(self): return self.con.execute('SELECT id,parent_type_id FROM entity_type').fetchall()

class EntityRepository(Repo):
    def insert_identity(self,workspace_id,type_id,stable_code=None):
        u=uid('entity'); c=self.con.execute('INSERT INTO entity_identity(uid,workspace_id,entity_type_id,stable_code,created_at) VALUES(?,?,?,?,?)',(u,workspace_id,type_id,stable_code,now()))
        return EntityIdentity(c.lastrowid,u,workspace_id,type_id,stable_code)
    def insert_definition(self,identity_id,name,description=None,origin='MODELED'):
        u=uid('definition'); c=self.con.execute('INSERT INTO entity_definition(uid,entity_identity_id,name,description,origin,created_at) VALUES(?,?,?,?,?,?)',(u,identity_id,name,description,origin,now()))
        return EntityDefinition(c.lastrowid,u,identity_id,name,description,origin)
    def identity(self,id):
        r=self.one('SELECT * FROM entity_identity WHERE id=?',(id,)); return EntityIdentity(r['id'],r['uid'],r['workspace_id'],r['entity_type_id'],r['stable_code'])
    def definition(self,id):
        r=self.one('SELECT * FROM entity_definition WHERE id=?',(id,)); return EntityDefinition(r['id'],r['uid'],r['entity_identity_id'],r['name'],r['description'],r['origin'])

class RelationRepository(Repo):
    def insert(self,workspace_id,semantic_id,source_id,target_id):
        u=uid('relation'); c=self.con.execute('INSERT INTO relation_definition(uid,workspace_id,semantic_id,source_entity_identity_id,target_entity_identity_id,created_at) VALUES(?,?,?,?,?,?)',(u,workspace_id,semantic_id,source_id,target_id,now()))
        return RelationDefinition(c.lastrowid,u,workspace_id,semantic_id,source_id,target_id)
    def get(self,id):
        r=self.one('SELECT * FROM relation_definition WHERE id=?',(id,)); return RelationDefinition(r['id'],r['uid'],r['workspace_id'],r['semantic_id'],r['source_entity_identity_id'],r['target_entity_identity_id'])
    def affected_by_identity(self,identity_id):
        return tuple(r['id'] for r in self.con.execute('SELECT id FROM relation_definition WHERE source_entity_identity_id=? OR target_entity_identity_id=?',(identity_id,identity_id)))

class ModelRepository(Repo):
    def insert_model(self,workspace_id,name,description=None):
        u=uid('model'); c=self.con.execute('INSERT INTO process_model(uid,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)',(u,workspace_id,name,description,now()))
        return ProcessModel(c.lastrowid,u,workspace_id,name)
    def model(self,id):
        r=self.one('SELECT * FROM process_model WHERE id=?',(id,)); return ProcessModel(r['id'],r['uid'],r['workspace_id'],r['name'])
    def insert_revision(self,model_id,code,purpose=None,parent=None):
        u=uid('revision'); c=self.con.execute("INSERT INTO model_revision(uid,process_model_id,parent_revision_id,revision_code,purpose,status,created_at) VALUES(?,?,?,?,?,'DRAFT',?)",(u,model_id,parent,code,purpose,now()))
        return self.revision(c.lastrowid)
    def revision(self,id):
        r=self.one('SELECT * FROM model_revision WHERE id=?',(id,)); return ModelRevision(r['id'],r['uid'],r['process_model_id'],r['parent_revision_id'],r['revision_code'],r['purpose'],RevisionStatus(r['status']))
    def set_status(self,id,status):
        if status==RevisionStatus.PUBLISHED: self.con.execute('UPDATE model_revision SET status=?,published_at=? WHERE id=?',(status.value,now(),id))
        else: self.con.execute('UPDATE model_revision SET status=? WHERE id=?',(status.value,id))
    def add_entity(self,rev,definition): self.con.execute('INSERT INTO model_revision_entity VALUES(?,?)',(rev,definition))
    def remove_entity(self,rev,definition): self.con.execute('DELETE FROM model_revision_entity WHERE model_revision_id=? AND entity_definition_id=?',(rev,definition))
    def add_relation(self,rev,relation): self.con.execute('INSERT INTO model_revision_relation VALUES(?,?)',(rev,relation))
    def remove_relation(self,rev,relation): self.con.execute('DELETE FROM model_revision_relation WHERE model_revision_id=? AND relation_definition_id=?',(rev,relation))
    def definition_for_identity(self,rev,identity):
        r=self.con.execute('''SELECT ed.* FROM model_revision_entity mre JOIN entity_definition ed ON ed.id=mre.entity_definition_id WHERE mre.model_revision_id=? AND ed.entity_identity_id=?''',(rev,identity)).fetchone()
        if not r: raise NotFoundError('definition in revision')
        return EntityDefinition(r['id'],r['uid'],r['entity_identity_id'],r['name'],r['description'],r['origin'])
    def entities(self,rev):
        rows=self.con.execute('''SELECT ei.*, ed.id did,ed.uid duid,ed.name,ed.description,ed.origin FROM model_revision_entity mre JOIN entity_definition ed ON ed.id=mre.entity_definition_id JOIN entity_identity ei ON ei.id=ed.entity_identity_id WHERE mre.model_revision_id=?''',(rev,)).fetchall()
        return tuple((EntityIdentity(r['id'],r['uid'],r['workspace_id'],r['entity_type_id'],r['stable_code']),EntityDefinition(r['did'],r['duid'],r['id'],r['name'],r['description'],r['origin'])) for r in rows)
    def relations(self,rev):
        rows=self.con.execute('SELECT rd.* FROM model_revision_relation mrr JOIN relation_definition rd ON rd.id=mrr.relation_definition_id WHERE mrr.model_revision_id=?',(rev,)).fetchall()
        return tuple(RelationDefinition(r['id'],r['uid'],r['workspace_id'],r['semantic_id'],r['source_entity_identity_id'],r['target_entity_identity_id']) for r in rows)
    def clone_memberships(self,src,dst):
        self.con.execute('INSERT INTO model_revision_entity SELECT ?,entity_definition_id FROM model_revision_entity WHERE model_revision_id=?',(dst,src))
        self.con.execute('INSERT INTO model_revision_relation SELECT ?,relation_definition_id FROM model_revision_relation WHERE model_revision_id=?',(dst,src))
        self.con.execute('INSERT INTO model_revision_rule SELECT ?,rule_definition_id FROM model_revision_rule WHERE model_revision_id=?',(dst,src))
    def snapshot(self,rev):
        rv=self.revision(rev); return RevisionSnapshot(rv,self.model(rv.process_model_id),self.entities(rev),self.relations(rev))

class ExecutionRepository(Repo):
    def insert_context(self,workspace_id,name):
        u=uid('context'); c=self.con.execute('INSERT INTO execution_context(uid,workspace_id,name,created_at) VALUES(?,?,?,?)',(u,workspace_id,name,now())); return ExecutionContext(c.lastrowid,u,workspace_id,name)
    def context(self,id):
        r=self.one('SELECT * FROM execution_context WHERE id=?',(id,)); return ExecutionContext(r['id'],r['uid'],r['workspace_id'],r['name'])
    def insert_execution(self,context_id,revision_id):
        u=uid('execution'); c=self.con.execute('INSERT INTO model_execution(uid,execution_context_id,model_revision_id,created_at) VALUES(?,?,?,?)',(u,context_id,revision_id,now())); return ModelExecution(c.lastrowid,u,context_id,revision_id)
    def insert_instance(self,context_id,definition_id):
        u=uid('instance'); c=self.con.execute('INSERT INTO entity_instance(uid,execution_context_id,entity_definition_id,created_at) VALUES(?,?,?,?)',(u,context_id,definition_id,now())); return EntityInstance(c.lastrowid,u,context_id,definition_id)
    def attach_entity(self,execution_id,instance_id): self.con.execute('INSERT INTO model_execution_entity VALUES(?,?)',(execution_id,instance_id))

class ExpressionRepository(Repo):
    def insert(self, expression):
        from ...domain.expressions import Expression
        u=expression.uid or uid('expression')
        c=self.con.execute('INSERT INTO expression(uid,created_at) VALUES(?,?)',(u,now()))
        eid=c.lastrowid
        def put(node,parent=None,pos=0):
            from ...domain.expressions import LiteralNode,ReferenceNode,OperationNode
            if isinstance(node,LiteralNode):
                t=node.value.type.value; val=node.value.value
                cols={'literal_text':None,'literal_integer':None,'literal_real':None,'literal_boolean':None}
                if t in ('TEXT','ENUM'): cols['literal_text']=str(val)
                elif t=='DATE': cols['literal_text']=val.isoformat() if hasattr(val,'isoformat') else str(val)
                elif t=='DATETIME': cols['literal_text']=val.isoformat() if hasattr(val,'isoformat') else str(val)
                elif t=='DURATION': cols['literal_text']=f'SECONDS:{val.total_seconds()}' if hasattr(val,'total_seconds') else str(val)
                elif t=='INTEGER': cols['literal_integer']=int(val)
                elif t=='NUMBER': cols['literal_real']=float(val)
                elif t=='BOOLEAN': cols['literal_boolean']=1 if val else 0
                cur=self.con.execute('''INSERT INTO expression_node(expression_id,parent_node_id,position,node_kind,literal_type,literal_text,literal_integer,literal_real,literal_boolean) VALUES(?,?,?,'LITERAL',?,?,?,?,?)''',(eid,parent,pos,t,cols['literal_text'],cols['literal_integer'],cols['literal_real'],cols['literal_boolean']))
            elif isinstance(node,ReferenceNode):
                cur=self.con.execute('''INSERT INTO expression_node(expression_id,parent_node_id,position,node_kind,reference_kind,entity_identity_id,property_definition_id,variable_name,reference_scope) VALUES(?,?,?,'REFERENCE',?,?,?,?,?)''',(eid,parent,pos,node.kind.value,node.entity_identity_id,node.property_definition_id,node.variable_name,node.scope.value))
            else:
                cur=self.con.execute("INSERT INTO expression_node(expression_id,parent_node_id,position,node_kind,operation_code) VALUES(?,?,?,'OPERATION',?)",(eid,parent,pos,node.operation_code))
                nid=cur.lastrowid
                for i,ch in enumerate(node.children): put(ch,nid,i)
                return
        put(expression.root)
        return Expression(eid,u,expression.root)
    def get(self,eid):
        from ...domain.expressions import Expression,ValueType,LiteralNode,TypedValue,ReferenceNode,ReferenceKind,ReferenceScope,OperationNode
        e=self.one('SELECT * FROM expression WHERE id=?',(eid,)); rows=self.con.execute('SELECT * FROM expression_node WHERE expression_id=? ORDER BY parent_node_id,position',(eid,)).fetchall()
        children={}
        for r in rows: children.setdefault(r['parent_node_id'],[]).append(r)
        def build(r):
            k=r['node_kind']
            if k=='LITERAL':
                t=ValueType(r['literal_type']); val=r['literal_text'] if r['literal_text'] is not None else r['literal_integer'] if r['literal_integer'] is not None else r['literal_real'] if r['literal_real'] is not None else bool(r['literal_boolean'])
                if r['literal_text'] is not None:
                    from datetime import datetime,date,timedelta
                    if t==ValueType.DATETIME: val=datetime.fromisoformat(val)
                    elif t==ValueType.DATE: val=date.fromisoformat(val)
                    elif t==ValueType.DURATION and val.startswith('SECONDS:'): val=timedelta(seconds=float(val.split(':',1)[1]))
                return LiteralNode(TypedValue(t,val))
            if k=='REFERENCE': return ReferenceNode(ReferenceKind(r['reference_kind']),ReferenceScope(r['reference_scope']),r['entity_identity_id'],r['property_definition_id'],r['variable_name'])
            return OperationNode(r['operation_code'],tuple(build(x) for x in children.get(r['id'],[])))
        roots=children.get(None,[])
        if len(roots)!=1: raise ValueError('Expression must have exactly one root')
        return Expression(e['id'],e['uid'],build(roots[0]))

class RuleRepository(Repo):
    def insert_identity(self,workspace_id,stable_code=None):
        from ...domain.rules import RuleIdentity
        u=uid('rule'); c=self.con.execute('INSERT INTO rule_identity(uid,workspace_id,stable_code,created_at) VALUES(?,?,?,?)',(u,workspace_id,stable_code,now())); return RuleIdentity(c.lastrowid,u,workspace_id,stable_code)
    def insert_definition(self,rule):
        from ...domain.rules import AssertionRuleDefinition,DerivationRuleDefinition
        app=rule.applicability.id if rule.applicability else None; body=rule.body.id
        sem='ASSERTION' if isinstance(rule,AssertionRuleDefinition) else 'DERIVATION'; target_e=target_p=None
        if isinstance(rule,DerivationRuleDefinition): target_e,target_p=rule.target.entity_identity_id,rule.target.property_definition_id
        u=rule.uid or uid('ruledef'); c=self.con.execute('''INSERT INTO rule_definition(uid,rule_identity_id,semantic,name,applicability_expression_id,body_expression_id,target_entity_identity_id,target_property_definition_id,severity,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',(u,rule.identity_id,sem,rule.name,app,body,target_e,target_p,rule.severity,now()))
        return c.lastrowid
    def add_to_revision(self,revision_id,rule_definition_id): self.con.execute('INSERT INTO model_revision_rule VALUES(?,?)',(revision_id,rule_definition_id))
    def get_definition(self,rid,expressions):
        from ...domain.rules import AssertionRuleDefinition,DerivationRuleDefinition,PropertyTarget
        r=self.one('SELECT * FROM rule_definition WHERE id=?',(rid,))
        body=expressions.get(r['body_expression_id']); app=expressions.get(r['applicability_expression_id']) if r['applicability_expression_id'] else None
        if r['semantic']=='ASSERTION': return AssertionRuleDefinition(r['id'],r['uid'],r['rule_identity_id'],r['name'],body,app,r['severity'])
        return DerivationRuleDefinition(r['id'],r['uid'],r['rule_identity_id'],r['name'],PropertyTarget(r['target_entity_identity_id'],r['target_property_definition_id']),body,app,r['severity'])

# Runtime graph helpers are kept here to preserve the compact Milestone repository layout.
def _execution_relation_helpers():
    def insert_relation_instance(self, context_id, semantic_id, source_instance_id, target_instance_id, relation_definition_id=None):
        u=uid('relation-instance')
        c=self.con.execute('''INSERT INTO relation_instance(uid,execution_context_id,semantic_id,source_entity_instance_id,target_entity_instance_id,relation_definition_id,created_at) VALUES(?,?,?,?,?,?,?)''',(u,context_id,semantic_id,source_instance_id,target_instance_id,relation_definition_id,now()))
        return RelationInstance(c.lastrowid,u,context_id,semantic_id,source_instance_id,target_instance_id,relation_definition_id)
    def attach_relation(self, execution_id, relation_instance_id):
        self.con.execute('INSERT INTO model_execution_relation VALUES(?,?)',(execution_id,relation_instance_id))
    def execution_entities(self, execution_id):
        rows=self.con.execute('''SELECT ei.* FROM model_execution_entity mee JOIN entity_instance ei ON ei.id=mee.entity_instance_id WHERE mee.model_execution_id=? ORDER BY ei.id''',(execution_id,)).fetchall()
        return tuple(EntityInstance(r['id'],r['uid'],r['execution_context_id'],r['entity_definition_id']) for r in rows)
    def execution_relations(self, execution_id):
        rows=self.con.execute('''SELECT ri.* FROM model_execution_relation mer JOIN relation_instance ri ON ri.id=mer.relation_instance_id WHERE mer.model_execution_id=? ORDER BY ri.id''',(execution_id,)).fetchall()
        return tuple(RelationInstance(r['id'],r['uid'],r['execution_context_id'],r['semantic_id'],r['source_entity_instance_id'],r['target_entity_instance_id'],r['relation_definition_id']) for r in rows)
    ExecutionRepository.insert_relation_instance=insert_relation_instance
    ExecutionRepository.attach_relation=attach_relation
    ExecutionRepository.execution_entities=execution_entities
    ExecutionRepository.execution_relations=execution_relations
_execution_relation_helpers()
