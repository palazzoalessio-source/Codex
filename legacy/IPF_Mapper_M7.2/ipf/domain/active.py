from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

class ModelPresence(str,Enum): MODELED='MODELED'; AD_HOC='AD_HOC'
class ApplicabilityStatus(str,Enum): APPLICABLE='APPLICABLE'; NOT_APPLICABLE='NOT_APPLICABLE'; UNKNOWN='UNKNOWN'; CONFLICT='CONFLICT'; NOT_MODELED='NOT_MODELED'
class RequirementStatus(str,Enum): REQUIRED='REQUIRED'; OPTIONAL='OPTIONAL'; FORBIDDEN='FORBIDDEN'; NOT_APPLICABLE='NOT_APPLICABLE'; UNKNOWN='UNKNOWN'; CONFLICT='CONFLICT'; NOT_MODELED='NOT_MODELED'
class EnablementStatus(str,Enum): ENABLED='ENABLED'; BLOCKED='BLOCKED'; NOT_APPLICABLE='NOT_APPLICABLE'; UNKNOWN='UNKNOWN'; CONFLICT='CONFLICT'; NOT_MODELED='NOT_MODELED'
class RealizationStatus(str,Enum): NOT_REALIZED='NOT_REALIZED'; REALIZED='REALIZED'; MULTIPLE='MULTIPLE'; UNKNOWN='UNKNOWN'
class RulePurpose(str,Enum): GENERAL='GENERAL'; APPLICABILITY='APPLICABILITY'; REQUIREMENT='REQUIREMENT'; ENABLEMENT='ENABLEMENT'

@dataclass(frozen=True)
class StateEvidence:
    source:str; result:Any; rule_definition_id:int|None=None; details:dict=field(default_factory=dict)
@dataclass(frozen=True)
class ElementState:
    identity_id:int; presence:ModelPresence; applicability:ApplicabilityStatus; requirement:RequirementStatus; enablement:EnablementStatus; realization:RealizationStatus; instance_ids:tuple[int,...]=(); evidence:tuple[StateEvidence,...]=()
@dataclass(frozen=True)
class ActiveProjection:
    at_time:Any; elements:tuple[ElementState,...]
    def by_identity(self, identity_id:int): return next((x for x in self.elements if x.identity_id==identity_id),None)
    @property
    def actionable(self): return tuple(x for x in self.elements if x.applicability==ApplicabilityStatus.APPLICABLE and x.requirement!=RequirementStatus.FORBIDDEN and x.enablement==EnablementStatus.ENABLED)

@dataclass(frozen=True)
class StateRule:
    identity_id:int; purpose:RulePurpose; evaluate:Callable[[Any],Any]; rule_definition_id:int|None=None

class ActiveStateResolver:
    """Pure projection engine. Business facts and thresholds arrive through ctx/rules; none are hard-coded."""
    def resolve(self, modeled_identity_ids, ctx, rules=(), at_time=None):
        modeled=set(modeled_identity_ids); runtime=set(ctx.instances_by_identity); ids=sorted(modeled|runtime); out=[]
        grouped={}
        for r in rules: grouped.setdefault((r.identity_id,r.purpose),[]).append(r)
        for iid in ids:
            inst=tuple(ctx.instances_by_identity.get(iid,()))
            real=RealizationStatus.NOT_REALIZED if not inst else RealizationStatus.REALIZED if len(inst)==1 else RealizationStatus.MULTIPLE
            if iid not in modeled:
                out.append(ElementState(iid,ModelPresence.AD_HOC,ApplicabilityStatus.NOT_MODELED,RequirementStatus.NOT_MODELED,EnablementStatus.NOT_MODELED,real,inst)); continue
            ev=[]
            app=self._resolve(grouped.get((iid,RulePurpose.APPLICABILITY),()),ctx,ApplicabilityStatus.APPLICABLE,ApplicabilityStatus)
            ev += app[1]
            if app[0]==ApplicabilityStatus.NOT_APPLICABLE:
                req=RequirementStatus.NOT_APPLICABLE; ena=EnablementStatus.NOT_APPLICABLE
            elif app[0] in (ApplicabilityStatus.UNKNOWN,ApplicabilityStatus.CONFLICT):
                req=RequirementStatus.UNKNOWN; ena=EnablementStatus.UNKNOWN
            else:
                reqr=self._resolve(grouped.get((iid,RulePurpose.REQUIREMENT),()),ctx,RequirementStatus.OPTIONAL,RequirementStatus); req=reqr[0]; ev+=reqr[1]
                if req==RequirementStatus.FORBIDDEN: ena=EnablementStatus.NOT_APPLICABLE
                elif req in (RequirementStatus.UNKNOWN,RequirementStatus.CONFLICT): ena=EnablementStatus.UNKNOWN
                else:
                    enar=self._resolve(grouped.get((iid,RulePurpose.ENABLEMENT),()),ctx,EnablementStatus.ENABLED,EnablementStatus); ena=enar[0]; ev+=enar[1]
            out.append(ElementState(iid,ModelPresence.MODELED,app[0],req,ena,real,inst,tuple(ev)))
        return ActiveProjection(at_time,tuple(out))
    def _resolve(self,rules,ctx,default,enum_cls):
        if not rules:return default,[]
        vals=[]; ev=[]; unknown=False
        for r in rules:
            try:v=r.evaluate(ctx)
            except Exception:v=None
            if v is None or getattr(v,'value',v)=='UNKNOWN': unknown=True; ev.append(StateEvidence('RULE','UNKNOWN',r.rule_definition_id)); continue
            try:v=enum_cls(getattr(v,'value',v))
            except Exception: unknown=True; ev.append(StateEvidence('RULE','UNKNOWN',r.rule_definition_id)); continue
            vals.append(v); ev.append(StateEvidence('RULE',v.value,r.rule_definition_id))
        if unknown:return enum_cls.UNKNOWN,ev
        uniq=set(vals)
        if len(uniq)>1:return enum_cls.CONFLICT,ev
        return (vals[0] if vals else default),ev
