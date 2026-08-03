# ---------------------------------------------------------------------
# Bundle 01 – Step 3
# Replacement: Intraday/intraday_trade_validation_engine.py
#
# ONLY functional change:
#   Preserve Pattern intelligence for downstream learning pipeline.
#
# Existing validation / risk / target logic remains unchanged.
# ---------------------------------------------------------------------

# Inside IntradayTradeValidationEngine.run()

def run(self):

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Missing input file: {INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    # -------------------------------------------------------------
    # Ensure historical intelligence columns always exist.
    # These are propagated only.
    # No business logic is changed.
    # -------------------------------------------------------------

    intelligence_columns = {
        "Pattern": "",
        "Pattern_DNA": "",
        "Pattern_ID": ""
    }

    for column, default in intelligence_columns.items():

        if column not in df.columns:

            df[column] = default

    # -------------------------------------------------------------
    # Existing validation logic
    # -------------------------------------------------------------

    df["Validation Signal"] = df.apply(
        self.validate_signal,
        axis=1
    )

    df["Risk Level"] = df.apply(
        self.risk_level,
        axis=1
    )

    (
        df[
            [
                "Entry Price",
                "Stop Loss",
                "Target"
            ]
        ]
    ) = df.apply(
        self.calculate_trade_levels,
        axis=1
    )

    # -------------------------------------------------------------
    # Preserve Pattern intelligence with trade candidates.
    # These columns are intentionally retained for:
    #
    # intraday_trade_memory_connector.py
    # intraday_learning_memory_builder.py
    # intraday_intelligence_loader.py
    # intraday_intelligence_query.py
    # Historical Evidence Layer
    # -------------------------------------------------------------

    preferred_order = [

        "Symbol",

        "Pattern",
        "Pattern_DNA",
        "Pattern_ID",

        "Intraday Probability %",
        "Validation Signal",
        "Risk Level",

        "Entry Price",
        "Stop Loss",
        "Target"
    ]

    ordered = [
        c
        for c in preferred_order
        if c in df.columns
    ]

    remaining = [
        c
        for c in df.columns
        if c not in ordered
    ]

    df = df[
        ordered + remaining
    ]

    df = df.sort_values(
        "Intraday Probability %",
        ascending=False
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    return OUTPUT_FILE