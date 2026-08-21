from pathlib import Path

TARGET = Path(r"E:\NSE_Daily_Analysis\SDL\derivative_signal\dashboard.py")
text = TARGET.read_text(encoding="utf-8")

old_selected = """    day["previous_snapshot"] = _snapshot_rows(_read(path))
    day["source_file"] = str(path)
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)
    return result
"""

new_selected = """    # Keep raw previous_snapshot for the next signal calculation.
    # Persist the enriched decision separately so qualified/developing
    # candidates are never lost between processing and dashboard rendering.
    decision_rows = result.to_dict(orient="records") if not result.empty else []
    candidate_rows = [
        row for row in decision_rows
        if str(row.get("decision_state", "")).upper() in QUALIFIED_STATES
    ]
    day["previous_snapshot"] = _snapshot_rows(_read(path))
    day["decision_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in decision_rows
        if str(row.get("symbol", "")).strip()
    }
    day["candidate_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in candidate_rows
        if str(row.get("symbol", "")).strip()
    }
    day["source_file"] = str(path)
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)
    return result
"""

old_all = """    day["previous_snapshot"] = previous
    day["source_file"] = str(ordered[-1]) if ordered else ""
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)
    return latest_result, pd.DataFrame(timeline_rows)
"""

new_all = """    # previous_snapshot remains the raw calculation state.
    # decision_snapshot carries the complete enriched decision layer.
    # candidate_snapshot carries every developing/qualified candidate.
    decision_rows = latest_result.to_dict(orient="records") if not latest_result.empty else []
    candidate_rows = [
        row for row in decision_rows
        if str(row.get("decision_state", "")).upper() in QUALIFIED_STATES
    ]
    day["previous_snapshot"] = previous
    day["decision_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in decision_rows
        if str(row.get("symbol", "")).strip()
    }
    day["candidate_snapshot"] = {
        str(row.get("symbol", "")).upper(): row
        for row in candidate_rows
        if str(row.get("symbol", "")).strip()
    }
    day["source_file"] = str(ordered[-1]) if ordered else ""
    day["processed_at"] = datetime.now().isoformat()
    save_state(state, STATE_JSON)
    return latest_result, pd.DataFrame(timeline_rows)
"""

if old_selected not in text:
    raise SystemExit("ABORTED: selected-source persistence anchor not found.")
if old_all not in text:
    raise SystemExit("ABORTED: all-sources persistence anchor not found.")

text = text.replace(old_selected, new_selected, 1)
text = text.replace(old_all, new_all, 1)
TARGET.write_text(text, encoding="utf-8")

print("FIX APPLIED")
print(TARGET)
