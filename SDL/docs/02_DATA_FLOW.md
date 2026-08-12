# SDL Phase-1 Data Flow

Source snapshot
→ source_loader
→ normalized primary rows
→ straddle_calculator
→ derived Total ATM Straddle Premium
→ base/threshold calculation
→ first-crossing detector
→ compact event CSV
→ Streamlit dashboard

Normal rows are processed but not permanently stored as intelligence events.
