
import pandas as pd

class IntradayOutputWriter:
    def write(self,records,output):
        pd.DataFrame(records).to_csv(output/'intraday_import_summary.csv',index=False)
