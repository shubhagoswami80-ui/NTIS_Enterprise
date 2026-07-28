class HMMEHistoricalReplayAdapter:

    def __init__(self):
        self.status = "READY"

    def prepare_replay(self, historical_data=None):

        return {
            "status": "READY_FOR_REPLAY",
            "records": 0 if historical_data is None else len(historical_data)
        }

    def send_to_replay(self, replay_engine, data):

        return replay_engine.replay(data)
