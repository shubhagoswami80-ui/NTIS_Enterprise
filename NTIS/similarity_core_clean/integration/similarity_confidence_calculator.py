"""
NTIS Similarity Confidence Calculator v1.0

Bundle 02 - Historical Intelligence Layer

Combines similarity evidence score with base confidence
as an integration layer.
"""

class SimilarityConfidenceCalculator:

    def __init__(self):
        self.status = "READY"

    def calculate(self, similarity_result=None, evidence_scores=None):

        evidence_scores = evidence_scores or []

        evidence_confidence = 0

        if evidence_scores:
            evidence_confidence = sum(
                item.get("evidence_score", 0)
                for item in evidence_scores
            ) / len(evidence_scores)

        return {
            "status": "CALCULATED",
            "similarity_result": similarity_result or {},
            "evidence_confidence": evidence_confidence,
            "evidence_records": len(evidence_scores)
        }
