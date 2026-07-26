class HMMEOutcomeCalibration:

    def __init__(self):
        self.status = "READY"

    def validate_outcome(self, replay_result=None):

        return {
            "status": "VALIDATED",
            "records": 0 if replay_result is None else len(replay_result)
        }

    def calibrate(self, outcome_result):

        return {
            "status": "CALIBRATED",
            "outcome": outcome_result
        }
