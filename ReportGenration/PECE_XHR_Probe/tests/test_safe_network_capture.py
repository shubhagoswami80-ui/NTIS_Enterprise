from pathlib import Path
import py_compile
ROOT = Path(__file__).resolve().parents[1]
py_compile.compile(str(ROOT/"pece_network_capture.py"), doraise=True)
s = (ROOT/"pece_network_capture.py").read_text(encoding="utf-8")
assert "launch_persistent_context" not in s
assert "sync_playwright" not in s
assert "page.click" not in s
assert "context.new_page()" in s
assert "TotalPECEOIDiff_Beta.php" in s
assert "download_button_clicked" in s
print("PASS: safe network capture syntax/safety checks")
