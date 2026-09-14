import concurrent.futures
import os
import time
import zipfile
from datetime import datetime
import pandas as pd
import requests
import yfinance as yf

# Target storage directory path
LOG_FOLDER = r"D:\My-data\Share_P&L\ytdata"
PREVIOUS_STATE = {}


def is_market_hours():
    """Validates if execution fits inside official NSE trading hours."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_start <= now <= market_end


def archive_daily_log(target_date_str):
    """Compresses the day's tracking file into an optimized ZIP container at EOD."""
    csv_filename = f"nse_log_{target_date_str}.csv"
    csv_path = os.path.join(LOG_FOLDER, csv_filename)
    zip_path = os.path.join(LOG_FOLDER, f"nse_log_{target_date_str}.zip")

    if os.path.exists(csv_path) and not os.path.exists(zip_path):
        print(f"\n🤐 Post-market processing: Archiving {csv_filename}...")
        try:
            with zipfile.ZipFile(
                zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9
            ) as zipf:
                zipf.write(csv_path, arcname=csv_filename)
            os.remove(csv_path)
            print("📦 Compression complete. Raw data storage footprint minimized successfully.")
        except Exception as e:
            print(f"❌ Error while running archiving sequence: {e}")


def get_current_fno_tickers():
    """Fetches dynamic active F&O pool counters directly from official NSE feeds."""
    try:
        url = "https://nseindia.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            lines = response.text.split("\n")
            tickers = []
            for line in lines[5:]:
                parts = line.split(",")
                if len(parts) > 1:
                    symbol = parts.strip()
                    if (
                        symbol
                        and not symbol.startswith("MKT")
                        and symbol
                        not in [
                            "UNDERLYING",
                            "NIFTY",
                            "BANKNIFTY",
                            "FINNIFTY",
                            "MIDCPNIFTY",
                        ]
                    ):
                        tickers.append(f"{symbol}.NS")
            unique_tickers = sorted(list(set(tickers)))
            if unique_tickers:
                return unique_tickers
    except Exception:
        pass
    return [
        "RELIANCE.NS",
        "TCS.NS",
        "INFY.NS",
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "SBIN.NS",
    ]


def fetch_aggregated_data(ticker_symbol):
    """Gathers and maps underlying premium chains across workers."""
    try:
        stock = yf.Ticker(ticker_symbol)
        expirations = stock.options
        if not expirations:
            return None

        nearest_expiry = expirations
        opt_chain = stock.option_chain(nearest_expiry)

        calls = opt_chain.calls
        total_ce_volume = (
            int(calls["volume"].fillna(0).sum())
            if "volume" in calls.columns
            else 0
        )
        total_ce_oi = (
            int(calls["openInterest"].fillna(0).sum())
            if "openInterest" in calls.columns
            else 0
        )

        puts = opt_chain.puts
        total_pe_volume = (
            int(puts["volume"].fillna(0).sum())
            if "volume" in puts.columns
            else 0
        )
        total_pe_oi = (
            int(puts["openInterest"].fillna(0).sum())
            if "openInterest" in puts.columns
            else 0
        )

        return {
            "ticker": ticker_symbol,
            "expiry": nearest_expiry,
            "total_ce_volume": total_ce_volume,
            "total_pe_volume": total_pe_volume,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
        }
    except Exception:
        return None


def run_downloader():
    global PREVIOUS_STATE
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    current_date = now.strftime("%Y-%m-%d")

    tickers = get_current_fno_tickers()
    print(f"[{now_str}] Downloading option metrics across pool...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_aggregated_data, tickers))

    valid_records = [res for res in results if res is not None]

    if valid_records:
        current_df = pd.DataFrame(valid_records)
        current_df.insert(0, "timestamp", now_str)

        current_df["ce_volume_change"] = 0
        current_df["pe_volume_change"] = 0
        current_df["ce_oi_change"] = 0
        current_df["pe_oi_change"] = 0

        for idx, row in current_df.iterrows():
            ticker = row["ticker"]
            curr_ce_vol = row["total_ce_volume"]
            curr_pe_vol = row["total_pe_volume"]
            curr_ce_oi = row["total_ce_oi"]
            curr_pe_oi = row["total_pe_oi"]

            if ticker in PREVIOUS_STATE:
                prev = PREVIOUS_STATE[ticker]
                current_df.at[idx, "ce_volume_change"] = max(
                    0, curr_ce_vol - prev["ce_volume"]
                )
                current_df.at[idx, "pe_volume_change"] = max(
                    0, curr_pe_vol - prev["pe_volume"]
                )
                current_df.at[idx, "ce_oi_change"] = curr_ce_oi - prev["ce_oi"]
                current_df.at[idx, "pe_oi_change"] = curr_pe_oi - prev["pe_oi"]

            PREVIOUS_STATE[ticker] = {
                "ce_volume": curr_ce_vol,
                "pe_volume": curr_pe_vol,
                "ce_oi": curr_ce_oi,
                "pe_oi": curr_pe_oi,
            }

        optimized_df = current_df[
            (current_df["ce_volume_change"] > 0)
            | (current_df["pe_volume_change"] > 0)
        ].copy()

        if optimized_df.empty:
            print(" No active volume momentum shifts recorded in this window.")
            return

        final_cols = [
            "timestamp",
            "ticker",
            "expiry",
            "total_ce_volume",
            "ce_volume_change",
            "total_pe_volume",
            "pe_volume_change",
            "total_ce_oi",
            "ce_oi_change",
            "total_pe_oi",
            "pe_oi_change",
        ]
        output_df = optimized_df[final_cols]

        os.makedirs(LOG_FOLDER, exist_ok=True)
        file_path = os.path.join(LOG_FOLDER, f"nse_log_{current_date}.csv")

        file_exists = os.path.isfile(file_path)
        output_df.to_csv(file_path, mode="a", index=False, header=not file_exists)
        print(f" Saved {len(output_df)} active rows to storage layout.")
    else:
        print(" Empty capture window.")


INTERVAL_SECONDS = 5 * 60
print(f"🤖 Automated Storage Compressor Engine Online. Directing logs to: {LOG_FOLDER}")

while True:
    loop_start = time.time()
    now_check = datetime.now()

    if is_market_hours():
        run_downloader()
    else:
        PREVIOUS_STATE.clear()
        # Trigger EOD compression if active market hours just closed
        if now_check.hour >= 15 and now_check.minute >= 30:
            archive_daily_log(now_check.strftime("%Y-%m-%d"))

        print(
            f"[{now_check.strftime('%H:%M:%S')}] Market Closed (9:15 AM - 3:30 PM weekdays). Sleeping..."
        )

    elapsed = time.time() - loop_start
    sleep_time = max(5, INTERVAL_SECONDS - elapsed)
    time.sleep(sleep_time)
