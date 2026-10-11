from __future__ import annotations
from collections import defaultdict
from itertools import combinations
from ..domain.graph import DirectedGraph, GraphEdge
from ..domain.active import ApplicabilityStatus, RequirementStatus, EnablementStatus
from ..domain.process_analysis import *

class AnalysisEngine:
    """Derives process semantics from explicit rules, active state and observations.

    No business names, thresholds or process-specific policies live here. Geometry is never
    treated as semantic evidence. Results are projections and are not persisted as flags.
    """

    def dependency_graph(self, constraints):
        cs=tuple(constraints)
        nodes=frozenset(x for c in cs for x in (c.prerequisite_identity_id,c.dependent_identity_id))
        edges=tuple(GraphEdge(c.prerequisite_identity_id,c.dependent_identity_id,ref_id=c.rule_definition_id) for c in cs)
        return DirectedGraph(nodes,edges)

    def dependencies(self,constraints,include_transitive=True):
        cs=tuple(constraints); graph=self.dependency_graph(cs); out=[]; direct=set()
        for c in cs:
            key=(c.prerequisite_identity_id,c.dependent_identity_id); direct.add(key)
            out.append(DependencyResult(*key,False,(AnalysisEvidence('ENABLEMENT_RULE',{'rule_definition_id':c.rule_definition_id,'condition':c.condition_label}),)))
        if include_transitive:
            for a in graph.nodes:
                for b in graph.descendants(a):
                    if (a,b) not in direct:
                        out.append(DependencyResult(a,b,True,(AnalysisEvidence('TRANSITIVE_CLOSURE'),)))
        return tuple(sorted(out,key=lambda x:(x.prerequisite_identity_id,x.dependent_identity_id,x.transitive)))

    def sequence(self,left:InstanceInterval,right:InstanceInterval):
        if left.start is None or right.start is None: return SequenceResult(left.instance_id,right.instance_id,SequenceKind.UNKNOWN)
        le=left.end or left.start; re=right.end or right.start
        if le <= right.start: return SequenceResult(left.instance_id,right.instance_id,SequenceKind.BEFORE,right.start-le)
        if re <= left.start: return SequenceResult(left.instance_id,right.instance_id,SequenceKind.AFTER,left.start-re)
        return SequenceResult(left.instance_id,right.instance_id,SequenceKind.OVERLAP)

    def branches(self,constraints,active_projection=None):
        grouped=defaultdict(set)
        for c in constraints: grouped[c.prerequisite_identity_id].add(c.dependent_identity_id)
        out=[]
        for pre,deps in grouped.items():
            if len(deps)<2: continue
            kind=BranchKind.FAN_OUT; evidence=[AnalysisEvidence('COMMON_PREREQUISITE')]
            if active_projection is not None:
                states=[active_projection.by_identity(x) for x in deps]
                states=[x for x in states if x is not None]
                applicable=[x for x in states if x.applicability==ApplicabilityStatus.APPLICABLE]
                if states and len(applicable)<len(states):
                    kind=BranchKind.CONDITIONAL; evidence.append(AnalysisEvidence('APPLICABILITY_PROJECTION'))
                elif states and all(x.requirement==RequirementStatus.REQUIRED for x in states):
                    kind=BranchKind.AND; evidence.append(AnalysisEvidence('ALL_DEPENDENTS_REQUIRED'))
            out.append(BranchResult(pre,tuple(sorted(deps)),kind,tuple(evidence)))
        return tuple(sorted(out,key=lambda x:x.prerequisite_identity_id))

    def potential_parallelism(self,identity_ids,constraints,active_projection,intervals=()):
        """Candidates require an explicit analysis scope plus current applicability/enablement.
        Mere absence of an edge globally is insufficient; identity_ids is the caller-defined common process scope.
        """
        graph=self.dependency_graph(constraints); ids=tuple(sorted(set(identity_ids))); by_identity=defaultdict(list)
        for i in intervals: by_identity[i.identity_id].append(i)
        out=[]
        for a,b in combinations(ids,2):
            sa=active_projection.by_identity(a); sb=active_projection.by_identity(b)
            if not sa or not sb: continue
            eligible=all(s.applicability==ApplicabilityStatus.APPLICABLE and s.requirement!=RequirementStatus.FORBIDDEN and s.enablement==EnablementStatus.ENABLED for s in (sa,sb))
            dependent=(b in graph.descendants(a)) or (a in graph.descendants(b))
            potential=eligible and not dependent
            actual=None
            if by_identity[a] and by_identity[b]:
                actual=any(self.sequence(x,y).kind==SequenceKind.OVERLAP for x in by_identity[a] for y in by_identity[b])
            if potential or actual:
                ev=(AnalysisEvidence('COMMON_ANALYSIS_SCOPE'),AnalysisEvidence('NO_DEPENDENCY_PATH')) if potential else (AnalysisEvidence('OBSERVED_INTERVAL_OVERLAP'),)
                out.append(ParallelismResult(a,b,potential,actual,ev))
        return tuple(out)

    def waiting(self,interval:InstanceInterval,enabled_at):
        if interval.start is None or enabled_at is None: return WaitingResult(interval.instance_id,enabled_at,interval.start,None,Confidence.UNKNOWN)
        wait=interval.start-enabled_at
        if wait.total_seconds()<0: return WaitingResult(interval.instance_id,enabled_at,interval.start,None,Confidence.UNKNOWN)
        return WaitingResult(interval.instance_id,enabled_at,interval.start,wait,Confidence.OBSERVED)

    def cycles(self,constraints):
        graph=self.dependency_graph(constraints); found=set(); out=[]
        for n in graph.nodes:
            if n not in graph.descendants(n):
                # DirectedGraph intentionally excludes origin from descendants; test reachability back manually.
                pass
            for e in graph.outgoing(n):
                if n==e.target or n in graph.descendants(e.target):
                    members=frozenset({n,e.target}|set(graph.descendants(e.target)&graph.ancestors(n)))
                    key=tuple(sorted(members))
                    if key and key not in found: found.add(key); out.append(CycleResult(key))
        return tuple(sorted(out,key=lambda x:x.identity_ids))

    def repeats(self,intervals,corrections=()):
        grouped=defaultdict(list)
        for i in intervals: grouped[i.identity_id].append(i)
        correction_pairs={(c.correcting_instance_id,c.corrected_instance_id):c for c in corrections}
        out=[]
        for identity,xs in grouped.items():
            xs=sorted(xs,key=lambda x:(x.start is None,x.start,x.instance_id)); ids=tuple(x.instance_id for x in xs)
            if len(ids)==1:
                out.append(RepeatResult(identity,ids,RepeatKind.SINGLE)); continue
            evidence=[]; is_rework=False
            for newer in ids:
                for older in ids:
                    c=correction_pairs.get((newer,older))
                    if c:
                        is_rework=True; evidence.append(AnalysisEvidence(c.source,{'correcting_instance_id':newer,'corrected_instance_id':older}))
            kind=RepeatKind.REWORK if is_rework else RepeatKind.ITERATION
            if not is_rework: evidence.append(AnalysisEvidence('MULTIPLE_INSTANCES_NO_CORRECTION_SEMANTIC'))
            out.append(RepeatResult(identity,ids,kind,tuple(evidence)))
        return tuple(sorted(out,key=lambda x:x.identity_id))
