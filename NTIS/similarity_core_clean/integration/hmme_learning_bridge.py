class HMMELearningBridge:

    def __init__(self):
        self.status = "READY"

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _is_valid_calibration_payload(feedback):
        if not isinstance(feedback, dict):
            return False

        required_fields = {
            "status",
            "calibration_status",
            "historical_strength",
            "evidence_quality",
            "replay_quality",
            "overall_quality",
            "calibration_summary",
            "replay",
        }
        if not required_fields.issubset(feedback):
            return False

        if feedback.get("status") not in {"CALIBRATED", "REJECTED_REPLAY"}:
            return False

        if not isinstance(feedback.get("calibration_summary"), dict):
            return False

        return True

    def collect_feedback(self, outcome_data=None):

        return {
            "status": "COLLECTED",
            "records": 0 if outcome_data is None else len(outcome_data)
        }

    def update_learning(self, feedback):

        if not self._is_valid_calibration_payload(feedback):
            return {
                "status": "REJECTED_CALIBRATION",
                "learning_status": "REJECTED_CALIBRATION",
                "learning_score": 0.0,
                "learning_confidence": None,
                "learning_summary": {
                    "historical_strength": 0.0,
                    "overall_quality": 0.0,
                    "learning_score": 0.0,
                    "learning_confidence": None,
                    "calibration_status": "REJECTED_CALIBRATION",
                },
                "calibration": feedback,
            }

        calibration_status = feedback.get("calibration_status")
        historical_strength = self._coerce_float(feedback.get("historical_strength"))
        evidence_quality = self._coerce_float(feedback.get("evidence_quality"))
        replay_quality = self._coerce_float(feedback.get("replay_quality"))
        overall_quality = self._coerce_float(feedback.get("overall_quality"))
        replay = feedback.get("replay")

        if historical_strength is None:
            historical_strength = 0.0
        if evidence_quality is None:
            evidence_quality = 0.0
        if replay_quality is None:
            replay_quality = 0.0
        if overall_quality is None:
            overall_quality = 0.0

        learning_score = feedback.get("learning_score")
        if learning_score is None:
            learning_score = round(
                (historical_strength + evidence_quality + replay_quality + overall_quality) / 4.0,
                4,
            )

        learning_confidence = feedback.get("learning_confidence")
        if learning_confidence is None and isinstance(replay, dict):
            replay_confidence = self._coerce_float(replay.get("replay_confidence"))
            if replay_confidence is not None:
                learning_confidence = round(replay_confidence, 4)

        learning_summary = {
            "historical_strength": historical_strength,
            "overall_quality": overall_quality,
            "learning_score": learning_score,
            "learning_confidence": learning_confidence,
            "calibration_status": calibration_status,
        }

        return {
            "status": "LEARNING_UPDATED",
            "learning_status": "LEARNING_UPDATED",
            "learning_score": learning_score,
            "learning_confidence": learning_confidence,
            "learning_summary": learning_summary,
            "calibration": feedback,
        }
