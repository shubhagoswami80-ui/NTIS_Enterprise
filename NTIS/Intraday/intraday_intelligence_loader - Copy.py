from pathlib import Path
import pandas as pd

class IntelligenceLoader:
    def load(self, file):
        return pd.read_csv(Path(file))
