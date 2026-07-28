class HMMERealReplayController:

    def __init__(self):
        self.status = "READY"

    def run_replay(self, importer, replay_engine, filename=None):

        data = importer.import_file(filename) if filename else None

        return replay_engine.replay(data)
