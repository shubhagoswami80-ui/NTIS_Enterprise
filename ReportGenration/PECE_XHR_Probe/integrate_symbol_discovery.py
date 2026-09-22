from pathlib import Path
import ast
import shutil
import re

TARGET = Path("app_pece_manager_diagnostic.py")
HELPER = Path("pece_control_discovery.py")
MARKER = "# PECE_SYMBOL_DISCOVERY_INTEGRATED_V1_2_1_AST"
IMPORT_LINE = "from pece_control_discovery import discover_pece_controls\n"

def read_source(path):
    return path.read_text(encoding="utf-8-sig").lstrip("\ufeff")

def main():
    if not TARGET.exists() or not HELPER.exists():
        raise SystemExit("SAFETY STOP: required diagnostic files missing")
    original = read_source(TARGET)
    if MARKER in original:
        print("ALREADY INTEGRATED: no changes made"); return
    if "from pece_manager_diagnostic import" not in original:
        raise SystemExit("SAFETY STOP: diagnostic import anchor not found")
    wm = re.search(r'(?m)^(?P<i>[ \\t]*)if command == [\"\']open[\"\']:\s*$', original)
    if not wm: raise SystemExit("SAFETY STOP: worker open-command anchor not found")
    wi=wm.group('i')
    wb=(f'{wi}if command == "pece_symbol_discovery":\n'
        f'{wi}    result = discover_pece_controls(\n'
        f'{wi}        context=context,\n'
        f'{wi}        target_url="https://www.icharts.in/opt/TotalPECEOIDiff_Beta.php",\n'
        f'{wi}        current_symbol=None,\n'
        f'{wi}        output_root=ROOT / "pece_xhr_probe",\n'
        f'{wi}    )\n'
        f'{wi}    self.state["last_pece_discovery"] = result\n'
        f'{wi}    continue\n\n')
    um=re.search(r'(?m)^(?P<i>[ \\t]*)col1,\s*col2,\s*col3,\s*col4\s*=\s*st\.columns\(4\)\s*$', original)
    if not um: raise SystemExit("SAFETY STOP: dashboard 4-column anchor not found")
    ui=um.group('i')
    ub=(f'{ui}st.divider()\n'
        f'{ui}st.subheader("PE/CE XHR Discovery — Temporary")\n'
        f'{ui}st.caption("Uses the existing authenticated Playwright context; discovery opens one temporary tab.")\n'
        f'{ui}if st.button("DISCOVER PE/CE STOCK CONTROL", key="pece_symbol_discovery"):\n'
        f'{ui}    manager.cmd("pece_symbol_discovery")\n'
        f'{ui}    time.sleep(0.4)\n'
        f'{ui}    st.rerun()\n\n')
    text=original.replace("from pece_manager_diagnostic import", IMPORT_LINE+"from pece_manager_diagnostic import",1)
    wm2=re.search(r'(?m)^(?P<i>[ \\t]*)if command == [\"\']open[\"\']:\s*$',text)
    um2=re.search(r'(?m)^(?P<i>[ \\t]*)col1,\s*col2,\s*col3,\s*col4\s*=\s*st\.columns\(4\)\s*$',text)
    wi2=wm2.group('i'); ui2=um2.group('i')
    wb=wb.replace(wi,wi2,1); ub=ub.replace(ui,ui2,1)
    text=text.replace(wm2.group(0),wb+wm2.group(0),1)
    text=text.replace(um2.group(0),ub+um2.group(0),1)
    text += "\n"+MARKER+"\n"
    ast.parse(text)
    backup=TARGET.with_suffix(TARGET.suffix+'.pre_ast_discovery')
    if backup.exists(): raise SystemExit("SAFETY STOP: backup already exists")
    shutil.copy2(TARGET,backup)
    TARGET.write_text(text,encoding='utf-8',newline='\n')
    ast.parse(read_source(TARGET))
    print('PATCHED:',TARGET)
    print('AST VALIDATION: PASS')
if __name__=='__main__': main()
