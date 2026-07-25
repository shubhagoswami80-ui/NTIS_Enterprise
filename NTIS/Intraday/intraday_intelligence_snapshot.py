from pathlib import Path
import pandas as pd
class IntradayIntelligenceSnapshot:
    def run(self, source, output):
        df=pd.read_csv(source)
        df.to_csv(output,index=False)
        return output
