# Next Execution Step

1. Put one real supplied source workbook into `data/input`.
2. Confirm its exact headers.
3. Confirm the source formula/semantics for `ATM Straddle %`.
4. Confirm the opening/base straddle premium derivation.
5. Remove the guard in `build_base_premium_map()` only after that formula is verified.
6. Run the two unit tests.
7. Process one real snapshot.
8. Verify the event CSV.
9. Start Streamlit on port 8504.
