# W73 Source Contract v1

Approved external source root (configurable):
`NTIS_W73_SOURCE_ROOT`

Default:
`D:\My-data\Share_P&L\Ichart Data\Screenshot`

Rules:
- Month folder and trading-day folder are explicit inputs.
- The selected trading-day folder is read non-recursively.
- Only `Daywise_Price_and_OI_Summary_*.xlsx` files are accepted.
- Filename suffix `_YYYYMMDD_HHMMSS.xlsx` supplies the interval timestamp.
- Source files are read-only.
- No fallback to unrelated folders.
- PECE_Volume, PCR_Volume_Skew_Output, testrun and other sibling trees are not scanned.
- Live and replay use the same adapter.
