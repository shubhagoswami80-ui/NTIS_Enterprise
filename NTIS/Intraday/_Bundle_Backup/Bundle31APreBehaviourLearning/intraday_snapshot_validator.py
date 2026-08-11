import pandas as pd
def validate_snapshot(file):
    df=pd.read_csv(file)
    return [c for c in ['Symbol','Pattern'] if c not in df.columns]
