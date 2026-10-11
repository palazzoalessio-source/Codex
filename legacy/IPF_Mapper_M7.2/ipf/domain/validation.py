from .models import ValidationIssue,ValidationReport,Severity

class TypeSystem:
    def __init__(self, rows): self.parent={r['id']:r['parent_type_id'] for r in rows}
    def is_same_or_subtype(self,actual,expected):
        seen=set()
        while actual is not None and actual not in seen:
            if actual==expected:return True
            seen.add(actual); actual=self.parent.get(actual)
        return False

class ModelValidator:
    def __init__(self,uow): self.uow=uow
    def validate(self,revision_id):
        s=self.uow.models.snapshot(revision_id); report=ValidationReport(); byid={i.id:(i,d) for i,d in s.entities}; types=TypeSystem(self.uow.catalogs.all_types())
        # duplicate identity resolution
        ids=[i.id for i,_ in s.entities]
        if len(ids)!=len(set(ids)): report.issues.append(ValidationIssue('MULTIPLE_DEFINITIONS_FOR_IDENTITY',Severity.ERROR,'More than one definition of an identity is included in the revision.'))
        # workspace consistency
        for i,_ in s.entities:
            if i.workspace_id!=s.model.workspace_id: report.issues.append(ValidationIssue('WORKSPACE_MISMATCH',Severity.ERROR,'Entity belongs to another workspace.','ENTITY',i.uid))
        # relation endpoint + signature + workspace
        for r in s.relations:
            if r.workspace_id!=s.model.workspace_id: report.issues.append(ValidationIssue('WORKSPACE_MISMATCH',Severity.ERROR,'Relation belongs to another workspace.','RELATION',r.uid)); continue
            if r.source_identity_id not in byid or r.target_identity_id not in byid:
                report.issues.append(ValidationIssue('RELATION_ENDPOINT_NOT_IN_REVISION',Severity.ERROR,'Relation endpoint is not included in the revision.','RELATION',r.uid)); continue
            st=byid[r.source_identity_id][0].entity_type_id; tt=byid[r.target_identity_id][0].entity_type_id
            sigs=self.uow.catalogs.signatures(r.semantic_id)
            if not any(types.is_same_or_subtype(st,x['source_entity_type_id']) and types.is_same_or_subtype(tt,x['target_entity_type_id']) for x in sigs):
                report.issues.append(ValidationIssue('RELATION_SIGNATURE_INVALID',Severity.ERROR,'Relation source/target types are incompatible with its semantic.','RELATION',r.uid))
        # cycles for acyclic semantics
        sem_ids={r.semantic_id for r in s.relations}
        for sem in sem_ids:
            sr=self.uow.con.execute('SELECT is_acyclic FROM relation_semantic WHERE id=?',(sem,)).fetchone()
            if not sr or not sr['is_acyclic']: continue
            adj={}
            for r in s.relations:
                if r.semantic_id==sem: adj.setdefault(r.source_identity_id,[]).append(r.target_identity_id)
            visiting=set(); done=set()
            def dfs(n):
                if n in visiting:return True
                if n in done:return False
                visiting.add(n)
                for m in adj.get(n,[]):
                    if dfs(m):return True
                visiting.remove(n);done.add(n);return False
            if any(dfs(n) for n in list(adj) if n not in done): report.issues.append(ValidationIssue('ACYCLIC_RELATION_CYCLE',Severity.ERROR,'Cycle detected for an acyclic relation semantic.'))
        return report
