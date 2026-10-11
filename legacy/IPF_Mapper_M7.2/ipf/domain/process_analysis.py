from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

class Confidence(str, Enum):
    PROVEN='PROVEN'; OBSERVED='OBSERVED'; CANDIDATE='CANDIDATE'; UNKNOWN='UNKNOWN'
class SequenceKind(str, Enum):
    BEFORE='BEFORE'; OVERLAP='OVERLAP'; AFTER='AFTER'; UNKNOWN='UNKNOWN'
class BranchKind(str, Enum):
    AND='AND'; CONDITIONAL='CONDITIONAL'; FAN_OUT='FAN_OUT'; UNKNOWN='UNKNOWN'
class RepeatKind(str, Enum):
    SINGLE='SINGLE'; ITERATION='ITERATION'; REWORK='REWORK'; UNKNOWN='UNKNOWN'

@dataclass(frozen=True)
class AnalysisEvidence:
    source:str
    details:dict[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class DependencyConstraint:
    """A semantic operational constraint: dependent is blocked until prerequisite is satisfied.
    It is produced from configured model rules/templates, never inferred from drawing geometry.
    """
    prerequisite_identity_id:int
    dependent_identity_id:int
    rule_definition_id:int|None=None
    condition_label:str|None=None

@dataclass(frozen=True)
class DependencyResult:
    prerequisite_identity_id:int
    dependent_identity_id:int
    transitive:bool=False
    evidence:tuple[AnalysisEvidence,...]=()

@dataclass(frozen=True)
class InstanceInterval:
    instance_id:int
    identity_id:int
    start:datetime|None
    end:datetime|None

@dataclass(frozen=True)
class SequenceResult:
    left_instance_id:int
    right_instance_id:int
    kind:SequenceKind
    gap:timedelta|None=None

@dataclass(frozen=True)
class ParallelismResult:
    left_identity_id:int
    right_identity_id:int
    potential:bool
    actual_overlap:bool|None
    evidence:tuple[AnalysisEvidence,...]=()

@dataclass(frozen=True)
class BranchResult:
    prerequisite_identity_id:int
    dependent_identity_ids:tuple[int,...]
    kind:BranchKind
    evidence:tuple[AnalysisEvidence,...]=()

@dataclass(frozen=True)
class WaitingResult:
    instance_id:int
    enabled_at:datetime|None
    started_at:datetime|None
    observed_wait:timedelta|None
    classification:Confidence

@dataclass(frozen=True)
class CycleResult:
    identity_ids:tuple[int,...]

@dataclass(frozen=True)
class CorrectionEvidence:
    correcting_instance_id:int
    corrected_instance_id:int
    source:str='EXPLICIT_CORRECTION_SEMANTIC'

@dataclass(frozen=True)
class RepeatResult:
    identity_id:int
    instance_ids:tuple[int,...]
    kind:RepeatKind
    evidence:tuple[AnalysisEvidence,...]=()

@dataclass(frozen=True)
class ProcessAnalysis:
    dependencies:tuple[DependencyResult,...]=()
    branches:tuple[BranchResult,...]=()
    parallelism:tuple[ParallelismResult,...]=()
    cycles:tuple[CycleResult,...]=()
    repeats:tuple[RepeatResult,...]=()
