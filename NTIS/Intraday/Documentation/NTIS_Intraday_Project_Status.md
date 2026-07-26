# NTIS Intraday Project Status

## Architecture Status

Architecture is frozen.

Before any new module: 1. Check Module Registry. 2. Reuse existing owner
module. 3. Modify existing module where possible.

## Pipeline

Data Import → Market Master → Scoring → Pattern → Probability → Trade
Validation → Replay → Accuracy → Calibration → Learning Memory

## Rules

-   No duplicate files/modules.
-   Preserve working configuration.
-   Validate before moving forward.
-   Update change log after changes.
