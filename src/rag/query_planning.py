from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


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
        "IFRIC 1", "IFRIC 10", "IFRIC 19", "SIC 7",
    ]
    for c in candidates:
        if c in q_up:
            out.append(c)
    return out


def _has_any(q_up: str, items: list[str]) -> bool:
    return any(x in q_up for x in items)


def _plan_from_question_type(question_type: str, targets: list[str], notes: list[str]) -> QueryPlan:
    if question_type == "transition_disclosure":
        return QueryPlan(
            question_type=question_type,
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
    if question_type == "change_analysis":
        return QueryPlan(
            question_type=question_type,
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
    if question_type == "disclosure_check":
        return QueryPlan(
            question_type=question_type,
            target_standards=targets,
            source_preference="consolidated_first",
            needs_change_tracking=False,
            needs_transition_focus=False,
            needs_disclosure_focus=True,
            needs_numeric_reasoning=False,
            needs_consolidated_priority=True,
            needs_modifying_act_priority=False,
            suggested_top_k=7,
            analysis_pool_target=16,
            min_candidate_floor=12,
            threshold_fallback_ladder=[0.72, 0.69, 0.66, 0.63, 0.60],
            notes=notes,
        )
    if question_type == "numeric_calculation":
        return QueryPlan(
            question_type=question_type,
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


def build_query_plan(query: str, semantic_route: dict[str, Any] | None = None) -> QueryPlan:
    q = (query or "").strip()
    q_up = q.upper()
    notes: list[str] = []
    targets = _detect_target_standards(q)

    route = semantic_route or {}
    semantic_hint = str(route.get("top_question_type_hint") or "").strip()
    semantic_intent = str(route.get("top_intent_id") or "").strip()
    semantic_ambiguous = bool(route.get("ambiguous"))

    mentions_reg_change = _has_any(q_up, [
        "REGOLAMENTO UE", "REGULATION", "2025/1266", "32025R1266",
        "MODIFIC", "AMEND", "UPDATE",
    ])

    mentions_transition_strict = _has_any(q_up, [
        "FIRST-TIME", "FIRST TIME", "PRIMA ADOZIONE",
        "FIRST APPLICATION", "INITIAL APPLICATION",
        "EFFECTIVE DATE", "DATA DI ENTRATA IN VIGORE",
        "TRANSITION REQUIREMENTS",
    ])

    mentions_disclosure = _has_any(q_up, [
        "DISCLOSURE", "INFORMATIVA", "DISCLOSURES", "SENSITIVITY ANALYSIS",
        "MATURITY ANALYSIS", "RISK DISCLOSURE", "MARKET RISK", "LIQUIDITY RISK",
        "KEY ASSUMPTIONS", "ASSUNZIONI CHIAVE",
    ])

    strong_numeric = _has_any(q_up, [
        "CALCOL", "COMPUT", "NUMERIC", "FORMULA", "DCF", "WACC", "ATTUALIZZ",
        "DISCOUNT RATE", "VALUE IN USE", "VALORE D'USO",
        "FAIR VALUE LESS COSTS OF DISPOSAL", "FVLCOD", "VIU",
        "PRESENT VALUE", "PERCENT", "%",
    ])

    numeric_context_only = _has_any(q_up, [
        "SENSITIVITY ANALYSIS", "MARKET RISK", "LIQUIDITY RISK",
        "DISCLOSURE", "INFORMATIVA", "KEY ASSUMPTIONS", "ASSUNZIONI CHIAVE",
    ])

    is_change = mentions_reg_change
    is_transition_disclosure = mentions_transition_strict and (mentions_disclosure or is_change)
    is_disclosure_check = mentions_disclosure and not is_change and not is_transition_disclosure
    is_numeric = strong_numeric and not numeric_context_only and not is_disclosure_check

    question_type = "rule_interpretation"

    if semantic_hint and not semantic_ambiguous:
        question_type = semantic_hint
        notes.append(f"Semantic router hint accepted: {semantic_intent} -> {semantic_hint}.")
    else:
        if is_change and is_transition_disclosure:
            question_type = "transition_disclosure"
            notes.append("Transition/disclosure query tied to regulatory or amendment context.")
        elif is_change:
            question_type = "change_analysis"
            notes.append("Prioritise modifying act because the query explicitly asks about regulatory changes.")
        elif is_disclosure_check:
            question_type = "disclosure_check"
            notes.append("Disclosure-oriented query: prefer operative consolidated requirements and narrow lateral context.")
        elif is_numeric:
            question_type = "numeric_calculation"
            notes.append("Numeric or measurement-heavy query: prefer rule grounding before calculation scaffolding.")
        else:
            question_type = "rule_interpretation"
            notes.append("Use consolidated text as default source of current operative rule.")

    if targets:
        notes.append(f"Detected target standards: {', '.join(targets)}")

    return _plan_from_question_type(question_type, targets, notes)
