REPORTGENRATION - ONLINE REPORT DOWNLOADER
==========================================

Location:
E:\NSE_Daily_Analysis\ReportGenration

Runtime:
Uses the existing Python environment:
E:\NSE_Daily_Analysis\NTIS\.venv

New dependency:
Playwright only. Already installed and verified.

No package installation is performed by the launcher.

START
-----
.\start_8506.ps1

Open:
http://localhost:8506

STOP APPLICATION
----------------
.\stop_8506.ps1

DAILY WORKFLOW
--------------
1. Start the utility.
2. Open/Login Session.
3. Log in normally in the browser if required.
4. Enter a destination folder for each enabled report.
5. Set Start and Stop time.
6. Press START DAILY RUN.
7. The utility downloads enabled reports at their configured intervals.
8. It stops automatically at the configured Stop time.
9. STOP NOW can stop the daily run manually.

IMPORTANT
---------
- Existing applications are not modified.
- No credentials are stored by this utility.
- Destination folders are entered at runtime and are not saved.
- The downloaded file is saved in the website's original downloaded format.
- Report 1 is enabled initially.
- Reports 2-6 are placeholders and remain disabled until configured.
- The current implementation first targets the native Download Data control.
- If the site's DOM uses a different download element, only that report's
  download_selector in reports.json needs to be set after inspection.
