# W73 Real Source Validation v1

Purpose:
Validate one real September26 day-folder interval through the W73 source boundary.

Default:
- Month folder: `September26`
- Trading date: `2026-09-18`
- Cutoff: `09:18:09`

The trading date comes from the selected day folder.
The filename timestamp is used only as the source interval timestamp.

This validation:
- reads the external source;
- never writes to the external source;
- writes only to W73's local `.cache` and `07_OUTPUT`;
- verifies required raw fields;
- verifies canonical mapping;
- verifies cache round-trip;
- explicitly reports that V8 state derivation is NOT_YET_DERIVED.

It does not manufacture V8 feature states from raw fields.
