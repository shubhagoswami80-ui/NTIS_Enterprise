"""
=========================================================
NTIS Intraday Probability Engine
Version : 1.4

Purpose:
    Convert Intraday score + pattern into probability.

Input:
    intraday_pattern_analysis.csv

Learning Input:
    intraday_probability_calibration.csv

Output:
    intraday_probability_analysis.csv

Update:
    - Added sample-size weighted learning
    - Small samples have limited influence
    - Preserves existing scoring logic
=========================================================
"""

from pathlib import Path
import pandas as pd

from intraday_path_config import get_today_output


OUTPUT_FOLDER = get_today_output()


INPUT_FILE = (
    OUTPUT_FOLDER /
    "intraday_pattern_analysis.csv"
)


OUTPUT_FILE = (
    OUTPUT_FOLDER /
    "intraday_probability_analysis.csv"
)


CALIBRATION_FILE = (
    OUTPUT_FOLDER /
    "intraday_probability_calibration.csv"
)



class IntradayProbabilityEngine:


    def __init__(self):

        self.historical_intelligence = (
            self.load_historical_intelligence()
        )


    def load_historical_intelligence(self):

        try:

            from intraday_intelligence_loader import (
                IntradayIntelligenceLoader
            )
            from intraday_intelligence_query import (
                IntradayIntelligenceQuery
            )

            loader = IntradayIntelligenceLoader()
            loader.load()

            return IntradayIntelligenceQuery(
                loader
            )

        except Exception:

            return None


    def pattern_probability(self, pattern):

        mapping = {

            "Fresh Long Buildup": 75,
            "Short Covering": 70,
            "Futures Long Setup": 75,
            "Volume Expansion": 60,
            "Short Buildup": 35,
            "Long Unwinding": 30,
            "Futures Short Setup": 30,
            "Neutral": 50

        }

        return mapping.get(
            pattern,
            50
        )



    def load_pattern_learning(self):

        if not CALIBRATION_FILE.exists():

            return {}


        calibration = pd.read_csv(
            CALIBRATION_FILE
        )


        learning = {}


        for _, row in calibration.iterrows():

            pattern = row.get(
                "Pattern"
            )

            quality = row.get(
                "Pattern Quality %",
                0
            )

            samples = row.get(
                "Signals",
                0
            )


            if pd.notna(pattern):

                learning[pattern] = {

                    "quality": float(quality),

                    "samples": int(samples)

                }


        return learning



    def learning_weight(
        self,
        samples
    ):

        if samples < 20:

            return 0.25


        elif samples <= 100:

            return 0.50


        return 1.0



    def learning_adjustment(
        self,
        pattern,
        learning
    ):


        data = learning.get(
            pattern
        )


        if data is None:

            return 0



        base = self.pattern_probability(
            pattern
        )


        quality = data["quality"]

        samples = data["samples"]


        weight = self.learning_weight(
            samples
        )


        difference = (
            quality - base
        )


        adjustment = (
            difference
            *
            weight
        )


        if adjustment > 10:

            adjustment = 10


        if adjustment < -10:

            adjustment = -10


        return adjustment



    def get_evidence_level(self, occurrences):
        try:
            occ = int(float(occurrences))
        except Exception:
            occ = 0
        if occ > 15:
            return "MATURE"
        elif occ >= 6:
            return "ESTABLISHED"
        elif occ >= 3:
            return "DEVELOPING"
        return "NEW"

    def compute_historical_intelligence(self, row, intelligence_query):
        if intelligence_query is None:
            return {
                "Historical_Probability": 50.0,
                "Historical_Confidence": 50.0,
                "Evidence_Level": "NEW",
                "Occurrences": 0,
                "Success_%": 0.0,
                "Average_PnL": 0.0,
                "Confidence_Score": 0.0
            }

        pattern_id = row.get("Pattern_ID", row.get("Business_Pattern_ID", ""))
        if not pattern_id:
            return {
                "Historical_Probability": 50.0,
                "Historical_Confidence": 50.0,
                "Evidence_Level": "NEW",
                "Occurrences": 0,
                "Success_%": 0.0,
                "Average_PnL": 0.0,
                "Confidence_Score": 0.0
            }

        try:
            summary = intelligence_query.historical_summary(pattern_id)
            occ = summary.get("Occurrences", 0)
            win_rate = summary.get("WinRate", summary.get("Success_%", 50.0))
            avg_pnl = summary.get("AveragePnL", summary.get("Average_PnL", 0.0))
            
            evidence_level = self.get_evidence_level(occ)
            
            hist_prob = float(win_rate) if occ > 0 else 50.0
            hist_prob = max(10.0, min(hist_prob, 95.0))
            
            hist_conf = round(min(100.0, (occ * 3.0) + (float(win_rate) * 0.7)), 2)

            return {
                "Historical_Probability": round(hist_prob, 2),
                "Historical_Confidence": hist_conf,
                "Evidence_Level": evidence_level,
                "Occurrences": occ,
                "Success_%": float(win_rate),
                "Average_PnL": float(avg_pnl),
                "Confidence_Score": hist_conf
            }
        except Exception:
            return {
                "Historical_Probability": 50.0,
                "Historical_Confidence": 50.0,
                "Evidence_Level": "NEW",
                "Occurrences": 0,
                "Success_%": 0.0,
                "Average_PnL": 0.0,
                "Confidence_Score": 0.0
            }



    def calculate_probability(
        self,
        row,
        learning
    ):


        score = row.get(
            "NTIS Intraday Score",
            0
        )


        pattern = row.get(
            "Pattern",
            "Neutral"
        )


        base = self.pattern_probability(
            pattern
        )


        adjustment = 0



        if score >= 70:

            adjustment += 15


        elif score >= 50:

            adjustment += 5


        elif score < 30:

            adjustment -= 15



        adjustment += self.learning_adjustment(
            pattern,
            learning
        )


        adjustment += self.historical_probability_adjustment(
            row,
            self.historical_intelligence
        )


        probability = (
            base
            +
            adjustment
        )


        probability = max(
            10,
            min(
                probability,
                95
            )
        )


        return round(
            probability,
            2
        )



    def confidence(
        self,
        probability
    ):

        if probability >= 75:

            return "HIGH"


        elif probability >= 55:

            return "MEDIUM"


        return "LOW"



    def run(self):


        df = pd.read_csv(
            INPUT_FILE
        )


        learning = (
            self.load_pattern_learning()
        )


        hist_results = df.apply(
            lambda row: self.compute_historical_intelligence(row, self.historical_intelligence),
            axis=1
        )
        df["Historical_Probability"] = [r["Historical_Probability"] for r in hist_results]
        df["Historical_Confidence"] = [r["Historical_Confidence"] for r in hist_results]
        df["Evidence_Level"] = [r["Evidence_Level"] for r in hist_results]


        df["Intraday Probability %"] = (

            df.apply(

                lambda row:

                self.calculate_probability(
                    row,
                    learning
                ),

                axis=1

            )

        )



        df["Confidence"] = (

            df["Intraday Probability %"]
            .apply(
                self.confidence
            )

        )



        df["Final Bias"] = "NEUTRAL"


        df.loc[

            df["Intraday Probability %"] >= 70,

            "Final Bias"

        ] = "BUY"



        df.loc[

            df["Intraday Probability %"] <= 35,

            "Final Bias"

        ] = "SELL"



        df = df.sort_values(

            "Intraday Probability %",

            ascending=False

        )



        df.to_csv(

            OUTPUT_FILE,

            index=False

        )


        return OUTPUT_FILE



if __name__ == "__main__":


    result = (

        IntradayProbabilityEngine()

        .run()

    )


    print("=" * 60)

    print(
        "INTRADAY PROBABILITY COMPLETE"
    )

    print(result)

    print("=" * 60)