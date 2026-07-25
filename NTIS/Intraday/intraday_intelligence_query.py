class IntelligenceQuery:
    def filter_symbol(self, df, symbol):
        return df[df["Symbol"] == symbol]
