# Downloader Portal — controlled parallel foundation

Target: `localhost:9001`

This is a new, isolated downloader framework. It does **not** modify or replace
the existing `ReportGenration` / port 8506 implementation.

## Design

- One portal manages all downloader jobs.
- Jobs have independent schedules and execution state.
- A slow/failed job does not block other jobs.
- Each browser job owns a dedicated Playwright Page/Tab.
- One persistent authenticated Chromium profile is shared by the portal's pages.
- The Playwright runtime is async and owns the browser from one dedicated event-loop
  thread; browser/page objects are not passed between worker threads.
- URL discovery inspects the authenticated page and proposes a configuration.
- High-confidence browser-download pages can be activated from the proposed config.
- XHR/fetch candidates are detected and recorded, but are not blindly converted into
  executable arbitrary requests. A transport adapter can be added after endpoint
  validation.
- Per-job timeout, retry, overlap prevention and structured logs are included.
- Destination paths support `{year}`, `{month}`, `{month_name}`, `{day}`, `{date}`,
  and `{time}`.

## First deployment

1. Copy the `DownloaderPortal` folder under `E:\NSE_Daily_Analysis`.
2. Review `config/portal.json`.
3. Run `start_9001.ps1`.
4. Open `http://localhost:9001`.
5. Add a URL and run **Discover**.
6. Review the proposed configuration.
7. Activate the job only after discovery is sensible.
8. Use a few test jobs first to prove parallel execution.

The existing 8506 application remains untouched during this validation phase.

## Important migration rule

Do not copy the old `reports.json` into this portal as an active production
configuration yet. Existing jobs are migrated only after parallel execution,
failure isolation, browser recovery and output separation have been validated.

Baseline inspected read-only from Git:
`a9ecfcd` — `Application:8506 Report Dpwnloader_Code (PECE report downloader -working state)-16-09,15.46PM`
