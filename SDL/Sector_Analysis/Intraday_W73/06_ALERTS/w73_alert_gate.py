from __future__ import annotations

from typing import Mapping

REQUIRED_W73 = (
    "orb_minutes","maturity","orb_dir","price_dir","fut_dir","option_dir",
    "fut_state","volume_state","ce_state","pe_state","pec_state",
    "fut_oi_state","ce_pct_state","pe_pct_state","pec_pct_state",
    "fut_pct_state","price_state","orb_agree","evidence_agreement",
    "persistent","strength_bucket","core_count_band","magnitude_count_band",
    "orb_fut_agree","orb_price_agree",
)

def exact_ready(vector: Mapping[str, object]) -> bool:
    return all(vector.get(k) is not None for k in REQUIRED_W73)

def evaluate_variants(strategy, vector: Mapping[str, object]) -> dict:
    if not exact_ready(vector):
        return {"status": "INCOMPLETE", "W73-A": False, "W73-B": False}
    return {
        "status": "READY",
        "W73-A": bool(strategy.match_variant(vector, "W73-A")),
        "W73-B": bool(strategy.match_variant(vector, "W73-B")),
    }
