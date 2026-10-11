from __future__ import annotations
from dataclasses import replace
from datetime import datetime
from functools import reduce
from operator import mul
from ..domain.expressions import *

UNKNOWN=TruthValue.UNKNOWN

def tv(v): return TruthValue.from_value(v)
def and2(a,b):
    a,b=tv(a),tv(b)
    if TruthValue.FALSE in (a,b): return TruthValue.FALSE
    if TruthValue.UNKNOWN in (a,b): return TruthValue.UNKNOWN
    return TruthValue.TRUE
def or2(a,b):
    a,b=tv(a),tv(b)
    if TruthValue.TRUE in (a,b): return TruthValue.TRUE
    if TruthValue.UNKNOWN in (a,b): return TruthValue.UNKNOWN
    return TruthValue.FALSE

class ExpressionEngine:
    def evaluate(self, expr:Expression|ExpressionNode, ctx:EvaluationContext):
        node=expr.root if isinstance(expr,Expression) else expr
        if isinstance(node,LiteralNode): return node.value.value
        if isinstance(node,ReferenceNode): return self._ref(node,ctx)
        if node.operation_code in {'FILTER','ANY','ALL'}:
            return self._set_special(node,ctx)
        vals=[self.evaluate(c,ctx) for c in node.children]
        return self._op(node.operation_code,vals,ctx)

    def _ref(self,n,ctx):
        if n.kind==ReferenceKind.VARIABLE: return ctx.variables.get(n.variable_name, UNKNOWN)
        if n.kind==ReferenceKind.CONTEXT: return ctx.context_values.get(n.variable_name or '', UNKNOWN)
        if n.kind==ReferenceKind.ENTITY:
            xs=ctx.instances_by_identity.get(n.entity_identity_id,())
            return xs if n.scope==ReferenceScope.INSTANCE else n.entity_identity_id
        if n.kind==ReferenceKind.PROPERTY:
            if n.scope==ReferenceScope.DEFINITION: return ctx.definition_properties.get((n.entity_identity_id,n.property_definition_id),UNKNOWN)
            iid=ctx.current_instance_by_identity.get(n.entity_identity_id)
            return UNKNOWN if iid is None else ctx.instance_properties.get((iid,n.property_definition_id),UNKNOWN)
        return UNKNOWN

    def _context_for_item(self,ctx,item):
        # Binding is explicit. '$item' is always available. If the item is an entity instance,
        # the binder may provide its identity through the reserved map in context_values.
        variables=dict(ctx.variables); variables['item']=item
        current=dict(ctx.current_instance_by_identity)
        identity_map=ctx.context_values.get('__instance_identity__',{})
        identity_id=identity_map.get(item) if isinstance(identity_map,dict) else None
        if identity_id is not None: current[identity_id]=item
        return replace(ctx,variables=variables,current_instance_by_identity=current)

    def _set_special(self,node,ctx):
        source=self.evaluate(node.children[0],ctx)
        if source is UNKNOWN: return UNKNOWN
        items=tuple(source)
        predicate=node.children[1]
        if node.operation_code=='FILTER':
            out=[]; unknown=False
            for item in items:
                r=tv(self.evaluate(predicate,self._context_for_item(ctx,item)))
                if r==TruthValue.TRUE: out.append(item)
                elif r==TruthValue.UNKNOWN: unknown=True
            # A filter with uncertain membership is itself uncertain; do not silently drop unknown items.
            return UNKNOWN if unknown else tuple(out)
        if node.operation_code=='ANY':
            result=TruthValue.FALSE
            for item in items:
                result=or2(result,self.evaluate(predicate,self._context_for_item(ctx,item)))
                if result==TruthValue.TRUE: break
            return result
        if node.operation_code=='ALL':
            result=TruthValue.TRUE
            for item in items:
                result=and2(result,self.evaluate(predicate,self._context_for_item(ctx,item)))
                if result==TruthValue.FALSE: break
            return result
        raise ValueError(node.operation_code)

    def _op(self,op,v,ctx):
        if op=='AND': return reduce(and2,v,TruthValue.TRUE)
        if op=='OR': return reduce(or2,v,TruthValue.FALSE)
        if op=='NOT':
            x=tv(v[0]); return UNKNOWN if x==UNKNOWN else (TruthValue.FALSE if x==TruthValue.TRUE else TruthValue.TRUE)
        if op=='IMPLIES': return or2(self._op('NOT',[v[0]],ctx),v[1])
        if op in {'EQ','NEQ','GT','GTE','LT','LTE'}:
            if UNKNOWN in v: return UNKNOWN
            f={'EQ':lambda a,b:a==b,'NEQ':lambda a,b:a!=b,'GT':lambda a,b:a>b,'GTE':lambda a,b:a>=b,'LT':lambda a,b:a<b,'LTE':lambda a,b:a<=b}[op]
            return TruthValue.TRUE if f(v[0],v[1]) else TruthValue.FALSE
        if op=='ADD': return UNKNOWN if UNKNOWN in v else sum(v)
        if op=='SUBTRACT': return UNKNOWN if UNKNOWN in v else v[0]-v[1]
        if op=='MULTIPLY': return UNKNOWN if UNKNOWN in v else reduce(mul,v,1)
        if op=='DIVIDE': return UNKNOWN if UNKNOWN in v or v[1]==0 else v[0]/v[1]
        if op=='COUNT': return UNKNOWN if v[0] is UNKNOWN else len(v[0])
        if op=='EXISTS': return UNKNOWN if v[0] is UNKNOWN else (TruthValue.TRUE if len(v[0])>0 else TruthValue.FALSE)
        if op=='SUM': return UNKNOWN if v[0] is UNKNOWN else sum(v[0])
        if op=='AVG': return UNKNOWN if v[0] is UNKNOWN or not v[0] else sum(v[0])/len(v[0])
        if op=='MIN': return UNKNOWN if v[0] is UNKNOWN or not v[0] else min(v[0])
        if op=='MAX': return UNKNOWN if v[0] is UNKNOWN or not v[0] else max(v[0])
        if op=='LATEST': return UNKNOWN if v[0] is UNKNOWN or not v[0] else v[0][-1]
        if op=='NOW': return ctx.now if ctx.now is not None else datetime.now().astimezone()
        if op=='DURATION': return UNKNOWN if UNKNOWN in v else v[1]-v[0]
        if op=='TIME': return v[0]
        if op in {'UPSTREAM','DOWNSTREAM','ANCESTORS','DESCENDANTS'}:
            if ctx.graph is None or v[0] is UNKNOWN: return UNKNOWN
            fn=getattr(ctx.graph,op.lower())
            return tuple(fn(v[0]))
        raise ValueError(f'Operation not executable: {op}')
