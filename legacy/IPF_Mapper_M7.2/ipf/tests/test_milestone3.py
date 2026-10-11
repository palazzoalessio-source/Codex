import unittest
from ipf.database.connection import connect,initialize
from ipf.repositories.uow import UnitOfWork
from ipf.services.revision_service import RevisionService
from ipf.services.execution_service import ExecutionService
from ipf.engines.graph_engine import GraphEngine
from ipf.engines.binding_engine import BindingEngine
from ipf.engines.expression_engine import ExpressionEngine
from ipf.domain.expressions import *
from ipf.domain.graph import DirectedGraph,GraphEdge


def expr(root): return Expression(None,'',root)
def lit(t,v): return LiteralNode(TypedValue(t,v))

class M3(unittest.TestCase):
    def setUp(self):
        self.con=connect();initialize(self.con);self.u=UnitOfWork(self.con)
        self.rs=RevisionService(self.u);self.es=ExecutionService(self.u);self.ge=GraphEngine();self.ee=ExpressionEngine()
        with self.u as u: self.ws=u.workspaces.insert('W');u.commit()
        self.model,self.rev=self.rs.create_model(self.ws.id,'P')

    def add(self,t,n): return self.rs.add_entity(self.rev.id,t,n)

    def test_potential_graph_is_definition_projection(self):
        g,_=self.add('PROCESS_GROUP','G');a,_=self.add('ACTION','A');i,_=self.add('INFORMATION','I')
        self.rs.add_relation(self.rev.id,'CONTAINS',g.id,a.id);self.rs.add_relation(self.rev.id,'OUTPUT',a.id,i.id)
        graph=self.ge.potential(self.u.models.snapshot(self.rev.id))
        self.assertEqual(graph.nodes,{g.id,a.id,i.id});self.assertEqual(len(graph.edges),2)

    def test_graph_queries_are_generic_and_not_persisted(self):
        graph=DirectedGraph(frozenset({1,2,3,4}),(GraphEdge(1,2),GraphEdge(2,3),GraphEdge(1,4)))
        self.assertEqual(graph.downstream(1),{2,4});self.assertEqual(graph.descendants(1),{2,3,4});self.assertEqual(graph.ancestors(3),{1,2})
        ctx=EvaluationContext({}, {}, {}, {}, {}, {}, graph=graph)
        e=expr(OperationNode('DESCENDANTS',(lit(ValueType.INTEGER,1),)))
        self.assertEqual(set(self.ee.evaluate(e,ctx)),{2,3,4})

    def _runtime(self):
        a,ad=self.add('ACTION','A');self.rs.publish(self.rev.id);c=self.es.create_context(self.ws.id,'C');ex=self.es.start_execution(c.id,self.rev.id)
        i1=self.es.instantiate_entity(c.id,ad.id);self.es.attach_entity(ex.id,i1.id)
        return a,ad,c,ex,i1

    def test_binding_unique_instance_resolves_scalar_property(self):
        a,ad,c,ex,i1=self._runtime()
        self.con.execute('INSERT INTO instance_property_value(entity_instance_id,property_definition_id,value_text) VALUES(?,?,?)',(i1.id,4,'COMPLETE'));self.con.commit()
        ctx=BindingEngine(self.con).for_execution(ex.id)
        r=ReferenceNode(ReferenceKind.PROPERTY,ReferenceScope.INSTANCE,a.id,4)
        self.assertEqual(self.ee.evaluate(expr(r),ctx),'COMPLETE')

    def test_multiple_instances_do_not_get_magic_current_selection(self):
        a,ad,c,ex,i1=self._runtime();i2=self.es.instantiate_entity(c.id,ad.id);self.es.attach_entity(ex.id,i2.id)
        for iid,status in [(i1.id,'COMPLETE'),(i2.id,'IN_PROGRESS')]: self.con.execute('INSERT INTO instance_property_value(entity_instance_id,property_definition_id,value_text) VALUES(?,?,?)',(iid,4,status))
        self.con.commit();ctx=BindingEngine(self.con).for_execution(ex.id)
        self.assertNotIn(a.id,ctx.current_instance_by_identity)
        r=ReferenceNode(ReferenceKind.PROPERTY,ReferenceScope.INSTANCE,a.id,4)
        self.assertEqual(self.ee.evaluate(expr(r),ctx),TruthValue.UNKNOWN)

    def test_any_all_bind_each_instance_explicitly(self):
        a,ad,c,ex,i1=self._runtime();i2=self.es.instantiate_entity(c.id,ad.id);self.es.attach_entity(ex.id,i2.id)
        for iid,status in [(i1.id,'COMPLETE'),(i2.id,'IN_PROGRESS')]: self.con.execute('INSERT INTO instance_property_value(entity_instance_id,property_definition_id,value_text) VALUES(?,?,?)',(iid,4,status))
        self.con.commit();ctx=BindingEngine(self.con).for_execution(ex.id)
        source=ReferenceNode(ReferenceKind.ENTITY,ReferenceScope.INSTANCE,a.id)
        status=ReferenceNode(ReferenceKind.PROPERTY,ReferenceScope.INSTANCE,a.id,4)
        pred=OperationNode('EQ',(status,lit(ValueType.ENUM,'COMPLETE')))
        self.assertEqual(self.ee.evaluate(expr(OperationNode('ANY',(source,pred))),ctx),TruthValue.TRUE)
        self.assertEqual(self.ee.evaluate(expr(OperationNode('ALL',(source,pred))),ctx),TruthValue.FALSE)

    def test_filter_propagates_unknown_membership(self):
        a,ad,c,ex,i1=self._runtime();i2=self.es.instantiate_entity(c.id,ad.id);self.es.attach_entity(ex.id,i2.id)
        self.con.execute('INSERT INTO instance_property_value(entity_instance_id,property_definition_id,value_text) VALUES(?,?,?)',(i1.id,4,'COMPLETE'));self.con.commit()
        ctx=BindingEngine(self.con).for_execution(ex.id);source=ReferenceNode(ReferenceKind.ENTITY,ReferenceScope.INSTANCE,a.id);status=ReferenceNode(ReferenceKind.PROPERTY,ReferenceScope.INSTANCE,a.id,4)
        pred=OperationNode('EQ',(status,lit(ValueType.ENUM,'COMPLETE')))
        self.assertEqual(self.ee.evaluate(expr(OperationNode('FILTER',(source,pred))),ctx),TruthValue.UNKNOWN)

    def test_realized_graph_uses_instances_and_observed_relations(self):
        a,ad=self.add('ACTION','A');i,idf=self.add('INFORMATION','I');rd=self.rs.add_relation(self.rev.id,'OUTPUT',a.id,i.id);self.rs.publish(self.rev.id)
        c=self.es.create_context(self.ws.id,'C');ex=self.es.start_execution(c.id,self.rev.id);ai=self.es.instantiate_entity(c.id,ad.id);ii=self.es.instantiate_entity(c.id,idf.id);self.es.attach_entity(ex.id,ai.id);self.es.attach_entity(ex.id,ii.id)
        ri=self.es.instantiate_relation(ex.id,rd.semantic_id,ai.id,ii.id,rd.id)
        graph=self.ge.realized(self.u.executions.execution_entities(ex.id),self.u.executions.execution_relations(ex.id))
        self.assertEqual(graph.nodes,{ai.id,ii.id});self.assertEqual(graph.edges[0].ref_id,ri.id);self.assertEqual(graph.downstream(ai.id),{ii.id})

    def test_active_is_projection_not_inference(self):
        graph=DirectedGraph(frozenset({1,2,3}),(GraphEdge(1,2),GraphEdge(2,3)))
        active=self.ge.active(graph,{1,2})
        self.assertEqual(active.nodes,{1,2});self.assertEqual(len(active.edges),1)
        # GraphEngine deliberately has no rule-based guess for active nodes.
        self.assertFalse(hasattr(self.ge,'infer_active'))

if __name__=='__main__': unittest.main()
