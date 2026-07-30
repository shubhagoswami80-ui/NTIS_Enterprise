"""
NTIS Dashboard - Dashboard Metrics
"""
from __future__ import annotations
import pandas as pd

def calculate_dashboard_metrics(df: pd.DataFrame) -> dict:
    out = {}
    if "Probability" in df.columns:
        p = pd.to_numeric(df["Probability"], errors="coerce")
        out["Average Probability"] = round(p.mean(),2)
        out["Highest Probability"] = round(p.max(),2)
        out["Lowest Probability"] = round(p.min(),2)
    if "NTIS Score" in df.columns:
        s = pd.to_numeric(df["NTIS Score"], errors="coerce")
        out["Average Score"] = round(s.mean(),2)
        out["Median Score"] = round(s.median(),2)
    if {"Price","Support"}.issubset(df.columns):
        out["Avg Support Distance %"] = round((((df["Price"]-df["Support"])/df["Price"])*100).mean(),2)
    if {"Price","Resistance"}.issubset(df.columns):
        out["Avg Resistance Distance %"] = round((((df["Resistance"]-df["Price"])/df["Price"])*100).mean(),2)
    return out
