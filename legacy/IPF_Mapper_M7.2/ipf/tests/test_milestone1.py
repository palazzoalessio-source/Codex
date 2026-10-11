import unittest
from ipf.database.connection import connect,initialize
from ipf.repositories.uow import UnitOfWork
from ipf.services.revision_service import RevisionService
from ipf.services.execution_service import ExecutionService
from ipf.domain.exceptions import ImmutableObjectError,ConflictError

class CoreScenario(unittest.TestCase):
    def setUp(self):
        self.con=connect();initialize(self.con);self.u=UnitOfWork(self.con);self.rs=RevisionService(self.u);self.es=ExecutionService(self.u)
        with self.u as u:
            self.ws=u.workspaces.insert('Energy Dome');u.commit()
        self.model,self.rev=self.rs.create_model(self.ws.id,'Procurement','v1','AS_IS')
    def entity(self,t,n): return self.rs.add_entity(self.rev.id,t,n)

    def test_01_valid_and_invalid_signature(self):
        proc,_=self.entity('INTERNAL_FUNCTION','Procurement'); action,_=self.entity('ACTION','Prepare RFQ'); info,_=self.entity('INFORMATION','Technical Spec')
        self.rs.add_relation(self.rev.id,'PERFORMER',action.id,proc.id);self.rs.add_relation(self.rev.id,'INPUT',action.id,info.id)
        self.assertTrue(self.rs.validate(self.rev.id).is_valid)
        self.rs.add_relation(self.rev.id,'INPUT',action.id,proc.id)
        codes=[x.code for x in self.rs.validate(self.rev.id).errors]
        self.assertIn('RELATION_SIGNATURE_INVALID',codes)

    def test_02_copy_on_write_and_clone(self):
        ident,d1=self.entity('ACTION','Prepare RFQ');self.rs.publish(self.rev.id)
        v2=self.rs.clone_revision(self.rev.id,'v2')
        before=self.u.models.definition_for_identity(v2.id,ident.id);self.assertEqual(before.id,d1.id)
        d2=self.rs.replace_entity_definition(v2.id,ident.id,'Prepare and Validate RFQ')
        self.assertNotEqual(d1.id,d2.id);self.assertEqual(self.u.models.definition_for_identity(self.rev.id,ident.id).name,'Prepare RFQ');self.assertEqual(self.u.models.definition_for_identity(v2.id,ident.id).name,'Prepare and Validate RFQ')

    def test_03_removal_impact(self):
        action,_=self.entity('ACTION','Prepare RFQ');info,_=self.entity('INFORMATION','Technical Spec');r=self.rs.add_relation(self.rev.id,'INPUT',action.id,info.id)
        impact=self.rs.analyze_removal(self.rev.id,info.id);self.assertEqual(impact.relation_ids,(r.id,))
        with self.assertRaises(ConflictError): self.rs.remove_entity(self.rev.id,info.id)
        self.assertEqual(self.u.models.definition_for_identity(self.rev.id,info.id).name,'Technical Spec')

    def test_04_published_revision_is_immutable(self):
        ident,_=self.entity('ACTION','Prepare RFQ');self.rs.publish(self.rev.id)
        with self.assertRaises(ImmutableObjectError): self.rs.replace_entity_definition(self.rev.id,ident.id,'Changed')

    def test_05_shared_runtime_reality(self):
        _,d=self.entity('INFORMATION','Technical Spec');self.rs.publish(self.rev.id); v2=self.rs.clone_revision(self.rev.id,'v2');self.rs.publish(v2.id)
        c=self.es.create_context(self.ws.id,'Amarillo');e1=self.es.start_execution(c.id,self.rev.id);e2=self.es.start_execution(c.id,v2.id);inst=self.es.instantiate_entity(c.id,d.id);self.es.attach_entity(e1.id,inst.id);self.es.attach_entity(e2.id,inst.id)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM entity_instance').fetchone()[0],1);self.assertEqual(self.con.execute('SELECT COUNT(*) FROM model_execution_entity').fetchone()[0],2)

    def test_06_contains_cycle_rejected(self):
        a,_=self.entity('PROCESS_GROUP','A');b,_=self.entity('PROCESS_GROUP','B');c,_=self.entity('PROCESS_GROUP','C')
        self.rs.add_relation(self.rev.id,'CONTAINS',a.id,b.id);self.rs.add_relation(self.rev.id,'CONTAINS',b.id,c.id);self.rs.add_relation(self.rev.id,'CONTAINS',c.id,a.id)
        self.assertIn('ACYCLIC_RELATION_CYCLE',[x.code for x in self.rs.validate(self.rev.id).errors])

    def test_07_transaction_rollback(self):
        before=self.con.execute('SELECT COUNT(*) FROM entity_identity').fetchone()[0]
        try:
            with self.u as u:
                t=u.catalogs.entity_type('ACTION',self.ws.id);u.entities.insert_identity(self.ws.id,t.id,'DUP');u.entities.insert_identity(self.ws.id,t.id,'DUP');u.commit()
        except Exception: pass
        after=self.con.execute('SELECT COUNT(*) FROM entity_identity').fetchone()[0];self.assertEqual(before,after)

    def test_08_clone_does_not_duplicate_definitions(self):
        self.entity('ACTION','A');self.entity('INFORMATION','I');before=self.con.execute('SELECT COUNT(*) FROM entity_definition').fetchone()[0];v2=self.rs.clone_revision(self.rev.id,'v2');after=self.con.execute('SELECT COUNT(*) FROM entity_definition').fetchone()[0]
        self.assertEqual(before,after);self.assertEqual(len(self.u.models.entities(v2.id)),2)

if __name__=='__main__': unittest.main()
