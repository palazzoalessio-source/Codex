from __future__ import annotations
from datetime import date, datetime, timedelta
from ..domain.expressions import EvaluationContext

class BindingEngine:
    """Builds an EvaluationContext from persisted definition/runtime facts.

    Multiple instances of the same identity are preserved as a set. A scalar property
    reference is bound automatically only when exactly one relevant instance exists;
    otherwise it remains unresolved unless FILTER/ANY/ALL establishes an item binding.
    """
    def __init__(self, con): self.con=con

    def for_execution(self, model_execution_id:int, *, context_values=None, variables=None, now=None, graph=None):
        ex=self.con.execute('SELECT * FROM model_execution WHERE id=?',(model_execution_id,)).fetchone()
        if not ex: raise KeyError(model_execution_id)
        rev=ex['model_revision_id']; ctxid=ex['execution_context_id']

        rows=self.con.execute('''
            SELECT ei.id instance_id, ed.entity_identity_id identity_id
            FROM model_execution_entity mee
            JOIN entity_instance ei ON ei.id=mee.entity_instance_id
            JOIN entity_definition ed ON ed.id=ei.entity_definition_id
            WHERE mee.model_execution_id=?
            ORDER BY ei.id
        ''',(model_execution_id,)).fetchall()
        by_identity={}; instance_identity={}
        for r in rows:
            by_identity.setdefault(r['identity_id'],[]).append(r['instance_id'])
            instance_identity[r['instance_id']]=r['identity_id']
        by_identity={k:tuple(v) for k,v in by_identity.items()}
        current={k:v[0] for k,v in by_identity.items() if len(v)==1}

        instance_props={}
        prop_rows=self.con.execute('''
            SELECT ipv.*, pd.value_type
            FROM instance_property_value ipv
            JOIN property_definition pd ON pd.id=ipv.property_definition_id
            JOIN model_execution_entity mee ON mee.entity_instance_id=ipv.entity_instance_id
            WHERE mee.model_execution_id=?
        ''',(model_execution_id,)).fetchall()
        for r in prop_rows:
            instance_props[(r['entity_instance_id'],r['property_definition_id'])]=self._decode(r)

        definition_props={}
        def_rows=self.con.execute('''
            SELECT dpv.*, pd.value_type, ed.entity_identity_id
            FROM definition_property_value dpv
            JOIN property_definition pd ON pd.id=dpv.property_definition_id
            JOIN entity_definition ed ON ed.id=dpv.entity_definition_id
            JOIN model_revision_entity mre ON mre.entity_definition_id=ed.id
            WHERE mre.model_revision_id=?
        ''',(rev,)).fetchall()
        for r in def_rows:
            definition_props[(r['entity_identity_id'],r['property_definition_id'])]=self._decode(r)

        cv=dict(context_values or {}); cv['__instance_identity__']=instance_identity
        return EvaluationContext(definition_props,instance_props,cv,dict(variables or {}),by_identity,current,now,graph)

    @staticmethod
    def _decode(r):
        raw=r['value_text'] if r['value_text'] is not None else r['value_integer'] if r['value_integer'] is not None else r['value_real'] if r['value_real'] is not None else bool(r['value_boolean'])
        t=r['value_type']
        if t=='DATETIME' and isinstance(raw,str): return datetime.fromisoformat(raw)
        if t=='DATE' and isinstance(raw,str): return date.fromisoformat(raw)
        if t=='DURATION' and isinstance(raw,str) and raw.startswith('SECONDS:'): return timedelta(seconds=float(raw.split(':',1)[1]))
        return raw
