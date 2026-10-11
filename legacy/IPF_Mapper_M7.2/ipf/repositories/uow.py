from .sqlite.core import WorkspaceRepository,CatalogRepository,EntityRepository,RelationRepository,ModelRepository,ExecutionRepository,ExpressionRepository,RuleRepository
class UnitOfWork:
    def __init__(self,con):
        self.con=con
        self.workspaces=WorkspaceRepository(con); self.catalogs=CatalogRepository(con); self.entities=EntityRepository(con); self.relations=RelationRepository(con); self.models=ModelRepository(con); self.executions=ExecutionRepository(con); self.expressions=ExpressionRepository(con); self.rules=RuleRepository(con)
    def __enter__(self): self.con.execute('BEGIN'); return self
    def commit(self): self.con.commit()
    def rollback(self): self.con.rollback()
    def __exit__(self,t,v,tb):
        if t: self.rollback()
        elif self.con.in_transaction: self.rollback()
