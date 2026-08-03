"""
NTIS HMME Real Replay Controller v2.0

Bundle 02 - Historical Intelligence Layer

Adds optional evidence-score forwarding to replay execution
while preserving existing controller behaviour.
"""


class HMMERealReplayController:

    def __init__(self):
        self.status = "READY"

    def run_replay(
        self,
        importer,
        replay_engine,
        filename=None,
        evidence_scores=None
    ):

        data = importer.import_file(filename) if filename else None

        return replay_engine.replay(
            data,
            evidence_scores=evidence_scores
        )
