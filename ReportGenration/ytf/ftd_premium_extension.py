import concurrent.futures
import csv
import json
import os
import time
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf


# ============================================================
# Configuration
# ============================================================
LOG_FOLDER = r"D:\My-data\Share_P&L\ytdata"
STATE_CACHE_FILE = os.path.join(LOG_FOLDER, "collector_state.json")

# Set False for live market collection.
TEST_MODE = True

COLLECTION_INTERVAL_SECONDS = 300
MAX_WORKERS = 20

# Existing PCR/volume snapshot schema is preserved.
LEGACY_HEADERS = [
    "timestamp", "ticker", "expiry", "total_ce_volume",
    "ce_volume_change", "total_pe_volume", "pe_volume_change",
    "total_ce_oi", "ce_oi_change", "total_pe_oi",
    "pe_oi_change", "Bias_%"
]

# New additive premium/IV snapshot schema.
PREMIUM_HEADERS = [
    "timestamp",
    "ticker",
    "expiry",
    "spot",
    "strike",
    "call_last_price",
    "put_last_price",
    "call_bid",
    "call_ask",
    "put_bid",
    "put_ask",
    "call_iv",
    "put_iv",
    "atm_call_iv",
    "atm_put_iv",
    "call_25delta_iv",
    "put_25delta_iv",
    "atm_call_iv_change",
    "atm_put_iv_change",
    "call_25delta_iv_change",
    "put_25delta_iv_change",
    "call_delta",
    "put_delta",
    "delta_source",
]

STATE_CACHE = {}


def is_market_hours():
    if TEST_MODE:
        return True
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return (
        now.replace(hour=9, minute=15, second=0)
        <= now
        <= now.replace(hour=15, minute=30, second=0)
    )


def get_current_fno_tickers():
    try:
        response = requests.get(
            "https://nseindia.com",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if response.status_code == 200:
            values = []
            for line in response.text.splitlines()[5:]:
                parts = line.split(",")
                if len(parts) > 1:
                    symbol = parts[1].strip()
                    if symbol and not symbol.startswith("MKT"):
                        values.append(f"{symbol}.NS")
            if values:
                return sorted(set(values))
    except Exception:
        pass
    return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS"]


def load_state():
    global STATE_CACHE
    try:
        if os.path.isfile(STATE_CACHE_FILE):
            with open(STATE_CACHE_FILE, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            STATE_CACHE = raw if isinstance(raw, dict) else {}
    except Exception as exc:
        print(f"State cache load warning: {exc}")
        STATE_CACHE = {}


def save_state():
    os.makedirs(LOG_FOLDER, exist_ok=True)
    temporary = STATE_CACHE_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(STATE_CACHE, handle, separators=(",", ":"))
    os.replace(temporary, STATE_CACHE_FILE)


def number(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def first_valid(frame, column, default=None):
    if column not in frame.columns or frame.empty:
        return default
    value = frame[column].iloc[0]
    return number(value) if default is None else value


def find_spot(ticker):
    try:
        value = yf.Ticker(ticker).fast_info.get("last_price")
        return number(value)
    except Exception:
        return None


def select_nearest_row(frame, spot):
    if frame is None or frame.empty or "strike" not in frame.columns or spot is None:
        return None
    work = frame.copy()
    work["__distance"] = (pd.to_numeric(work["strike"], errors="coerce") - spot).abs()
    work = work.dropna(subset=["__distance"])
    if work.empty:
        return None
    return work.sort_values("__distance").iloc[0]


def select_delta_row(frame, target_delta):
    """Use a real delta column only. Never infer 25-delta from strike distance."""
    if frame is None or frame.empty:
        return None
    delta_column = next(
        (column for column in ("delta", "Delta", "greeks_delta", "optionDelta")
         if column in frame.columns),
        None,
    )
    if not delta_column:
        return None
    work = frame.copy()
    work["__delta_numeric"] = pd.to_numeric(work[delta_column], errors="coerce")
    work = work.dropna(subset=["__delta_numeric"])
    if work.empty:
        return None
    work["__distance"] = (work["__delta_numeric"] - target_delta).abs()
    return work.sort_values("__distance").iloc[0]


def value_from(row, column):
    if row is None or column not in row.index:
        return None
    return number(row[column])


def change_key(ticker, expiry, category):
    return f"{ticker}|{expiry}|{category}"


def calculate_change(key, current):
    if current is None:
        return None
    previous = STATE_CACHE.get(key)
    STATE_CACHE[key] = current
    if previous is None:
        return None
    previous_number = number(previous)
    if previous_number is None:
        return None
    return round(current - previous_number, 6)


def process_ticker(ticker, timestamp_str):
    try:
        stock = yf.Ticker(ticker)
        expirations = list(stock.options or [])
        expiry = expirations[0] if expirations else "N/A"

        # Existing aggregate PCR/volume/OI calculation.
        total_ce_volume = total_pe_volume = total_ce_oi = total_pe_oi = 0
        calls = pd.DataFrame()
        puts = pd.DataFrame()

        if expiry != "N/A":
            chain = stock.option_chain(expiry)
            calls = chain.calls.copy() if chain.calls is not None else pd.DataFrame()
            puts = chain.puts.copy() if chain.puts is not None else pd.DataFrame()

            if not calls.empty:
                total_ce_volume = int(pd.to_numeric(calls.get("volume", 0), errors="coerce").fillna(0).sum())
                total_ce_oi = int(pd.to_numeric(calls.get("openInterest", 0), errors="coerce").fillna(0).sum())
            if not puts.empty:
                total_pe_volume = int(pd.to_numeric(puts.get("volume", 0), errors="coerce").fillna(0).sum())
                total_pe_oi = int(pd.to_numeric(puts.get("openInterest", 0), errors="coerce").fillna(0).sum())

        if TEST_MODE:
            # Preserve test operation for the legacy page only.
            import random
            expiry = expiry if expiry != "N/A" else "2026-09-24"
            total_ce_volume = random.randint(50000, 150000)
            total_pe_volume = random.randint(50000, 150000)
            total_ce_oi = random.randint(10000, 50000)
            total_pe_oi = random.randint(10000, 50000)

        previous_legacy = STATE_CACHE.get(f"legacy|{ticker}")
        if isinstance(previous_legacy, list) and len(previous_legacy) == 4:
            prev_cv, prev_pv, prev_co, prev_po = previous_legacy
            ce_vol_change = max(0, total_ce_volume - prev_cv)
            pe_vol_change = max(0, total_pe_volume - prev_pv)
            ce_oi_change = total_ce_oi - prev_co
            pe_oi_change = total_pe_oi - prev_po
        else:
            ce_vol_change = pe_vol_change = ce_oi_change = pe_oi_change = 0

        STATE_CACHE[f"legacy|{ticker}"] = [
            total_ce_volume, total_pe_volume, total_ce_oi, total_pe_oi
        ]
        total_volume_change = ce_vol_change + pe_vol_change
        legacy_bias = (
            round(((ce_vol_change - pe_vol_change) / total_volume_change) * 100, 2)
            if total_volume_change else 0.0
        )
        legacy_row = [
            timestamp_str, ticker, expiry, total_ce_volume, ce_vol_change,
            total_pe_volume, pe_vol_change, total_ce_oi, ce_oi_change,
            total_pe_oi, pe_oi_change, legacy_bias
        ]

        # New premium/IV rows. One row per available strike.
        premium_rows = []
        spot = find_spot(ticker)
        if expiry != "N/A" and not calls.empty and not puts.empty:
            call_by_strike = calls.set_index("strike", drop=False)
            put_by_strike = puts.set_index("strike", drop=False)

            atm_call = select_nearest_row(calls, spot)
            atm_put = select_nearest_row(puts, spot)

            call_25 = select_delta_row(calls, 0.25)
            put_25 = select_delta_row(puts, -0.25)

            atm_call_iv = value_from(atm_call, "impliedVolatility")
            atm_put_iv = value_from(atm_put, "impliedVolatility")
            call_25_iv = value_from(call_25, "impliedVolatility")
            put_25_iv = value_from(put_25, "impliedVolatility")

            atm_call_change = calculate_change(change_key(ticker, expiry, "atm_call_iv"), atm_call_iv)
            atm_put_change = calculate_change(change_key(ticker, expiry, "atm_put_iv"), atm_put_iv)
            call_25_change = calculate_change(change_key(ticker, expiry, "call_25delta_iv"), call_25_iv)
            put_25_change = calculate_change(change_key(ticker, expiry, "put_25delta_iv"), put_25_iv)

            for strike in sorted(set(call_by_strike.index).intersection(set(put_by_strike.index))):
                call_row = call_by_strike.loc[strike]
                put_row = put_by_strike.loc[strike]
                premium_rows.append([
                    timestamp_str, ticker, expiry, spot, number(strike),
                    value_from(call_row, "lastPrice"), value_from(put_row, "lastPrice"),
                    value_from(call_row, "bid"), value_from(call_row, "ask"),
                    value_from(put_row, "bid"), value_from(put_row, "ask"),
                    value_from(call_row, "impliedVolatility"),
                    value_from(put_row, "impliedVolatility"),
                    atm_call_iv, atm_put_iv, call_25_iv, put_25_iv,
                    atm_call_change, atm_put_change, call_25_change, put_25_change,
                    value_from(call_25, "delta"), value_from(put_25, "delta"),
                    "source_delta_column" if call_25 is not None and put_25 is not None else "unavailable"
                ])

        return legacy_row, premium_rows
    except Exception as exc:
        print(f"{ticker}: {exc}")
        return None, []


def write_csv_atomic(rows, headers, path):
    if not rows:
        return None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return str(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return str(path)


def run_cycle():
    if not is_market_hours():
        return

    cycle_time = datetime.now().replace(second=0, microsecond=0)
    timestamp_str = cycle_time.strftime("%Y-%m-%d %H:%M:%S")
    tickers = get_current_fno_tickers()
    print(f"[{timestamp_str}] Executing extended option-chain collection...")

    legacy_rows = []
    premium_rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(process_ticker, ticker, timestamp_str)
            for ticker in tickers
        ]
        for future in concurrent.futures.as_completed(futures):
            legacy_row, rows = future.result()
            if legacy_row is not None:
                legacy_rows.append(legacy_row)
            premium_rows.extend(rows)

    day_folder = Path(LOG_FOLDER) / cycle_time.strftime("%Y-%m-%d")
    time_str = cycle_time.strftime("%H%M")

    legacy_path = write_csv_atomic(
        legacy_rows, LEGACY_HEADERS, day_folder / f"snapshot_{time_str}.csv"
    )
    premium_path = write_csv_atomic(
        premium_rows, PREMIUM_HEADERS, day_folder / f"premium_snapshot_{time_str}.csv"
    )

    save_state()
    print(f"[{timestamp_str}] Legacy rows: {len(legacy_rows)} | Premium rows: {len(premium_rows)}")
    print(f"Legacy snapshot: {legacy_path}")
    print(f"Premium snapshot: {premium_path}")


if __name__ == "__main__":
    os.makedirs(LOG_FOLDER, exist_ok=True)
    load_state()
    print(f"NSE extended collector started. TEST_MODE={TEST_MODE}")
    while True:
        try:
            run_cycle()
        except Exception as exc:
            print(f"Collector cycle error: {exc}")
        time.sleep(COLLECTION_INTERVAL_SECONDS)
