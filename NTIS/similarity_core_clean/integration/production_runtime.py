"""
NTIS Production Runtime v4.0

Bundle 02 - Historical Intelligence Layer

Adds similarity confidence calculation output.
"""

import pandas as pd
from pathlib import Path

from similarity_core_clean.integration.execution_context import ExecutionContext
from similarity_core_clean.integration.hmme_runtime_executor import HMMERuntimeExecutor
from similarity_core_clean.integration.result_collector import ResultCollector
from similarity_core_clean.integration.functional_gateway import FunctionalGateway
from similarity_core_clean.reporting.hmme_production_report import HMMEProductionReport
from similarity_core_clean.integration.hmme_learning_bridge import HMMELearningBridge
from similarity_core_clean.integration.hmme_replay_engine import HMMEReplayEngine
from similarity_core_clean.integration.hmme_outcome_calibration import HMMEOutcomeCalibration
from similarity_core_clean.integration.hmme_historical_data_loader import HMMEHistoricalDataLoader
from similarity_core_clean.integration.pattern_repository_engine import PatternRepositoryEngine
from similarity_core_clean.integration.pattern_repository_manager import PatternRepositoryManager
from similarity_core_clean.integration.pattern_fingerprint_engine import PatternFingerprintEngine
from similarity_core_clean.integration.historical_pattern_intelligence import HistoricalPatternIntelligence
from similarity_core_clean.integration.historical_intelligence_bridge import HistoricalIntelligenceBridge
from similarity_core_clean.integration.eod_similarity_bridge import EODSimilarityBridge
from similarity_core_clean.integration.historical_evidence_aggregator import HistoricalEvidenceAggregator
from similarity_core_clean.integration.historical_evidence_service import HistoricalEvidenceService
from similarity_core_clean.integration.hmme_real_replay_controller import HMMERealReplayController
from similarity_core_clean.integration.historical_evidence_scorer import HistoricalEvidenceScorer
from similarity_core_clean.integration.probability_evidence_enhancer import ProbabilityEvidenceEnhancer
from similarity_core_clean.integration.similarity_confidence_calculator import SimilarityConfidenceCalculator


HISTORICAL_FOOTPRINT_FILE = Path(
    "E:/NSE_Daily_Analysis/Historical_Data/Footprints/NTIS_Historical_Footprints.csv"
)

HISTORICAL_DATA_DIR = Path("E:/NSE_Daily_Analysis/Historical_Data")
PREDICTION_ARCHIVE_DIR = HISTORICAL_DATA_DIR / "Predictions"
OUTCOME_ARCHIVE_DIR = HISTORICAL_DATA_DIR / "Outcomes"


class ProductionRuntime:

    def __init__(self):
        self.context = ExecutionContext()
        self.gateway = FunctionalGateway()

    def _build_replay_evidence_from_repository(self, repository_records):
        evidence_scores = []

        for record in repository_records or []:
            record_dict = record.to_dict() if hasattr(record, "to_dict") else record if isinstance(record, dict) else None
            if not isinstance(record_dict, dict):
                continue

            normalized_features = record_dict.get("normalized_features") or {}
            evidence_vector = record_dict.get("evidence_vector") or {}

            symbol = record_dict.get("symbol")
            date_value = normalized_features.get("date") or record_dict.get("last_seen")
            if not symbol or not date_value:
                continue

            evidence_score = evidence_vector.get("evidence_score")
            if evidence_score is None:
                confidence = normalized_features.get("confidence")
                if confidence is not None:
                    evidence_score = confidence

            evidence_scores.append({
                "symbol": symbol,
                "date": str(date_value),
                "market_pattern": record_dict.get("pattern_classification"),
                "ntis_score": evidence_vector.get("ntis_score"),
                "probability": evidence_vector.get("probability"),
                "entry": evidence_vector.get("entry"),
                "outcome": record_dict.get("historical_outcome") or evidence_vector.get("outcome"),
                "return_pct": evidence_vector.get("return_pct"),
                "accuracy": evidence_vector.get("accuracy"),
                "confidence": normalized_features.get("confidence") or evidence_vector.get("confidence"),
                "evidence_score": evidence_score,
                "business_pattern_id": record_dict.get("business_pattern_id"),
                "pattern_dna": record_dict.get("pattern_dna"),
            })

        return evidence_scores

    def _normalize_confidence(self, value):
        if value is None:
            return 0.0

        try:
            numeric = float(value)
        except Exception:
            return 0.0

        if numeric <= 0.0:
            return 0.0
        if numeric <= 1.0:
            return numeric
        if numeric <= 100.0:
            return numeric / 100.0
        return 1.0

    def _coerce_float(self, value):
        try:
            return float(value)
        except Exception:
            return None

    def _build_reason_summary(self, replay_strength, historical_success_ratio, evidence_confidence, repository_confidence):
        reasons = []

        if replay_strength >= 75:
            reasons.append("strong replay signal")
        elif replay_strength >= 40:
            reasons.append("moderate replay signal")
        else:
            reasons.append("weak replay signal")

        if historical_success_ratio >= 0.75:
            reasons.append("high historical success")
        elif historical_success_ratio >= 0.4:
            reasons.append("moderate historical success")
        else:
            reasons.append("low historical success")

        if evidence_confidence >= 0.75:
            reasons.append("high evidence confidence")
        elif evidence_confidence >= 0.4:
            reasons.append("moderate evidence confidence")

        if repository_confidence >= 0.75:
            reasons.append("high repository confidence")
        elif repository_confidence >= 0.4:
            reasons.append("moderate repository confidence")

        return "; ".join(reasons)

    def _build_candidate_ranking(self, repository_records, evidence_scores):
        evidence_map = {
            item.get("business_pattern_id"): item
            for item in evidence_scores
            if isinstance(item, dict) and item.get("business_pattern_id")
        }

        candidates = []
        for record in repository_records or []:
            record_dict = record.to_dict() if hasattr(record, "to_dict") else record if isinstance(record, dict) else None
            if not isinstance(record_dict, dict):
                continue

            normalized_features = record_dict.get("normalized_features") or {}
            raw_replay_strength = 0.0
            evidence_item = evidence_map.get(record_dict.get("business_pattern_id"))
            if evidence_item:
                raw_replay_strength = self._coerce_float(evidence_item.get("evidence_score")) or 0.0
            else:
                raw_replay_strength = self._coerce_float(record_dict.get("confidence")) or 0.0

            raw_repository_confidence = self._coerce_float(record_dict.get("confidence")) or 0.0
            raw_historical_success_ratio = self._coerce_float(record_dict.get("success_rate")) or 0.0
            raw_evidence_confidence = self._coerce_float(evidence_item.get("confidence") if evidence_item else normalized_features.get("confidence")) or 0.0
            raw_pattern_confidence = self._coerce_float(normalized_features.get("confidence")) or 0.0

            replay_strength = min(max(raw_replay_strength, 0.0), 100.0)
            repository_confidence = self._normalize_confidence(raw_repository_confidence)
            historical_success_ratio = raw_historical_success_ratio if raw_historical_success_ratio <= 1.0 else min(raw_historical_success_ratio / 100.0, 1.0)
            evidence_confidence = self._normalize_confidence(raw_evidence_confidence)
            pattern_confidence = self._normalize_confidence(raw_pattern_confidence)

            composite_score = (
                0.30 * (replay_strength / 100.0)
                + 0.25 * historical_success_ratio
                + 0.25 * evidence_confidence
                + 0.15 * repository_confidence
                + 0.05 * pattern_confidence
            )

            candidates.append({
                "symbol": record_dict.get("symbol"),
                "business_pattern_id": record_dict.get("business_pattern_id"),
                "pattern_dna": record_dict.get("pattern_dna"),
                "rank": 0,
                "composite_score": round(composite_score, 4),
                "replay_strength": round(replay_strength, 4),
                "historical_success_ratio": round(historical_success_ratio, 4),
                "evidence_confidence": round(evidence_confidence, 4),
                "repository_confidence": round(repository_confidence, 4),
                "reason_summary": self._build_reason_summary(
                    replay_strength,
                    historical_success_ratio,
                    evidence_confidence,
                    repository_confidence,
                ),
            })

        candidates.sort(key=lambda item: (-item["composite_score"], -item["replay_strength"], -item["repository_confidence"]))

        for index, candidate in enumerate(candidates, start=1):
            candidate["rank"] = index

        return candidates

    def _load_historical_footprints(self):
        if not HISTORICAL_FOOTPRINT_FILE.exists():
            return []

        try:
            df = pd.read_csv(HISTORICAL_FOOTPRINT_FILE)
        except Exception:
            return []

        if df.empty or "Symbol" not in df.columns:
            return []

        records = []
        for _, row in df.iterrows():
            outcome = str(row.get("Outcome", "PENDING"))
            wins = 1 if outcome == "SUCCESS" else 0
            losses = 1 if outcome == "FAILED" else 0
            pending = 1 if outcome == "PENDING" else 0

            try:
                actual_return = float(row.get("Actual Return %", 0.0))
            except Exception:
                actual_return = 0.0

            try:
                confidence = float(row.get("Confidence", 0.0))
            except Exception:
                confidence = 0.0

            resolved = wins + losses
            success_rate = wins / float(resolved) if resolved else 0.0

            records.append({
                "symbol": str(row.get("Symbol")),
                "business_pattern_id": str(row.get("Pattern", "")),
                "pattern_classification": str(row.get("Pattern", "")),
                "pattern_dna": str(row.get("Pattern Reason", "")),
                "fingerprint_version": "historical-footprint-v1",
                "first_seen": str(row.get("Trading Date", "")),
                "last_seen": str(row.get("Trading Date", "")),
                "occurrences": 1,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "success_rate": success_rate,
                "average_return": actual_return if resolved else 0.0,
                "confidence": confidence,
                "lifecycle_status": "HISTORICAL",
                "normalized_features": {},
                "evidence_vector": {},
                "historical_outcome": outcome,
            })

        return records

    def _discover_historical_archive_pairs(self):
        pairs = []
        if not PREDICTION_ARCHIVE_DIR.exists():
            return pairs

        for prediction_file in sorted(
            PREDICTION_ARCHIVE_DIR.rglob("NTIS_Prediction_*.csv")
        ):
            try:
                date_token = prediction_file.stem.replace(
                    "NTIS_Prediction_", ""
                )
                relative_path = prediction_file.parent.relative_to(
                    PREDICTION_ARCHIVE_DIR
                )
                outcome_file = (
                    OUTCOME_ARCHIVE_DIR
                    / relative_path
                    / f"NTIS_Outcome_{date_token}.csv"
                )
                pairs.append((prediction_file, outcome_file if outcome_file.exists() else None))
            except Exception:
                continue

        return pairs

    def _build_historical_fingerprint_payload(self, row, date_token, fingerprint_engine):
        market_state = {
            "symbol": str(row.get("Symbol") or "").strip(),
            "date": str(date_token),
        }

        mapped_values = {
            "open": ["Open"],
            "high": ["High"],
            "low": ["Low"],
            "close": ["Price", "CMP", "Entry Close"],
            "volume": ["Volume", "OI"],
            "confidence": ["Confidence", "BUY Probability %", "SELL Probability %"],
            "trend": ["Trend", "Price Chg", "Price Chg %"],
            "volatility": ["Volatility", "IV", "IV Chg %"],
        }

        for feature, keys in mapped_values.items():
            for key in keys:
                if key in row.index:
                    value = self._coerce_float(row.get(key))
                    if value is not None:
                        market_state[feature] = value
                        break

        if "Pattern" in row.index and row.get("Pattern") not in (None, ""):
            market_state["pattern_classification"] = str(row.get("Pattern"))
            market_state["market_pattern"] = str(row.get("Pattern"))
        elif "Signal" in row.index and row.get("Signal") not in (None, ""):
            market_state["pattern_classification"] = str(row.get("Signal"))
            market_state["market_pattern"] = str(row.get("Signal"))
        elif "Pattern Reason" in row.index and row.get("Pattern Reason") not in (None, ""):
            market_state["market_pattern"] = str(row.get("Pattern Reason"))

        fingerprint_payload = fingerprint_engine.build_fingerprint(market_state)
        if fingerprint_payload.get("status") != "FINGERPRINT_READY":
            return None

        if fingerprint_payload.get("evidence_vector") is None:
            fingerprint_payload["evidence_vector"] = {}

        return fingerprint_payload

    def _build_repository_record_from_historical_fingerprint(
        self, fingerprint_payload, row, date_token, repository_engine
    ):
        repository_response = repository_engine.create_repository_record(
            fingerprint_payload
        )
        repository_record = repository_response.get("repository_record")
        if repository_record is None:
            return None

        record = repository_record.copy()
        record["first_seen"] = str(date_token)
        record["last_seen"] = str(date_token)
        record["lifecycle_status"] = "HISTORICAL"

        if not isinstance(record.get("normalized_features"), dict):
            record["normalized_features"] = {}

        record["normalized_features"]["date"] = str(date_token)

        if not isinstance(record.get("evidence_vector"), dict):
            record["evidence_vector"] = {}

        evidence_vector = record["evidence_vector"]
        actual_return = self._coerce_float(row.get("Actual Return %"))
        if actual_return is not None:
            evidence_vector["return_pct"] = actual_return

        model_accuracy = self._coerce_float(row.get("Model Accuracy %"))
        if model_accuracy is not None:
            evidence_vector["accuracy"] = model_accuracy

        outcome_value = row.get("Outcome")
        historical_outcome = None
        if outcome_value is not None and not pd.isna(outcome_value):
            historical_outcome = str(outcome_value).strip()

        record["historical_outcome"] = historical_outcome

        wins = 1 if historical_outcome and historical_outcome.upper() == "SUCCESS" else 0
        losses = 1 if historical_outcome and historical_outcome.upper() == "FAILED" else 0
        pending = 1 if historical_outcome and historical_outcome.upper() == "PENDING" else 0

        record["occurrences"] = 1
        record["wins"] = wins
        record["losses"] = losses
        record["pending"] = pending
        record["success_rate"] = float(wins) / (wins + losses) if (wins + losses) > 0 else 0.0

        if wins + losses > 0 and actual_return is not None:
            record["average_return"] = actual_return
        else:
            record["average_return"] = 0.0

        confidence_value = self._coerce_float(row.get("Confidence"))
        if confidence_value is not None:
            record["confidence"] = confidence_value

        return record

    def _build_historical_archive_repository_records(self):
        archive_pairs = self._discover_historical_archive_pairs()
        if not archive_pairs:
            return []

        repository_records = []
        repository_engine = PatternRepositoryEngine()
        repository_manager = PatternRepositoryManager()
        fingerprint_engine = PatternFingerprintEngine()

        for prediction_file, outcome_file in archive_pairs:
            try:
                prediction_df = pd.read_csv(prediction_file)
            except Exception:
                continue

            if "Symbol" not in prediction_df.columns:
                continue

            outcome_df = None
            if outcome_file is not None:
                try:
                    outcome_df = pd.read_csv(outcome_file)
                except Exception:
                    outcome_df = None

            if outcome_df is not None and "Symbol" in outcome_df.columns:
                outcome_columns = [
                    column
                    for column in [
                        "Outcome",
                        "Actual Return %",
                        "Model Accuracy %",
                    ]
                    if column in outcome_df.columns
                ]
                outcome_subset = outcome_df[
                    ["Symbol"] + outcome_columns
                ].drop_duplicates(subset=["Symbol"], keep="last")
                merged = prediction_df.merge(
                    outcome_subset,
                    on="Symbol",
                    how="left",
                    suffixes=("", "_OUTCOME"),
                )
            else:
                merged = prediction_df.copy()

            date_token = prediction_file.stem.replace(
                "NTIS_Prediction_", ""
            )

            for _, row in merged.iterrows():
                fingerprint_payload = self._build_historical_fingerprint_payload(
                    row, date_token, fingerprint_engine
                )
                if fingerprint_payload is None:
                    continue

                historical_record = self._build_repository_record_from_historical_fingerprint(
                    fingerprint_payload,
                    row,
                    date_token,
                    repository_engine,
                )
                if historical_record is None:
                    continue

                merge_response = repository_manager.manage_repository_record(
                    historical_record,
                    repository_records,
                )
                merged_record = merge_response.get("repository_record")
                if merged_record is None:
                    continue

                existing_index = next(
                    (
                        index
                        for index, item in enumerate(repository_records)
                        if item.get("business_pattern_id") == merged_record.get("business_pattern_id")
                    ),
                    None,
                )

                if existing_index is not None:
                    repository_records[existing_index] = merged_record
                else:
                    repository_records.append(merged_record)

        return repository_records

    def _build_pdna_profile(self, repository_records):
        hpi = HistoricalPatternIntelligence()
        records = repository_records or self._load_historical_footprints()
        if not records:
            records = hpi._gather_records(repository_records)

        if not records:
            return {
                "status": "INSUFFICIENT_HISTORY",
                "reason": "No Historical Footprint or repository records available",
                "historical_occurrences": 0,
            }

        total_occurrences = 0
        total_wins = 0
        total_losses = 0
        total_return = 0.0
        total_confidence = 0.0
        resolved_confidence_count = 0
        patterns = set()
        stock_profiles = {}

        for record in records:
            record_dict = hpi._payload_to_dict(record)
            symbol = record_dict.get("symbol")
            pattern = record_dict.get("pattern_dna")
            occurrences = hpi._coerce_int(record_dict.get("occurrences")) or 0
            wins = hpi._coerce_int(record_dict.get("wins")) or 0
            losses = hpi._coerce_int(record_dict.get("losses")) or 0
            pending = hpi._coerce_int(record_dict.get("pending")) or 0
            average_return = hpi._coerce_float(record_dict.get("average_return")) or 0.0
            confidence = hpi._coerce_float(record_dict.get("confidence")) or 0.0

            total_occurrences += occurrences
            total_wins += wins
            total_losses += losses
            patterns.add(pattern)

            if wins + losses > 0:
                total_return += average_return * (wins + losses)
                total_confidence += confidence * (wins + losses)
                resolved_confidence_count += wins + losses

            if symbol:
                profile = stock_profiles.setdefault(
                    str(symbol),
                    {
                        "historical_occurrences": 0,
                        "resolved_occurrences": 0,
                        "wins": 0,
                        "losses": 0,
                        "pending": 0,
                        "historical_average_return": 0.0,
                        "historical_confidence": 0.0,
                        "patterns": set(),
                    },
                )

                profile["historical_occurrences"] += occurrences
                profile["resolved_occurrences"] += wins + losses
                profile["wins"] += wins
                profile["losses"] += losses
                profile["pending"] += pending
                profile["patterns"].add(pattern)

                if wins + losses > 0:
                    profile["historical_average_return"] += (
                        average_return * (wins + losses)
                    )
                    profile["historical_confidence"] += (
                        confidence * (wins + losses)
                    )

        resolved_occurrences = total_wins + total_losses
        historical_success_rate = (
            float(total_wins) / resolved_occurrences
            if resolved_occurrences > 0
            else 0.0
        )
        historical_average_return = (
            total_return / resolved_occurrences
            if resolved_occurrences > 0
            else 0.0
        )
        historical_confidence = (
            total_confidence / resolved_confidence_count
            if resolved_confidence_count > 0
            else 0.0
        )

        for symbol, profile in stock_profiles.items():
            resolved = profile["resolved_occurrences"]
            profile["historical_success_rate"] = (
                profile["wins"] / float(resolved)
                if resolved > 0
                else 0.0
            )
            profile["historical_average_return"] = (
                profile["historical_average_return"] / resolved
                if resolved > 0
                else 0.0
            )
            profile["historical_confidence"] = (
                profile["historical_confidence"] / resolved
                if resolved > 0
                else 0.0
            )
            profile["pattern_maturity"] = hpi._build_pattern_maturity(
                profile["historical_occurrences"]
            )
            profile["patterns"] = sorted(
                item for item in profile["patterns"] if item
            )
            profile["pattern_strength"] = hpi._build_pattern_strength(
                profile["historical_success_rate"],
                profile["historical_confidence"],
                profile["historical_average_return"],
            )

        pattern_success_rates = [
            hpi._coerce_float(record.get("success_rate")) or 0.0
            for record in records
            if (hpi._coerce_int(record.get("wins")) or 0)
            + (hpi._coerce_int(record.get("losses")) or 0) > 0
        ]
        pattern_stability = hpi._build_pattern_stability(pattern_success_rates)
        pattern_strength = hpi._build_pattern_strength(
            historical_success_rate,
            historical_confidence,
            historical_average_return,
        )

        return {
            "status": "PDNA_AVAILABLE",
            "reason": "Stock-specific historical PDNA profiles generated from Historical Footprint records",
            "symbols": sorted(stock_profiles),
            "pattern_dna": sorted(item for item in patterns if item),
            "historical_occurrences": total_occurrences,
            "resolved_occurrences": resolved_occurrences,
            "pending_occurrences": total_occurrences - resolved_occurrences,
            "historical_success_rate": historical_success_rate,
            "historical_average_return": historical_average_return,
            "historical_confidence": historical_confidence,
            "pattern_maturity": hpi._build_pattern_maturity(total_occurrences),
            "pattern_stability": pattern_stability,
            "pattern_strength": pattern_strength,
            "stock_profiles": stock_profiles,
        }

    def run(self):

        runtime_result = HMMERuntimeExecutor(self.gateway).execute()

        report_file = HMMEProductionReport().generate({})

        repository_records = list(self.context.metadata.get("repository_records") or [])
        historical_repository_records = self._build_historical_archive_repository_records()
        if historical_repository_records:
            repository_records.extend(historical_repository_records)

        fingerprint_records = self.context.metadata.get("pattern_fingerprint_records") or []

        if not fingerprint_records:
            fingerprint_records = EODSimilarityBridge().build_fingerprint_payloads()
            self.context.metadata["pattern_fingerprint_records"] = fingerprint_records or []

        if fingerprint_records:
            repository_engine = PatternRepositoryEngine()
            repository_manager = PatternRepositoryManager()

            for fingerprint in fingerprint_records:
                repository_response = repository_engine.create_repository_record(fingerprint)
                repository_record = repository_response.get("repository_record")
                if repository_record is None:
                    continue

                merge_response = repository_manager.manage_repository_record(
                    repository_record,
                    repository_records,
                )
                merged_record = merge_response.get("repository_record")
                if merged_record is None:
                    continue

                existing_index = next(
                    (
                        index
                        for index, item in enumerate(repository_records)
                        if item.get("business_pattern_id") == merged_record.get("business_pattern_id")
                    ),
                    None,
                )

                if existing_index is not None:
                    repository_records[existing_index] = merged_record
                else:
                    repository_records.append(merged_record)

            self.context.metadata["repository_records"] = repository_records

        if repository_records:
            first = repository_records[0]
            normalized = first.get("normalized_features", {}) if isinstance(first, dict) else {}
            self.context.metadata["historical_evidence_symbol"] = first.get("symbol") if isinstance(first, dict) else None
            self.context.metadata["historical_evidence_date"] = normalized.get("date") or (first.get("last_seen") if isinstance(first, dict) else None)
            self.context.metadata["historical_evidence_market_pattern"] = first.get("pattern_classification") if isinstance(first, dict) else None

        historical_intelligence = HistoricalPatternIntelligence().analyze(
            repository_records
        )

        bridge_payload = HistoricalIntelligenceBridge().build_intelligence_payload(
            historical_intelligence
        )

        aggregated_evidence = HistoricalEvidenceAggregator().aggregate(
            bridge_payload
        )

        service_output = HistoricalEvidenceService().serve(
            aggregated_evidence
        )

        if service_output.get("service_summary") and isinstance(service_output["service_summary"], dict):
            service_summary = service_output["service_summary"]
            service_summary["symbol"] = self.context.metadata.get("historical_evidence_symbol")
            service_summary["date"] = self.context.metadata.get("historical_evidence_date")
            service_summary["market_pattern"] = self.context.metadata.get("historical_evidence_market_pattern")

        loader = HMMEHistoricalDataLoader()

        historical_data = loader.load()
        evidence_records = loader.load_evidence(
            service_output=service_output
        )
        if not evidence_records:
            print("[WARNING] Historical Evidence Loader returned no evidence records.")

        evidence_scores = HistoricalEvidenceScorer().score(
            evidence_records
        )

        pdna_evidence_scores = self._build_replay_evidence_from_repository(repository_records)
        if pdna_evidence_scores:
            evidence_scores.extend(pdna_evidence_scores)

        similarity_confidence = SimilarityConfidenceCalculator().calculate(
            similarity_result={},
            evidence_scores=evidence_scores
        )

        candidate_ranking = self._build_candidate_ranking(repository_records, evidence_scores)

        probability_enhancement = ProbabilityEvidenceEnhancer().enhance(
            probability_result={},
            evidence_scores=evidence_scores
        )

        replay_engine = HMMEReplayEngine()
        controller = HMMERealReplayController()

        replay_result = controller.run_replay(
            loader,
            replay_engine,
            evidence_scores=evidence_scores
        )

        calibration = HMMEOutcomeCalibration()

        calibration_status = calibration.calibrate(
            calibration.validate_outcome(
                replay_result
            )
        )

        learning = HMMELearningBridge()

        learning_status = learning.update_learning(
            calibration_status
        )

        # PDNA must use pre-existing historical repository records only.
        # Do not count records created during the current runtime execution
        # as historical evidence.
        pdna_profile = self._build_pdna_profile(historical_repository_records)

        return ResultCollector().collect({
            "runtime": runtime_result,
            "report": str(report_file),
            "learning": learning_status,
            "replay": replay_result,
            "calibration": calibration_status,
            "historical_records": len(historical_data),
            "evidence_records": len(evidence_scores),
            "repository_summary": repository_records,
            "historical_intelligence": historical_intelligence,
            "historical_evidence": aggregated_evidence.get("historical_evidence") if 'aggregated_evidence' in locals() else None,
            "historical_service_summary": service_output.get("service_summary") if 'service_output' in locals() else None,
            "replay_status": replay_result.get("status") if isinstance(replay_result, dict) else None,
            "calibration_status": calibration_status.get("status") if isinstance(calibration_status, dict) else calibration_status,
            "learning_status": learning_status.get("status") if isinstance(learning_status, dict) else learning_status,
            "probability_enhancement": probability_enhancement,
            "similarity_confidence": similarity_confidence,
            "candidate_ranking": candidate_ranking,
            "pdna_profile": pdna_profile,
        })
# ==========================================================
# MAIN ENTRY POINT
# ==========================================================

def main():
    """
    Enterprise runtime entry point.

    Used by NTIS app.py to execute the complete
    Historical Intelligence pipeline.
    """
    runtime = ProductionRuntime()

    result = runtime.run()

    print("=" * 70)
    print("HISTORICAL INTELLIGENCE COMPLETED")
    print("=" * 70)

    if isinstance(result, dict):
        print(f"Historical Records : {result.get('historical_records', 0)}")
        print(f"Evidence Records   : {result.get('evidence_records', 0)}")

    return result


if __name__ == "__main__":
    main()