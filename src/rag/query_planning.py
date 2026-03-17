from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class QueryPlan:
    question_type: str
    target_standards: List[str]
    source_preference: str
    needs_change_tracking: bool
    needs_transition_focus: bool
    needs_disclosure_focus: bool
    needs_numeric_reasoning: bool
    needs_consolidated_priority: bool
    needs_modifying_act_priority: bool
    suggested_top_k: int
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_STANDARD_PATTERNS = [
    ("IAS 36", [r"\bIAS\s*36\b", r"\bCGU\b", r"VALORE\s+RECUPERABILE", r"RIDUZIONE\s+DI\s+VALORE", r"IMPAIRMENT"]),
    ("IFRS 9", [r"\bIFRS\s*9\b"]),
    ("IFRS 7", [r"\bIFRS\s*7\b", r"DISCLOSURE", r"INFORMATIVA", r"TRANSIZIONE"]),
    ("IFRS 13", [r"\bIFRS\s*13\b", r"FAIR\s+VALUE"]),
    ("IFRS 1", [r"\bIFRS\s*1\b", r"FIRST[-\s]?TIME", r"PRIMA\s+ADOZIONE"]),
]


def _detect_target_standards(q: str) -> List[str]:
    out: List[str] = []
    for std, patterns in _STANDARD_PATTERNS:
        for p in patterns:
            if re.search(p, q, flags=re.IGNORECASE):
                out.append(std)
                break
    # dedup preserve order
    seen = set()
    final = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        final.append(x)
    return final


def _looks_numeric(q: str) -> bool:
    q_up = (q or "").upper()

    strong_numeric_terms = [
        "CALCOLA", "CALCOLARE", "COMPUTE", "CALCULATE",
        "WACC", "DCF", "DISCOUNT", "DISCOUNT RATE",
        "FLUSSI DI CASSA", "CASH FLOW", "CASH FLOWS",
        "CARRYING AMOUNT", "VALORE CONTABILE",
        "FAIR VALUE", "VALUE IN USE", "VALORE D'USO",
        "TASSO DI ATTUALIZZAZIONE", "TASSO",
        "PERCENT", "%", "€", "EUR", "USD"
    ]
    if any(t in q_up for t in strong_numeric_terms):
        return True

    # remove common regulatory / standard identifiers before checking residual numbers
    scrubbed = q_up
    scrub_patterns = [
        r"\bIAS\s*\d+\b",
        r"\bIFRS\s*\d+\b",
        r"\bIFRIC\s*\d+\b",
        r"\bSIC\s*\d+\b",
        r"\b20\d{2}/\d{3,4}\b",         # e.g. 2025/1266
        r"\bCELEX:\d+[A-Z]?\d+\b",
        r"\bPARAGRAF[OA]\s+\d+([.,]\d+)*\b",
        r"\b\d+([.,]\d+)*\b(?=\s*[A-Z]\b)",  # weak guard for numbered article-like refs
    ]
    for p in scrub_patterns:
        scrubbed = re.sub(p, " ", scrubbed, flags=re.IGNORECASE)

    residual_numbers = re.findall(r"\b\d+[.,]?\d*\b", scrubbed)

    # Require at least two residual numbers to consider it plausibly computational
    # when no strong numeric term is present.
    return len(residual_numbers) >= 2


def build_query_plan(query: str) -> QueryPlan:
    q = (query or "").strip()
    q_up = q.upper()

    target_standards = _detect_target_standards(q)
    needs_numeric_reasoning = _looks_numeric(q)

    mentions_modifying_act = (
        "REGOLAMENTO" in q_up and
        ("2025/1266" in q_up or "32025R1266" in q_up or re.search(r"\b20\d{2}/\d{3,4}\b", q_up) is not None)
    )

    asks_for_changes = any(x in q_up for x in ["MODIFICHE", "CAMBIAMENTI", "INTRODUCE", "MODIFICA", "CHANGE", "AMEND"])
    asks_transition = any(x in q_up for x in ["TRANSIZIONE", "TRANSITION"])
    asks_disclosure = any(x in q_up for x in ["DISCLOSURE", "INFORMATIVA"])
    asks_definition = any(x in q_up for x in ["COSA SI INTENDE", "DEFINIZIONE", "DEFINE", "WHAT IS"])
    asks_compare = any(x in q_up for x in ["CONFRONTA", "DIFFERENZA", "VERSUS", "VS", "COMPARE"])

    if needs_numeric_reasoning and asks_definition:
        question_type = "mixed_numeric_interpretive"
    elif needs_numeric_reasoning:
        question_type = "numeric_calculation"
    elif asks_transition or asks_disclosure:
        question_type = "transition_disclosure"
    elif mentions_modifying_act and asks_for_changes:
        question_type = "change_analysis"
    elif asks_compare:
        question_type = "comparison"
    elif asks_definition:
        question_type = "definition"
    else:
        question_type = "rule_interpretation"

    needs_modifying_act_priority = mentions_modifying_act and (
        asks_for_changes or asks_transition or asks_disclosure
    )
    needs_consolidated_priority = not needs_modifying_act_priority
    needs_change_tracking = needs_modifying_act_priority
    needs_transition_focus = asks_transition
    needs_disclosure_focus = asks_disclosure

    if question_type in {"numeric_calculation", "mixed_numeric_interpretive"}:
        source_preference = "consolidated_first"
        suggested_top_k = 6
    elif needs_modifying_act_priority:
        source_preference = "modifying_act_first_then_consolidated"
        suggested_top_k = 8
    else:
        source_preference = "consolidated_first"
        suggested_top_k = 6

    notes: List[str] = []
    if needs_modifying_act_priority:
        notes.append("Prioritise modifying act because the query explicitly asks about regulatory changes.")
    if needs_consolidated_priority:
        notes.append("Use consolidated text as default source of current operative rule.")
    if needs_numeric_reasoning:
        notes.append("Numeric reasoning required: prefer rule grounding before calculation scaffolding.")
    if target_standards:
        notes.append("Detected target standards: " + ", ".join(target_standards))

    return QueryPlan(
        question_type=question_type,
        target_standards=target_standards,
        source_preference=source_preference,
        needs_change_tracking=needs_change_tracking,
        needs_transition_focus=needs_transition_focus,
        needs_disclosure_focus=needs_disclosure_focus,
        needs_numeric_reasoning=needs_numeric_reasoning,
        needs_consolidated_priority=needs_consolidated_priority,
        needs_modifying_act_priority=needs_modifying_act_priority,
        suggested_top_k=suggested_top_k,
        notes=notes,
    )
