
import pandas as pd

class IntradayReportParser:
    def detect_report_type(self, name):
        n=name.lower()
        rules={
            'PRICE_OI':['price','daywise'],
            'VOLUME_OI':['volume','spike'],
            'SUPPORT':['support'],
            'RESISTANCE':['resistance'],
            'IVR_IVP':['ivr','ivp'],
            'FUTURES_OI':['futures']
        }
        for k,v in rules.items():
            if any(x in n for x in v):
                return k
        return 'UNKNOWN'

    def load_excel(self,path):
        df=pd.read_excel(path)
        df.columns=[str(c).strip() for c in df.columns]
        return df
