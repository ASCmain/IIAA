from __future__ import annotations

from typing import List

from .query_planning import QueryPlan


def filter_evidences_for_plan(plan: QueryPlan, evidences, requested_top_k: int):
    if not evidences:
        return evidences

    primary = []
    secondary = []
    fallback = []

    target_upper = {x.upper() for x in (plan.target_standards or [])}

    for e in evidences:
        hay = " ".join([
            str(e.cite_key or ""),
            str(e.standard_id or ""),
            str(e.para_key or ""),
            str(e.section_path or ""),
            str(e.source or ""),
            str(e.text or "")[:1500],
        ]).upper()

        matched = False

        if plan.needs_modifying_act_priority:
            if "32025R1266" in hay or "2025/1266" in hay:
                primary.append(e)
                matched = True
            elif any(std in hay for std in target_upper):
                secondary.append(e)
                matched = True

        elif plan.needs_consolidated_priority:
            if any(std in hay for std in target_upper):
                primary.append(e)
                matched = True
            elif plan.question_type in {"numeric_calculation", "mixed_numeric_interpretive"}:
                if "VALORE RECUPERABILE" in hay or "CGU" in hay or "RIDUZIONE DI VALORE" in hay or "IMPAIRMENT" in hay:
                    secondary.append(e)
                    matched = True

        if not matched:
            fallback.append(e)

    filtered = primary + secondary + fallback

    seen = set()
    out = []
    for e in filtered:
        pid = getattr(e, "point_id", None)
        if pid in seen:
            continue
        seen.add(pid)
        out.append(e)

    keep_n = max(int(requested_top_k), min(max(int(requested_top_k), 12), len(out)))
    return out[:keep_n]


def rerank_evidences_for_plan(plan: QueryPlan, evidences):
    target_upper = {x.upper() for x in (plan.target_standards or [])}

    def score_evidence(e):
        score = float(e.score or 0.0)

        hay = " ".join([
            str(e.cite_key or ""),
            str(e.standard_id or ""),
            str(e.para_key or ""),
            str(e.section_path or ""),
            str(e.source or ""),
            str(e.text or "")[:1200],
        ]).upper()

        has_target = any(std in hay for std in target_upper) if target_upper else False
        mentions_ifric = "IFRIC" in hay
        mentions_side_standard = any(x in hay for x in ["IAS 38", "IAS 16", "IFRS 16", "IAS 20"])

        if plan.needs_modifying_act_priority:
            if "32025R1266" in hay or "2025/1266" in hay:
                score += 0.55
            if "MODIFICA IL REGOLAMENTO (UE) 2023/1803" in hay:
                score += 0.24
            if has_target:
                score += 0.12

            # penalise accessory amendment chains if not target-centred
            if mentions_ifric and not has_target:
                score -= 0.18
            if mentions_side_standard and not has_target:
                score -= 0.10

        if plan.needs_consolidated_priority:
            if has_target:
                score += 0.35

        if "IAS 36" in target_upper:
            if "IAS 36" in hay:
                score += 0.28
            if "CGU" in hay or "UNITÀ GENERATRICE DI FLUSSI FINANZIARI" in hay:
                score += 0.18
            if "VALORE RECUPERABILE" in hay:
                score += 0.18
            if "RIDUZIONE DI VALORE" in hay or "IMPAIRMENT" in hay:
                score += 0.14
            if ("IAS 38" in hay or "IAS 16" in hay or "IFRS 16" in hay) and "IAS 36" not in hay:
                score -= 0.18

        if plan.needs_disclosure_focus and ("DISCLOSURE" in hay or "INFORMATIVA" in hay or "IFRS 7" in hay):
            score += 0.14

        if plan.needs_transition_focus and ("TRANSIZIONE" in hay or "TRANSITION" in hay):
            score += 0.14

        # generic penalty for standards not requested, when targets are explicit
        if target_upper and not has_target:
            if any(x in hay for x in ["IAS ", "IFRS ", "IFRIC ", "SIC "]):
                score -= 0.08

        return score

    return sorted(evidences, key=score_evidence, reverse=True)


def split_core_and_context_for_plan(plan: QueryPlan, evidences):
    target_upper = {x.upper() for x in (plan.target_standards or [])}

    core = []
    context = []

    for e in evidences:
        hay = " ".join([
            str(e.cite_key or ""),
            str(e.standard_id or ""),
            str(e.para_key or ""),
            str(e.section_path or ""),
            str(e.source or ""),
            str(e.text or "")[:1500],
        ]).upper()

        is_target = any(std in hay for std in target_upper) if target_upper else False
        is_modifying_act = "32025R1266" in hay or "2025/1266" in hay
        is_measurement_context = any(x in hay for x in [
            "FAIR VALUE", "VALORE EQUO",
            "VALUE IN USE", "VALORE D'USO",
            "VALORE RECUPERABILE", "CARRYING AMOUNT", "VALORE CONTABILE",
            "CGU", "UNITÀ GENERATRICE DI FLUSSI FINANZIARI",
            "RIDUZIONE DI VALORE", "IMPAIRMENT"
        ])

        if plan.needs_modifying_act_priority:
            if is_modifying_act or is_target:
                core.append(e)
            else:
                context.append(e)
            continue

        if plan.question_type in {"rule_interpretation", "numeric_calculation", "mixed_numeric_interpretive"}:
            if is_target:
                core.append(e)
            elif is_measurement_context:
                context.append(e)
            else:
                context.append(e)
            continue

        if is_target:
            core.append(e)
        else:
            context.append(e)

    # dedup preserve order
    def _dedup(seq):
        seen = set()
        out = []
        for e in seq:
            pid = getattr(e, "point_id", None)
            if pid in seen:
                continue
            seen.add(pid)
            out.append(e)
        return out

    return _dedup(core), _dedup(context)
