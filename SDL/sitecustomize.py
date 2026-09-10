
import atexit, json, os, sys, threading, time
from pathlib import Path

LOG = os.environ.get("SDL_PROFILE_LOG")
if not LOG:
    return_code = False
else:
    TARGETS = {
        "discover_historical_snapshots","discover_daywise_files",
        "process_latest_snapshot_for_today","process_snapshot",
        "_ensure_first_snapshot_base","_apply_frozen_base","_new_events",
        "save_approaching_breakouts","load_events","append_events",
        "save_daily_evidence","save_state","load_primary_snapshot",
        "read_source","build_current_predictions","evaluate_row",
        "latest_live","candidates","add_first_times",
    }
    _calls=[]; _started={}
    def _target(frame):
        name=frame.f_code.co_name
        fn=frame.f_code.co_filename.replace("\\","/")
        return (name in TARGETS and "/SDL/" in fn) or (
            name=="read_excel" and "/pandas/io/excel/" in fn
        )
    def _profile(frame,event,arg):
        if event not in ("call","return","exception") or not _target(frame): return
        key=(threading.get_ident(),id(frame))
        if event=="call":
            _started[key]=time.perf_counter()
        else:
            start=_started.pop(key,None)
            if start is not None:
                _calls.append({
                    "ts":time.time(),"thread":threading.get_ident(),
                    "function":frame.f_code.co_name,
                    "file":frame.f_code.co_filename,
                    "event":event,
                    "elapsed_ms":round((time.perf_counter()-start)*1000,3)
                })
    sys.setprofile(_profile)
    threading.setprofile(_profile)
    def _write():
        try:
            Path(LOG).parent.mkdir(parents=True,exist_ok=True)
            with open(LOG,"w",encoding="utf-8") as f:
                for x in _calls: f.write(json.dumps(x)+"\n")
        except Exception: pass
    atexit.register(_write)
