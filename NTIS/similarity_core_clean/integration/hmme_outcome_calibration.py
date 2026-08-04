class HMMEOutcomeCalibration:

    def __init__(self):
        self.status = "READY"

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value)
        except Exception:
            return None

    def validate_outcome(self, replay_result=None):

        if not isinstance(replay_result, dict):
            return {
                "status": "REJECTED_REPLAY",
                "records": 0,
                "valid_records": 0,
                "matched_records": 0,
                "best_matches": [],
                "average_evidence_score": 0.0,
                "replay_confidence": None,
                "replay": replay_result,
                "valid": False,
            }

        status = replay_result.get("status")
        records = replay_result.get("records")
        valid_records = replay_result.get("valid_records")
        matched_records = replay_result.get("matched_records")
        best_matches = replay_result.get("best_matches")
        average_evidence_score = self._coerce_float(replay_result.get("average_evidence_score"))
        replay_confidence = self._coerce_float(replay_result.get("replay_confidence"))

        invalid = (
            status != "REPLAY_COMPLETED"
            or not isinstance(records, int)
            or records < 0
            or not isinstance(valid_records, int)
            or valid_records < 0
            or not isinstance(matched_records, int)
            or matched_records < 0
            or not isinstance(best_matches, list)
            or average_evidence_score is None
        )

        if invalid:
            return {
                "status": "REJECTED_REPLAY",
                "records": int(records) if isinstance(records, int) else 0,
                "valid_records": int(valid_records) if isinstance(valid_records, int) else 0,
                "matched_records": int(matched_records) if isinstance(matched_records, int) else 0,
                "best_matches": best_matches if isinstance(best_matches, list) else [],
                "average_evidence_score": average_evidence_score if average_evidence_score is not None else 0.0,
                "replay_confidence": replay_confidence,
                "replay": replay_result,
                "valid": False,
            }

        return {
            "status": "VALIDATED",
            "records": records,
            "valid_records": valid_records,
            "matched_records": matched_records,
            "best_matches": best_matches,
            "average_evidence_score": average_evidence_score,
            "replay_confidence": replay_confidence,
            "replay": replay_result,
            "valid": True,
        }

    def calibrate(self, outcome_result):

        if not isinstance(outcome_result, dict) or not outcome_result.get("valid"):
            return {
                "status": "REJECTED_REPLAY",
                "calibration_status": "REJECTED_REPLAY",
                "historical_strength": 0.0,
                "evidence_quality": 0.0,
                "replay_quality": 0.0,
                "overall_quality": 0.0,
                "calibration_summary": {
                    "records": 0,
                    "matched_records": 0,
                    "replay_confidence": None,
                    "average_evidence_score": 0.0,
                    "historical_strength": 0.0,
                    "overall_quality": 0.0,
                },
                "replay": outcome_result,
            }

        records = int(outcome_result.get("records", 0))
        matched_records = int(outcome_result.get("matched_records", 0))
        valid_records = int(outcome_result.get("valid_records", 0))
        average_evidence_score = float(outcome_result.get("average_evidence_score", 0.0))
        replay_confidence = outcome_result.get("replay_confidence")

        historical_strength = outcome_result.get("historical_strength")
        if historical_strength is None:
            historical_strength = round(average_evidence_score, 4)

        replay_quality = 0.0
        if valid_records > 0:
            replay_quality = round(matched_records / max(valid_records, 1), 4)

        evidence_quality = historical_strength
        if replay_confidence is not None:
            evidence_quality = round((float(historical_strength) + float(replay_confidence)) / 2.0, 4)

        overall_quality = outcome_result.get("overall_quality")
        if overall_quality is None:
            overall_quality = round((float(historical_strength) + float(evidence_quality) + float(replay_quality)) / 3.0, 4)

        return {
            "status": "CALIBRATED",
            "calibration_status": "CALIBRATED",
            "historical_strength": historical_strength,
            "evidence_quality": evidence_quality,
            "replay_quality": replay_quality,
            "overall_quality": overall_quality,
            "calibration_summary": {
                "records": records,
                "matched_records": matched_records,
                "replay_confidence": replay_confidence,
                "average_evidence_score": average_evidence_score,
                "historical_strength": historical_strength,
                "overall_quality": overall_quality,
            },
            "replay": outcome_result.get("replay"),
        }
