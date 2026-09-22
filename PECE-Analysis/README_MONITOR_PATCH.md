# Monitoring patch

This patch provides a separate live monitor. It does not stop or start any
process and does not affect your Streamlit applications.

Copy `monitor_pcr_volume.ps1` into:
`E:\NSE_Daily_Analysis\PECE-Analysis`

Run it from that folder with:
`powershell -ExecutionPolicy Bypass -File .\monitor_pcr_volume.ps1`

It checks for the PCR discovery process and displays the live status JSON.
The current discovery script must write `pcr_volume_skew_live_status.json`
for detailed stage/progress information to appear.
