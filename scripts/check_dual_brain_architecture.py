#!/usr/bin/env python3
from pathlib import Path
import json
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
expected = {
    "brain_red_v3": root / "src" / "brain_red_v3",
    "brain_blue_wangyifei_v1": root / "src" / "brain_blue_wangyifei_v1",
}
failed = False
for name, path in expected.items():
    package_name = ET.parse(path / "package.xml").getroot().findtext("name")
    status = "OK" if package_name == name else "FAIL"
    print(f"[{status}] {name}: {path}")
    failed |= package_name != name

config = json.loads((root / "sim_webots" / "config" / "bridge.json").read_text())
kickoff_ok = config.get("initial_kicking_team") == "red"
print("[OK] RED kickoff configured" if kickoff_ok else "[FAIL] RED kickoff missing")
failed |= not kickoff_ok
raise SystemExit(1 if failed else 0)
