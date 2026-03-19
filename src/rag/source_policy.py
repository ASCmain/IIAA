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

        hay = _evidence_haystack(e)
        tiers = classify_evidence_tiers(plan, e)

        legal_tier = tiers["legal_tier"]
        semantic_tier = tiers["semantic_tier"]
        has_target = tiers["is_target"]
        mentions_ifric = tiers["is_official_interpretation"]
        mentions_measurement = tiers["is_measurement_context"]
        mentions_intangible = tiers["mentions_intangible_context"]

        if legal_tier == "eu_modifying_act":
            score += 0.28
        elif legal_tier == "eu_consolidated_reference":
            score += 0.18

        if semantic_tier == "target_standard":
            score += 0.26
        elif semantic_tier == "official_interpretation":
            score += 0.05
        elif semantic_tier == "framework_concept":
            score -= 0.04

        if plan.needs_modifying_act_priority:
            if legal_tier == "eu_modifying_act":
                score += 0.34
            if "MODIFICA IL REGOLAMENTO (UE) 2023/1803" in hay:
                score += 0.24
            if has_target:
                score += 0.12
            if mentions_ifric and not has_target:
                score -= 0.24
            if semantic_tier == "related_or_support" and not has_target:
                score -= 0.10

        if plan.needs_consolidated_priority:
            if legal_tier == "eu_consolidated_reference":
                score += 0.20
            if has_target:
                score += 0.18

        if "IAS 36" in target_upper:
            if "IAS 36" in hay:
                score += 0.24
            if "CGU" in hay or "UNITÀ GENERATRICE DI FLUSSI FINANZIARI" in hay:
                score += 0.18
            if "VALORE RECUPERABILE" in hay:
                score += 0.18
            if "RIDUZIONE DI VALORE" in hay or "IMPAIRMENT" in hay:
                score += 0.14

            # IAS 38 is a strong linked context, but not core unless query asks for intangibles
            if "IAS 38" in hay and "IAS 36" not in hay:
                score -= 0.12
                if mentions_intangible:
                    score += 0.05

            if ("IAS 16" in hay or "IFRS 16" in hay) and "IAS 36" not in hay:
                score -= 0.16

        if plan.needs_disclosure_focus and ("DISCLOSURE" in hay or "INFORMATIVA" in hay or "IFRS 7" in hay):
            score += 0.14

        if plan.needs_transition_focus and ("TRANSIZIONE" in hay or "TRANSITION" in hay):
            score += 0.14

        if plan.question_type in {"rule_interpretation", "numeric_calculation", "mixed_numeric_interpretive"}:
            if mentions_measurement:
                score += 0.10

        if target_upper and not has_target:
            if any(x in hay for x in ["IAS ", "IFRS ", "IFRIC ", "SIC "]):
                score -= 0.08

        return score

    return sorted(evidences, key=score_evidence, reverse=True)


def split_core_and_context_for_plan(plan: QueryPlan, evidences):
    target_upper = {x.upper() for x in (plan.target_standards or [])}

    core = []
    context = []

    qtype = plan.question_type

    for e in evidences:
        hay = _evidence_haystack(e)
        tiers = classify_evidence_tiers(plan, e)

        legal_tier = tiers["legal_tier"]
        semantic_tier = tiers["semantic_tier"]
        is_target = tiers["is_target"]
        is_measurement_context = tiers["is_measurement_context"]
        mentions_intangible = tiers["mentions_intangible_context"]

        if plan.needs_modifying_act_priority:
            if legal_tier == "eu_modifying_act":
                core.append(e)
            elif is_target:
                core.append(e)
            elif semantic_tier == "official_interpretation":
                context.append(e)
            else:
                context.append(e)
            continue

        if qtype in {"rule_interpretation", "numeric_calculation", "mixed_numeric_interpretive"}:
            if is_target:
                core.append(e)
                continue

            if "IAS 36" in target_upper and "IAS 38" in hay and "IAS 36" not in hay:
                context.append(e)
                continue

            if is_measurement_context:
                context.append(e)
            else:
                context.append(e)
            continue

        if is_target:
            core.append(e)
        else:
            context.append(e)

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


def _evidence_haystack(e) -> str:
    return " ".join([
        str(e.cite_key or ""),
        str(e.standard_id or ""),
        str(e.para_key or ""),
        str(e.section_path or ""),
        str(e.source or ""),
        str(e.text or "")[:1500],
    ]).upper()


def classify_evidence_tiers(plan: QueryPlan, e) -> dict:
    hay = _evidence_haystack(e)
    target_upper = {x.upper() for x in (plan.target_standards or [])}

    standard_id = str(getattr(e, "standard_id", "") or "").upper()
    source = str(getattr(e, "source", "") or "").upper()

    # -------------------------
    # legal tier
    # -------------------------
    if "CELEX:32025R1266" in source or "32025R1266" in hay or "2025/1266" in hay:
        legal_tier = "eu_modifying_act"
    elif "CELEX:02023R1803-20250730" in source or "02023R1803-20250730" in hay:
        legal_tier = "eu_consolidated_reference"
    else:
        legal_tier = "other_or_unknown"

    # -------------------------
    # semantic tier
    # -------------------------
    if target_upper and any(std in hay for std in target_upper):
        semantic_tier = "target_standard"
    elif standard_id.startswith("IFRIC") or standard_id.startswith("SIC"):
        semantic_tier = "official_interpretation"
    elif "CONCEPTUAL FRAMEWORK" in hay or "FRAMEWORK" in hay:
        semantic_tier = "framework_concept"
    else:
        semantic_tier = "related_or_support"

    # role hints
    is_measurement_context = any(x in hay for x in [
        "FAIR VALUE", "VALORE EQUO",
        "VALUE IN USE", "VALORE D'USO",
        "VALORE RECUPERABILE", "CARRYING AMOUNT", "VALORE CONTABILE",
        "CGU", "UNITÀ GENERATRICE DI FLUSSI FINANZIARI",
        "RIDUZIONE DI VALORE", "IMPAIRMENT"
    ])

    mentions_intangible_context = any(x in hay for x in [
        "ATTIVITÀ IMMATERIALE",
        "IMMATERIAL",
        "VITA UTILE",
        "USEFUL LIFE",
    ])

    return {
        "legal_tier": legal_tier,
        "semantic_tier": semantic_tier,
        "is_measurement_context": is_measurement_context,
        "mentions_intangible_context": mentions_intangible_context,
        "is_target": semantic_tier == "target_standard",
        "is_official_interpretation": semantic_tier == "official_interpretation",
    }


def prune_evidences_for_plan(plan: QueryPlan, evidences):
    """
    Hard/soft admissibility layer applied after reranking and before core/context split.
    The goal is to remove evidences that are still semantically close but professionally secondary.
    """
    qtype = plan.question_type
    target_upper = {x.upper() for x in (plan.target_standards or [])}

    kept = []
    fallback = []
    non_target_interpretations = []

    for e in evidences:
        hay = _evidence_haystack(e)
        tiers = classify_evidence_tiers(plan, e)

        legal_tier = tiers["legal_tier"]
        semantic_tier = tiers["semantic_tier"]
        is_target = tiers["is_target"]
        is_measurement_context = tiers["is_measurement_context"]
        mentions_intangible = tiers["mentions_intangible_context"]

        if qtype == "change_analysis":
            if legal_tier == "eu_modifying_act":
                kept.append(e)
                continue
            if is_target:
                kept.append(e)
                continue
            if semantic_tier == "official_interpretation":
                non_target_interpretations.append(e)
                continue
            # reject generic side material by default
            fallback.append(e)
            continue

        if qtype == "transition_disclosure":
            if legal_tier == "eu_modifying_act":
                kept.append(e)
                continue
            if is_target:
                kept.append(e)
                continue
            if "DISCLOSURE" in hay or "INFORMATIVA" in hay or "TRANSITION" in hay or "TRANSIZIONE" in hay:
                kept.append(e)
                continue
            if semantic_tier == "official_interpretation":
                fallback.append(e)
                continue
            # exclude unrelated support standards like IFRS3 unless needed as last resort
            fallback.append(e)
            continue

        if qtype in {"rule_interpretation", "numeric_calculation", "mixed_numeric_interpretive"}:
            if is_target:
                kept.append(e)
                continue

            # IAS 36 special case: IAS 38 is admissible only as linked context
            if "IAS 36" in target_upper:
                if "IAS 38" in hay and "IAS 36" not in hay:
                    fallback.append(e)
                    continue
                if ("IAS 16" in hay or "IFRS 16" in hay) and "IAS 36" not in hay:
                    fallback.append(e)
                    continue

            if is_measurement_context:
                fallback.append(e)
                continue

            fallback.append(e)
            continue

        # default branch
        kept.append(e)

    # controlled reintroduction of very limited fallback material
    if qtype == "change_analysis":
        # no automatic reintroduction of non-target official interpretations
        # unless the evidence set is critically sparse
        if len(kept) < 3 and non_target_interpretations:
            kept.extend(non_target_interpretations[:1])

    elif qtype == "transition_disclosure":
        if len(kept) < 4:
            kept.extend(fallback[:2])

    elif qtype in {"rule_interpretation", "numeric_calculation", "mixed_numeric_interpretive"}:
        if len(kept) < 5:
            kept.extend(fallback[:3])

    # dedup preserve order
    seen = set()
    out = []
    for e in kept:
        pid = getattr(e, "point_id", None)
        if pid in seen:
            continue
        seen.add(pid)
        out.append(e)

    return out


def effective_threshold_for_plan(plan: QueryPlan) -> float:
    qtype = plan.question_type
    if qtype == "change_analysis":
        return 0.79
    if qtype == "transition_disclosure":
        return 0.78
    if qtype in {"rule_interpretation", "numeric_calculation", "mixed_numeric_interpretive"}:
        return 0.80
    return 0.78


def select_analysis_pool_for_plan(plan: QueryPlan, evidences):
    """
    Build a richer analysis pool before core/context split.
    The goal is to preserve sufficient informational coverage for long IAS/IFRS texts.
    """
    ladder = list(plan.threshold_fallback_ladder or [])
    target = int(plan.analysis_pool_target or max(int(plan.suggested_top_k or 8), 12))
    floor = int(plan.min_candidate_floor or max(8, int(target * 0.66)))

    ranked = rerank_evidences_for_plan(plan, evidences)

    selected = []
    threshold_used = None

    for thr in ladder:
        cand = [e for e in ranked if float(getattr(e, "score", 0.0) or 0.0) >= float(thr)]
        if len(cand) >= floor:
            selected = cand[:target]
            threshold_used = float(thr)
            break

    if not selected:
        selected = ranked[:target]
        threshold_used = None

    coverage_warning_low_candidate_count = len(selected) < floor

    return {
        "analysis_pool": selected,
        "analysis_pool_count": len(selected),
        "analysis_pool_target": target,
        "min_candidate_floor": floor,
        "threshold_used": threshold_used,
        "coverage_warning_low_candidate_count": coverage_warning_low_candidate_count,
    }
