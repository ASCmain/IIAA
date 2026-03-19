from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class QueryPlan:
    question_type: str
    target_standards: list[str]
    source_preference: str
    needs_change_tracking: bool
    needs_transition_focus: bool
    needs_disclosure_focus: bool
    needs_numeric_reasoning: bool
    needs_consolidated_priority: bool
    needs_modifying_act_priority: bool
    suggested_top_k: int
    analysis_pool_target: int
    min_candidate_floor: int
    threshold_fallback_ladder: list[float]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _detect_target_standards(q: str) -> list[str]:
    out: list[str] = []
    q_up = q.upper()

    candidates = [
        "IAS 1", "IAS 2", "IAS 7", "IAS 8", "IAS 12", "IAS 16", "IAS 19", "IAS 36", "IAS 37", "IAS 38",
        "IFRS 1", "IFRS 2", "IFRS 3", "IFRS 7", "IFRS 9", "IFRS 10", "IFRS 13", "IFRS 15", "IFRS 16", "IFRS 17",
        "IFRIC 10", "IFRIC 19", "SIC 7",
    ]
    for c in candidates:
        if c in q_up:
            out.append(c)
    return out


def build_query_plan(query: str) -> QueryPlan:
    q = (query or "").strip()
    q_up = q.upper()
    notes: list[str] = []
    targets = _detect_target_standards(q_up)

    is_change = any(x in q_up for x in [
        "MODIFIC", "CHANGE", "AGGIORN", "UPDATE", "REGOLAMENTO UE", "REGULATION", "2025/1266", "32025R1266"
    ])
    is_transition = any(x in q_up for x in [
        "TRANSIZIONE", "TRANSITION", "DISCLOSURE", "INFORMATIVA"
    ])
    is_numeric = any(x in q_up for x in [
        "CALCOL", "COMPUT", "NUMERIC", "VALORE D'USO", "VALUE IN USE", "FAIR VALUE",
        "ATTUALIZZ", "DISCOUNT", "WACC", "TASSO"
    ])

    if is_change and is_transition:
        notes.append("Prioritise modifying act because the query explicitly asks about regulatory changes.")
        if targets:
            notes.append(f"Detected target standards: {', '.join(targets)}")
        return QueryPlan(
            question_type="transition_disclosure",
            target_standards=targets,
            source_preference="modifying_act_first_then_consolidated",
            needs_change_tracking=True,
            needs_transition_focus=True,
            needs_disclosure_focus=True,
            needs_numeric_reasoning=False,
            needs_consolidated_priority=False,
            needs_modifying_act_priority=True,
            suggested_top_k=8,
            analysis_pool_target=12,
            min_candidate_floor=8,
            threshold_fallback_ladder=[0.78, 0.74, 0.70, 0.65, 0.60],
            notes=notes,
        )

    if is_change:
        notes.append("Prioritise modifying act because the query explicitly asks about regulatory changes.")
        if targets:
            notes.append(f"Detected target standards: {', '.join(targets)}")
        return QueryPlan(
            question_type="change_analysis",
            target_standards=targets,
            source_preference="modifying_act_first_then_consolidated",
            needs_change_tracking=True,
            needs_transition_focus=False,
            needs_disclosure_focus=False,
            needs_numeric_reasoning=False,
            needs_consolidated_priority=False,
            needs_modifying_act_priority=True,
            suggested_top_k=8,
            analysis_pool_target=12,
            min_candidate_floor=8,
            threshold_fallback_ladder=[0.79, 0.75, 0.70, 0.65, 0.60],
            notes=notes,
        )

    if is_numeric:
        notes.append("Use consolidated text as default source of current operative rule.")
        if targets:
            notes.append(f"Detected target standards: {', '.join(targets)}")
        return QueryPlan(
            question_type="numeric_calculation",
            target_standards=targets,
            source_preference="consolidated_first",
            needs_change_tracking=False,
            needs_transition_focus=False,
            needs_disclosure_focus=False,
            needs_numeric_reasoning=True,
            needs_consolidated_priority=True,
            needs_modifying_act_priority=False,
            suggested_top_k=7,
            analysis_pool_target=18,
            min_candidate_floor=12,
            threshold_fallback_ladder=[0.70, 0.68, 0.65, 0.62, 0.60],
            notes=notes,
        )

    notes.append("Use consolidated text as default source of current operative rule.")
    if targets:
        notes.append(f"Detected target standards: {', '.join(targets)}")
    return QueryPlan(
        question_type="rule_interpretation",
        target_standards=targets,
        source_preference="consolidated_first",
        needs_change_tracking=False,
        needs_transition_focus=False,
        needs_disclosure_focus=False,
        needs_numeric_reasoning=False,
        needs_consolidated_priority=True,
        needs_modifying_act_priority=False,
        suggested_top_k=6,
        analysis_pool_target=16,
        min_candidate_floor=12,
        threshold_fallback_ladder=[0.72, 0.69, 0.66, 0.63, 0.60],
        notes=notes,
    )
