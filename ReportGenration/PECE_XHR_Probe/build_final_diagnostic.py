from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent
PROD=ROOT.parent
SRC=PROD/"app.py"
DST=ROOT/"app_pece_manager_diagnostic.py"
EXPECTED="62c17d570bb019f5d24147ef10de20ba69090ae7"
if not SRC.exists(): raise SystemExit("SAFETY STOP: production app.py not found")
sha=subprocess.check_output(["git","hash-object",str(SRC)],text=True).strip()
if sha!=EXPECTED: raise SystemExit("SAFETY STOP: production app.py Git blob SHA mismatch: "+sha)
if DST.exists(): raise SystemExit("SAFETY STOP: diagnostic copy already exists")
text=SRC.read_text(encoding="utf-8")
text=text.replace('CFG = ROOT / "reports.json"','CFG = ROOT.parent / "reports.json"',1)
text=text.replace('PROFILE = ROOT / "browser_profile"','PROFILE = ROOT.parent / "browser_profile"',1)
if "pece_batch220_native_fast" not in text:
    anchor="class Manager:"
    if anchor not in text: raise SystemExit("SAFETY STOP: Manager anchor not found")
    text=text.replace(anchor,"from pece_batch220_native_fast import run_full_220\n\n"+anchor,1)
anchor='if cmd == "open":'
if 'cmd == "pece_full_220"' not in text:
    if anchor not in text: raise SystemExit("SAFETY STOP: open-command anchor not found")
    injection='''if cmd == "pece_full_220":
            try:
                result = run_full_220(context, str(ROOT / "pece_xhr_probe"), wait_first=10.0, concurrency=6)
                print("PECE 220:", result.get("status"), result.get("completed_count"), result.get("success_count"))
            except Exception as e:
                print("PECE 220 FAILED:", repr(e))
            continue

        '''
    text=text.replace(anchor,injection+anchor,1)
anchor="st.divider()"
if "RUN PE/CE ALL 220 STOCKS" not in text:
    if anchor not in text: raise SystemExit("SAFETY STOP: divider anchor not found")
    ui='''st.subheader("PE/CE 220 Diagnostic — Native XHR")
if st.button("RUN PE/CE ALL 220 STOCKS — FAST NATIVE XHR", disabled=status["running"]):
    manager.cmd("pece_full_220")
st.divider()
'''
    text=text.replace(anchor,ui,1)
DST.write_text(text,encoding="utf-8")
print("CREATED:",DST)
