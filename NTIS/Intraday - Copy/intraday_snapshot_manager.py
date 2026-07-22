
from datetime import datetime
import pandas as pd

class SnapshotManager:
    def save(self,records,output):
        pd.DataFrame(records).to_csv(output/'intraday_snapshot_history.csv',index=False)
