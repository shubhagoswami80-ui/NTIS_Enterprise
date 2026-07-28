
"""
HMME Learning Context V17
"""

class HMMELearningContextV17:

    def build(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Learning Context"] = "CREATED"

        return out
