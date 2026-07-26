class HMMEReplayEngine:

    def __init__(self):
        self.status = "READY"

    def replay(self, historical_data=None):

        return {
            "status": "REPLAY_COMPLETED",
            "records": 0 if historical_data is None else len(historical_data)
        }

    def evaluate(self, replay_result):

        return {
            "status": "EVALUATED",
            "replay": replay_result
        }
