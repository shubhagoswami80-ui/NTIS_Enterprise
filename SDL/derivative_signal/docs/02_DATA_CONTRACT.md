# Data Contract v0.1

The derivative layer consumes existing SDL source outputs read-only.

## Required evidence
- Symbol
- Open, High, Low, Close/current price
- Futures OI change / buildup where the source field is available
- CE OI change
- PE OI change
- PE-CE OI change

## Optional evidence
- PCR / PCR change
- Volume / OI
- Support / resistance / strike distance
- IV / IVR / IVP / IV change
- Sector context

## Important rule
The current SDL source contract distinguishes the primary 20-column Price/OI/Straddle workbook from richer Futures OI, Volume/OI, IVR/IVP and Support/Resistance reports. The physical Futures-OI header/semantics must be verified from the live source before that field is used as a hard decision input.

## Timestamp
Do not silently infer a market timestamp from an unrelated filesystem timestamp. Use the timestamp supplied by the existing SDL intake/process path. If unavailable, mark timestamp precision as operational/unknown rather than inventing it.
