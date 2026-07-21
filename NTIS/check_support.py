from market_data import market


market.load_all_reports()


symbol = "ABB"


print("\nChecking:", symbol)

print("\nIVR Data")
print(
    market.ivr_df[
        market.ivr_df["Symbol"] == symbol
    ]
)


print("\nSupport Data")
print(
    market.support_df[
        market.support_df["Symbol"] == symbol
    ]
)


print("\nResistance Data")
print(
    market.resistance_df[
        market.resistance_df["Symbol"] == symbol
    ]
)