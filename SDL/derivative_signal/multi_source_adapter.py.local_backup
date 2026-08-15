from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
import re
import pandas as pd

@dataclass(frozen=True)
class SourceSpec:
    role: str
    tokens: tuple[str, ...]
    required: bool = False
    priority: int = 0

@dataclass
class SourceBundle:
    trading_date: str
    files: dict[str, Path] = field(default_factory=dict)
    base_history: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rows: pd.DataFrame | None = None
    opening_rows: pd.DataFrame | None = None

SPECS = (
    SourceSpec("BASE", ("daywise_price_and_oi_summary", "daywise_price_and_oi"), True, 100),
    SourceSpec("FUTURES", ("futuresoi", "futures_oi", "future_oi"), False, 90),
    SourceSpec("IV", ("ivr-ivp", "ivr_ivp", "ivrivp"), False, 80),
    SourceSpec("SUPPORT", ("support",), False, 76),
    SourceSpec("RESISTANCE", ("resistance",), False, 75),
    SourceSpec("VOLUME", ("volumeandoispikesscans", "volume", "vol_oi", "volume_oi"), False, 70),
)

ALIASES = {
    "symbol": ("Symbol", "symbol", "Ticker", "ticker"),
    "open": ("Open", "open"), "high": ("High", "high"), "low": ("Low", "low"),
    "close": ("Close", "close", "CMP", "Current Price"),
    # IMPORTANT: exact percentage field only; never alias plain Price Chg into this field.
    "price_chg_pct": ("Price Chg %", "Price Chg (%)", "Price_Chg_Pct"),
    "atm_straddle_pct": ("ATM Straddle %", "ATM_Straddle_Pct"),
    "atm_straddle_price": ("ATM Straddle Price", "ATM_Straddle_Price"),
    "iv_chg_pct": ("IV Chg %", "IV Chg (%)", "IV_Chg_Pct"),
    "oi_chg_pct": ("OI Chg %", "OI Chg (%)", "OI_Chg_Pct"),
    "pcr_chg_pct": ("PCR Chg %", "PCR Chg (%)", "PCR_Chg_Pct"),
    "pe_ce_oi_chg": ("Tot PE-CE OI Chg", "PE-CE OI Chg", "PE_CE_OI_Chg"),
    "ivr": ("IVR", "IV Rank"), "ivp": ("IVP", "IV Percentile"),
    "fut_oi": ("Fut OI", "Future OI", "Futures OI"),
    "fut_oi_chg": ("Fut OI Chg", "Future OI Chg", "Futures OI Chg"),
    "fut_oi_chg_pct": ("Fut OI Chg %", "Future OI Chg %", "Futures OI Chg %"),
    "fut_buildup": ("Fut Buildup", "Future Buildup", "Futures Buildup"),
    "volume": ("Volume", "Tot Volume", "Total Volume"),
    "volume_chg_pct": ("Volume Chg %", "Volume Chg (%)", "Volume Change %"),
    "support": ("Support", "Support Level", "S/R Support"),
    "resistance": ("Resistance", "Resistance Level", "S/R Resistance"),
    "strike": ("Strike", "Relevant Strike"),
}


def _norm(v: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(v).lower())


def _find(df: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    cols = {_norm(c): c for c in df.columns}
    for alias in aliases:
        if _norm(alias) in cols:
            return cols[_norm(alias)]
    return None


def _family_match(path: Path, spec: SourceSpec) -> bool:
    name = _norm(path.stem)
    return any(_norm(token) in name for token in spec.tokens)


def _order_key(path: Path) -> tuple[int, float, str]:
    # Prefer explicit numeric copy/time suffixes when present, then mtime.
    stem = path.stem.lower()
    nums = re.findall(r"\((\d+)\)", stem)
    copy_no = int(nums[-1]) if nums else 0
    time_match = re.search(r"(?:_|-|\s)(\d{1,2})[.:_-](\d{2})(?:\b|$)", stem)
    hhmm = int(time_match.group(1))*100 + int(time_match.group(2)) if time_match else -1
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (max(hhmm, copy_no), mtime, path.name.lower())


def discover_sources(root: str | Path, trading_date: str) -> SourceBundle:
    root = Path(root)
    b = SourceBundle(trading_date=trading_date)
    if not root.exists() or not root.is_dir():
        b.errors.append(f"Source folder does not exist: {root}")
        return b
    files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {".xlsx", ".xls", ".xlsm"} and not p.name.startswith("~$")]

    base_candidates = sorted([p for p in files if _family_match(p, SPECS[0])], key=_order_key)
    b.base_history = base_candidates
    if base_candidates:
        b.files["BASE"] = base_candidates[-1]
    else:
        b.missing.append("BASE")

    for spec in SPECS[1:]:
        candidates = [p for p in files if _family_match(p, spec)]
        if candidates:
            b.files[spec.role] = max(candidates, key=_order_key)
    # Futures can also be supplied by the Support/Resistance reports.
    if "FUTURES" not in b.files and ("SUPPORT" in b.files or "RESISTANCE" in b.files):
        b.files["FUTURES"] = b.files.get("SUPPORT") or b.files.get("RESISTANCE")
    return b


def _canonicalize(raw: pd.DataFrame, role: str) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    for target, aliases in ALIASES.items():
        c = _find(raw, aliases)
        if c is not None:
            out[target] = raw[c]
    # Role-specific level mapping: Strike is the actual level in these reports.
    if role == "SUPPORT" and "support" not in out.columns and "strike" in out.columns:
        out["support"] = out["strike"]
    if role == "RESISTANCE" and "resistance" not in out.columns and "strike" in out.columns:
        out["resistance"] = out["strike"]
    out["_role"] = role
    return out


def _read(path: Path, role: str) -> pd.DataFrame:
    raw = pd.read_excel(path)
    raw.columns = [str(c).strip() for c in raw.columns]
    return _canonicalize(raw, role)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if "symbol" not in df.columns:
        return df.iloc[0:0].copy()
    df = df.copy()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df = df[df["symbol"].ne("") & df["symbol"].ne("NAN")]
    return df.drop_duplicates("symbol", keep="last")


def _coalesce(merged: pd.DataFrame, incoming: pd.DataFrame, role: str) -> pd.DataFrame:
    incoming = _clean(incoming)
    if incoming.empty:
        return merged
    lookup = incoming.set_index("symbol")
    for col in incoming.columns:
        if col in {"symbol", "_role", "strike"}:
            continue
        mapped = merged["symbol"].map(lookup[col])
        if col not in merged.columns:
            merged[col] = mapped
        else:
            merged[col] = merged[col].combine_first(mapped)
    merged[f"_source_{role}"] = True
    return merged


def load_and_merge(bundle: SourceBundle) -> SourceBundle:
    if not bundle.files:
        bundle.errors.append("No source files discovered.")
        return bundle
    frames: list[tuple[str, pd.DataFrame]] = []
    for role, path in bundle.files.items():
        try:
            frame = _clean(_read(path, role))
            if "symbol" not in frame.columns:
                bundle.errors.append(f"{role}: Symbol column not found in {path.name}")
                continue
            frames.append((role, frame))
        except Exception as exc:
            bundle.errors.append(f"{role}: {type(exc).__name__}: {exc}")
    if not frames:
        return bundle
    base = next((f for r, f in frames if r == "BASE"), frames[0][1])
    merged = base.drop(columns=["_role"], errors="ignore").copy()
    merged = _clean(merged)
    for role, frame in frames:
        if role != "BASE":
            merged = _coalesce(merged, frame, role)
    bundle.rows = merged

    # Opening snapshot for straddle progress: earliest BASE family file.
    if bundle.base_history:
        try:
            opening = _clean(_read(bundle.base_history[0], "BASE"))
            bundle.opening_rows = opening
        except Exception as exc:
            bundle.errors.append(f"BASE opening snapshot: {type(exc).__name__}: {exc}")
    return bundle
