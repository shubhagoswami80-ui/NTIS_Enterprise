from pathlib import Path
import pandas as pd


class HMMEProductionReport:

    def __init__(self):

        self.output_file = Path(
            "E:/NSE_Daily_Analysis/Output/hmme_production_report.csv"
        )


    def generate(self, data):

        rows = []

        for key, df in data.items():

            if df is not None:

                rows.append({
                    "Source": key,
                    "Rows": len(df)
                })


        report = pd.DataFrame(rows)

        report.to_csv(
            self.output_file,
            index=False
        )

        return self.output_file