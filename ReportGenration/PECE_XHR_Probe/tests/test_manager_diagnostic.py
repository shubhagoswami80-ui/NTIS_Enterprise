from pathlib import Path
import py_compile
root=Path(__file__).resolve().parents[1]
for f in ("pece_manager_diagnostic.py","build_manager_diagnostic.py"):
    py_compile.compile(str(root/f), doraise=True)
s=(root/"pece_manager_diagnostic.py").read_text(encoding="utf-8")
assert "context.new_page()" in s
assert "TotalPECEOIDiff_Beta.php" in s
assert "launch_persistent_context" not in s
assert "sync_playwright" not in s
assert "page.click" not in s
assert "download_button_clicked" in s
print("PASS: Manager diagnostic safety/syntax checks")
