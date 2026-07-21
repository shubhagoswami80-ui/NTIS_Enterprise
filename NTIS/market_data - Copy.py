"""
=========================================================
NTIS Market Data Manager
Version : 1.4

Purpose:
    Load NSE reports
    Create Master Dataset

Logic:

Support:
    Highest Put OI
    Strike < CMP
    Within 5% range

Resistance:
    Highest Call OI
    Strike > CMP
    Within 5% range

=========================================================
"""

import pandas as pd
from pathlib import Path

from config import DAILY_REPORTS, REPORT_FOLDERS
from utils import get_latest_file



class MarketData:


    def __init__(self):

        self.price_df = None
        self.volume_df = None
        self.support_df = None
        self.resistance_df = None
        self.ivr_df = None

        self.master_df = None



    # =====================================================
    # Symbol Cleaner
    # =====================================================

    def clean_symbol(self, value):

        if pd.isna(value):
            return None

        return (
            str(value)
            .strip()
            .upper()
            .replace("-EQ","")
            .replace(".NS","")
        )



    # =====================================================
    # Data Cleaner
    # =====================================================

    def clean_dataframe(self, df):

        if df is None:
            return None


        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )


        if "Symbol" in df.columns:

            df["Symbol"] = (
                df["Symbol"]
                .apply(self.clean_symbol)
            )


        numeric_columns = [

            "Price",
            "Strike",
            "OI",
            "OI Chg",
            "Put OI",
            "Call OI",
            "Put OI Chg",
            "Call OI Chg",
            "IV",
            "IVR",
            "IVP",
            "PCR"

        ]


        for col in numeric_columns:

            if col in df.columns:

                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(",","",regex=False)
                )

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )


        return df



    # =====================================================
    # Load Report
    # =====================================================

    def load_report(self, report_name):


        folder = DAILY_REPORTS / REPORT_FOLDERS[report_name]


        latest_file = get_latest_file(folder)


        print(
            f"Loading : {latest_file.name}"
        )


        if report_name == "ivr_ivp":

            df = pd.read_excel(
                latest_file,
                header=1
            )

        else:

            df = pd.read_excel(
                latest_file
            )


        return self.clean_dataframe(df)



    # =====================================================
    # Load All
    # =====================================================

    def load_all_reports(self):


        print("\nLoading Market Reports...\n")


        self.price_df = self.load_report(
            "price_oi"
        )

        self.volume_df = self.load_report(
            "volume_oi"
        )

        self.support_df = self.load_report(
            "support_oi"
        )

        self.resistance_df = self.load_report(
            "resistance_oi"
        )

        self.ivr_df = self.load_report(
            "ivr_ivp"
        )


        print(
            "\nAll market reports loaded.\n"
        )



    # =====================================================
    # CMP
    # =====================================================

    def get_cmp(self,symbol):


        for df in [

            self.ivr_df,
            self.volume_df,
            self.price_df

        ]:


            if df is None:
                continue


            if "Price" not in df.columns:
                continue



            row = df[
                df["Symbol"]==symbol
            ]


            if not row.empty:

                value=row.iloc[0]["Price"]


                if pd.notna(value):

                    return float(value)



        return None



    # =====================================================
    # Support Calculation
    # =====================================================

    def find_support(self,symbol,cmp):


        result={}


        if self.support_df is None:
            return result



        data=self.support_df[
            self.support_df["Symbol"]==symbol
        ].copy()



        if data.empty:
            return result



        # strike below CMP

        data=data[
            data["Strike"] < cmp
        ]



        # within 5%

        data=data[
            data["Strike"] >= cmp*0.95
        ]



        if data.empty:
            return result



        data=data.sort_values(
            "Put OI",
            ascending=False
        )


        row=data.iloc[0]



        distance=((cmp-row["Strike"])/cmp)*100



        return {

            "Support Strike":
                row["Strike"],

            "Support Put OI":
                row["Put OI"],

            "Support Put OI Chg":
                row["Put OI Chg"],

            "Support Distance %":
                round(distance,2),

            "Near Support":
                "YES" if distance<=0.5 else "NO"

        }



    # =====================================================
    # Resistance Calculation
    # =====================================================

    def find_resistance(self,symbol,cmp):


        result={}


        if self.resistance_df is None:
            return result



        data=self.resistance_df[
            self.resistance_df["Symbol"]==symbol
        ].copy()



        if data.empty:
            return result



        data=data[
            data["Strike"] > cmp
        ]



        data=data[
            data["Strike"] <= cmp*1.05
        ]



        if data.empty:
            return result



        data=data.sort_values(
            "Call OI",
            ascending=False
        )



        row=data.iloc[0]



        distance=((row["Strike"]-cmp)/cmp)*100



        return {


            "Resistance Strike":
                row["Strike"],


            "Resistance Call OI":
                row["Call OI"],


            "Resistance Call OI Chg":
                row["Call OI Chg"],


            "Resistance Distance %":
                round(distance,2),


            "Near Resistance":
                "YES" if distance<=0.5 else "NO"


        }



    # =====================================================
    # Build Master
    # =====================================================

    def build_master_dataset(self):


        print(
            "\nBuilding Master Dataset...\n"
        )


        records=[]


        for symbol in self.ivr_df["Symbol"].unique():


            row={}

            row["Symbol"]=symbol


            cmp=self.get_cmp(symbol)


            row["CMP"]=cmp



            for df in [

                self.price_df,
                self.volume_df,
                self.ivr_df

            ]:


                temp=df[
                    df["Symbol"]==symbol
                ]


                if not temp.empty:

                    row.update(
                        temp.iloc[0].to_dict()
                    )



            if cmp:


                row.update(
                    self.find_support(
                        symbol,
                        cmp
                    )
                )


                row.update(
                    self.find_resistance(
                        symbol,
                        cmp
                    )
                )



            records.append(row)



        self.master_df=pd.DataFrame(
            records
        )



        file=Path(
            "E:/NSE_Daily_Analysis/Output/market_master.csv"
        )


        file.parent.mkdir(
            exist_ok=True
        )


        self.master_df.to_csv(
            file,
            index=False
        )



        print(
            "Master Dataset Created"
        )

        print(
            f"Stocks : {len(self.master_df)}"
        )

        print(
            f"File   : {file}"
        )


        return self.master_df




    def summary(self):

        print("="*60)
        print("MARKET DATA SUMMARY")
        print("="*60)


        for name,df in {

            "Price & OI":self.price_df,
            "Volume & OI":self.volume_df,
            "Support":self.support_df,
            "Resistance":self.resistance_df,
            "IVR":self.ivr_df

        }.items():

            print(
                f"{name:<20}: {len(df)} rows"
            )





market=MarketData()



if __name__=="__main__":


    market.load_all_reports()

    market.summary()

    df=market.build_master_dataset()


    print("\nSample Output")
    print("-"*60)

    print(
        df.head()
    )