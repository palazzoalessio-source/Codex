from ..domain.exceptions import ImmutableObjectError,ConflictError,ValidationError,WorkspaceMismatchError
from ..domain.models import RevisionStatus,ChangeImpact
from ..domain.validation import ModelValidator

class RevisionService:
    def __init__(self,uow): self.uow=uow
    def _editable(self,revision_id):
        r=self.uow.models.revision(revision_id)
        if not r.is_editable: raise ImmutableObjectError('Published/archived revisions are immutable.')
        return r
    def create_model(self,workspace_id,name,revision_code='v1',purpose='AS_IS'):
        with self.uow as u:
            m=u.models.insert_model(workspace_id,name); r=u.models.insert_revision(m.id,revision_code,purpose); u.commit(); return m,r
    def add_entity(self,revision_id,type_code,name,stable_code=None,description=None):
        with self.uow as u:
            rv=self._editable(revision_id); model=u.models.model(rv.process_model_id); typ=u.catalogs.entity_type(type_code,model.workspace_id)
            ident=u.entities.insert_identity(model.workspace_id,typ.id,stable_code); d=u.entities.insert_definition(ident.id,name,description); u.models.add_entity(revision_id,d.id); u.commit(); return ident,d
    def include_existing_entity(self,revision_id,definition_id):
        with self.uow as u:
            rv=self._editable(revision_id); model=u.models.model(rv.process_model_id); d=u.entities.definition(definition_id); i=u.entities.identity(d.identity_id)
            if i.workspace_id!=model.workspace_id: raise WorkspaceMismatchError()
            try: u.models.definition_for_identity(revision_id,i.id); raise ConflictError('Identity already resolved in revision.')
            except Exception as e:
                if isinstance(e,ConflictError): raise
            u.models.add_entity(revision_id,d.id);u.commit()
    def replace_entity_definition(self,revision_id,identity_id,name,description=None):
        with self.uow as u:
            self._editable(revision_id); old=u.models.definition_for_identity(revision_id,identity_id); new=u.entities.insert_definition(identity_id,name,description if description is not None else old.description,old.origin); u.models.remove_entity(revision_id,old.id);u.models.add_entity(revision_id,new.id);u.commit();return new
    def add_relation(self,revision_id,semantic_code,source_identity_id,target_identity_id):
        with self.uow as u:
            rv=self._editable(revision_id); model=u.models.model(rv.process_model_id); sem=u.catalogs.semantic(semantic_code,model.workspace_id); r=u.relations.insert(model.workspace_id,sem['id'],source_identity_id,target_identity_id);u.models.add_relation(revision_id,r.id);u.commit();return r
    def clone_revision(self,source_id,new_code,purpose=None):
        with self.uow as u:
            src=u.models.revision(source_id); new=u.models.insert_revision(src.process_model_id,new_code,purpose or src.purpose,src.id);u.models.clone_memberships(src.id,new.id);u.commit();return new
    def validate(self,revision_id): return ModelValidator(self.uow).validate(revision_id)
    def publish(self,revision_id):
        with self.uow as u:
            self._editable(revision_id); report=ModelValidator(u).validate(revision_id)
            if not report.is_valid: raise ValidationError(report)
            u.models.set_status(revision_id,RevisionStatus.PUBLISHED);u.commit()
        return report
    def analyze_removal(self,revision_id,identity_id):
        rels=set(self.uow.relations.affected_by_identity(identity_id)); active={r.id for r in self.uow.models.relations(revision_id)}
        # rule impact will be populated once expression/rule engine lands; DB supports it already.
        return ChangeImpact(tuple(sorted(rels & active)),())
    def remove_entity(self,revision_id,identity_id,cascade=False):
        impact=self.analyze_removal(revision_id,identity_id)
        if impact.has_impact and not cascade: raise ConflictError(impact)
        with self.uow as u:
            self._editable(revision_id); d=u.models.definition_for_identity(revision_id,identity_id)
            if cascade:
                for rid in impact.relation_ids: u.models.remove_relation(revision_id,rid)
            u.models.remove_entity(revision_id,d.id);u.commit()
