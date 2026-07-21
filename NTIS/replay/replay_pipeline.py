"""
NTIS Replay Pipeline
"""
class ReplayPipeline:
    def __init__(self):
        self.steps = []

    def add_step(self, step):
        self.steps.append(step)

    def run(self, data):
        for step in self.steps:
            data = step(data)
        return data
