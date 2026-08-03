"""
NTIS Historical Replay Adapter v2.0

Bundle 02 - Historical Intelligence Layer

Connects Historical Evidence records with replay execution
while preserving existing replay behaviour.
"""

from similarity_core_clean.integration.historical_evidence_contract import (
    HistoricalEvidenceRecord,
)


class HMMEHistoricalReplayAdapter:

    def __init__(self):
        self.status = "READY"

    def prepare_replay(self, historical_data=None):

        records = 0

        if historical_data is not None:
            records = len(historical_data)

        return {
            "status": "READY_FOR_REPLAY",
            "records": records
        }

    def prepare_evidence(self, evidence_records=None):

        valid_records = []

        if evidence_records:

            for record in evidence_records:

                if isinstance(record, HistoricalEvidenceRecord):
                    valid_records.append(record)

        return {
            "status": "EVIDENCE_READY",
            "records": len(valid_records),
            "data": valid_records
        }

    def send_to_replay(self, replay_engine, data):

        return replay_engine.replay(data)
