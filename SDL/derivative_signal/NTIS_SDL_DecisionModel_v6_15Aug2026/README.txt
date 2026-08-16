NTIS SDL Decision Model v6

This bundle adds the evidence-based score/strength layer while preserving the frozen UI and the +/-0.75% hard gate.

Changes:
- 0-100 evidence score
- VERY STRONG / STRONG / MODERATE / WEAK / CONFLICTED strength
- S/R contributes to score
- First-range status contributes when supplied by the decision pipeline
- dashboard ranking uses decision score
- signal_engine.py is not changed
- SDL/data is not changed

Extract this folder under:
E:\NSE_Daily_Analysis\SDL\derivative_signal\NTIS_SDL_DecisionModel_v6_15Aug2026

Run:
powershell.exe -ExecutionPolicy Bypass -File ".\apply_decision_model_v6.ps1"

Send the complete output before restarting Streamlit. Do not commit until the 14-Aug 9:20 -> 10:16 acceptance test passes.
