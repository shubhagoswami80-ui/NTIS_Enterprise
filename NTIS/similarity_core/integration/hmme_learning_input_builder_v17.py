
"""
HMME Learning Input Builder V17
"""

class HMMELearningInputBuilderV17:

    def prepare(self, df):

        if df.empty:
            return df

        out = df.copy()
        out["Learning Status"] = "READY"

        return out
