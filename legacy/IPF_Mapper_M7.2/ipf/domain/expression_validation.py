from __future__ import annotations
from .expressions import *
from .models import ValidationIssue, ValidationReport, Severity

BOOL_OPS={'AND','OR','NOT','IMPLIES'}; CMP={'EQ','NEQ','GT','GTE','LT','LTE'}; NUM={'ADD','SUBTRACT','MULTIPLY','DIVIDE'}
class ExpressionValidator:
    def __init__(self, operations:dict[str,tuple[int,int|None]], property_types:dict[int,ValueType]|None=None):
        self.operations=operations; self.property_types=property_types or {}
    def validate(self,expr:Expression):
        report=ValidationReport(); self._infer(expr.root,report); return report
    def infer_type(self,expr):
        r=ValidationReport(); t=self._infer(expr.root if isinstance(expr,Expression) else expr,r); return t,r
    def _infer(self,n,r):
        if isinstance(n,LiteralNode): return n.value.type
        if isinstance(n,ReferenceNode):
            if n.kind==ReferenceKind.VARIABLE or n.kind==ReferenceKind.CONTEXT: return ValueType.ANY
            if n.kind==ReferenceKind.ENTITY: return ValueType.SET if n.scope==ReferenceScope.INSTANCE else ValueType.INTEGER
            if n.kind==ReferenceKind.PROPERTY:
                if n.entity_identity_id is None or n.property_definition_id is None: r.issues.append(ValidationIssue('REFERENCE_INVALID',Severity.ERROR,'Property reference requires entity and property.','Expression'))
                return self.property_types.get(n.property_definition_id,ValueType.ANY)
        op=n.operation_code
        if op not in self.operations:
            r.issues.append(ValidationIssue('OPERATION_UNKNOWN',Severity.ERROR,f'Unknown operation {op}.','Expression')); return ValueType.UNKNOWN
        lo,hi=self.operations[op]; argc=len(n.children)
        if argc<lo or (hi is not None and argc>hi): r.issues.append(ValidationIssue('OPERATION_ARITY_INVALID',Severity.ERROR,f'{op} received {argc} arguments.','Expression'))
        ct=[self._infer(c,r) for c in n.children]
        if op in BOOL_OPS:
            for t in ct:
                if t not in (ValueType.BOOLEAN,ValueType.ANY,ValueType.UNKNOWN): r.issues.append(ValidationIssue('EXPRESSION_TYPE_INVALID',Severity.ERROR,f'{op} requires BOOLEAN arguments.','Expression'))
            return ValueType.BOOLEAN
        if op in CMP: return ValueType.BOOLEAN
        if op in NUM: return ValueType.NUMBER
        if op=='COUNT':
            if ct and ct[0] not in (ValueType.SET,ValueType.ANY,ValueType.UNKNOWN): r.issues.append(ValidationIssue('EXPRESSION_TYPE_INVALID',Severity.ERROR,'COUNT requires a SET.','Expression'))
            return ValueType.INTEGER
        if op=='EXISTS':
            if ct and ct[0] not in (ValueType.SET,ValueType.ANY,ValueType.UNKNOWN): r.issues.append(ValidationIssue('EXPRESSION_TYPE_INVALID',Severity.ERROR,'EXISTS requires a SET.','Expression'))
            return ValueType.BOOLEAN
        if op in {'ALL','ANY'}:
            if ct and ct[0] not in (ValueType.SET,ValueType.ANY,ValueType.UNKNOWN): r.issues.append(ValidationIssue('EXPRESSION_TYPE_INVALID',Severity.ERROR,f'{op} first argument must be SET.','Expression'))
            if len(ct)>1 and ct[1] not in (ValueType.BOOLEAN,ValueType.ANY,ValueType.UNKNOWN): r.issues.append(ValidationIssue('EXPRESSION_TYPE_INVALID',Severity.ERROR,f'{op} predicate must be BOOLEAN.','Expression'))
            return ValueType.BOOLEAN
        if op=='FILTER':
            if ct and ct[0] not in (ValueType.SET,ValueType.ANY,ValueType.UNKNOWN): r.issues.append(ValidationIssue('EXPRESSION_TYPE_INVALID',Severity.ERROR,'FILTER first argument must be SET.','Expression'))
            if len(ct)>1 and ct[1] not in (ValueType.BOOLEAN,ValueType.ANY,ValueType.UNKNOWN): r.issues.append(ValidationIssue('EXPRESSION_TYPE_INVALID',Severity.ERROR,'FILTER predicate must be BOOLEAN.','Expression'))
            return ValueType.SET
        if op in {'SUM','AVG','MIN','MAX'}: return ValueType.NUMBER
        if op in {'UPSTREAM','DOWNSTREAM','ANCESTORS','DESCENDANTS'}: return ValueType.SET
        if op=='NOW': return ValueType.DATETIME
        if op=='DURATION': return ValueType.DURATION
        if op in {'LATEST','TIME'}: return ValueType.ANY
        return ValueType.ANY
