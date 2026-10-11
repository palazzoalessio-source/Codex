from ..domain.exceptions import ValidationError,WorkspaceMismatchError
from ..domain.models import RevisionStatus
class ExecutionService:
    def __init__(self,uow): self.uow=uow
    def create_context(self,workspace_id,name):
        with self.uow as u:
            c=u.executions.insert_context(workspace_id,name);u.commit();return c
    def start_execution(self,context_id,revision_id):
        with self.uow as u:
            c=u.executions.context(context_id);r=u.models.revision(revision_id);m=u.models.model(r.process_model_id)
            if c.workspace_id!=m.workspace_id: raise WorkspaceMismatchError()
            if r.status!=RevisionStatus.PUBLISHED: raise ValidationError('Only published revisions can execute.')
            e=u.executions.insert_execution(context_id,revision_id);u.commit();return e
    def instantiate_entity(self,context_id,definition_id):
        with self.uow as u:
            i=u.executions.insert_instance(context_id,definition_id);u.commit();return i
    def attach_entity(self,execution_id,instance_id):
        with self.uow as u:
            er=u.con.execute('SELECT execution_context_id FROM model_execution WHERE id=?',(execution_id,)).fetchone(); ir=u.con.execute('SELECT execution_context_id FROM entity_instance WHERE id=?',(instance_id,)).fetchone()
            if not er or not ir or er[0]!=ir[0]: raise WorkspaceMismatchError('Execution context mismatch.')
            u.executions.attach_entity(execution_id,instance_id);u.commit()
    def instantiate_relation(self,execution_id,semantic_id,source_instance_id,target_instance_id,relation_definition_id=None):
        with self.uow as u:
            er=u.con.execute('SELECT execution_context_id FROM model_execution WHERE id=?',(execution_id,)).fetchone()
            s=u.con.execute('SELECT execution_context_id FROM entity_instance WHERE id=?',(source_instance_id,)).fetchone()
            t=u.con.execute('SELECT execution_context_id FROM entity_instance WHERE id=?',(target_instance_id,)).fetchone()
            if not er or not s or not t or not (er[0]==s[0]==t[0]): raise WorkspaceMismatchError('Relation instance context mismatch.')
            ri=u.executions.insert_relation_instance(er[0],semantic_id,source_instance_id,target_instance_id,relation_definition_id)
            u.executions.attach_relation(execution_id,ri.id);u.commit();return ri
