class HMMELearningBridge:

    def __init__(self):
        self.status = "READY"

    def collect_feedback(self, outcome_data=None):

        return {
            "status": "COLLECTED",
            "records": 0 if outcome_data is None else len(outcome_data)
        }

    def update_learning(self, feedback):

        return {
            "status": "UPDATED",
            "feedback": feedback
        }
