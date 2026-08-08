#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

PACKAGES = {"red": "brain_red_v3", "blue": "brain_blue_wangyifei_v1"}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", choices=PACKAGES, required=True)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    pkg = root / "src" / PACKAGES[args.team]
    errors: list[str] = []
    warns: list[str] = []
    required = [pkg/"package.xml", pkg/"CMakeLists.txt", pkg/"src"/"main.cpp", pkg/"src"/"brain.cpp", pkg/"src"/"brain_tree.cpp", pkg/"include"/"brain_tree.h", pkg/"behavior_trees"/"game.xml", pkg/"config"/"config_sim_truth.yaml"]
    for path in required:
        if not path.is_file(): errors.append(f"missing: {path.relative_to(root)}")
    if (pkg/"package.xml").is_file():
        try:
            actual = ET.parse(pkg/"package.xml").getroot().findtext("name")
            if actual != PACKAGES[args.team]: errors.append(f"package name is {actual!r}, expected {PACKAGES[args.team]!r}")
        except Exception as exc: errors.append(f"package.xml invalid: {exc}")
    for path in pkg.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".cpp", ".h", ".hpp", ".xml", ".yaml", ".yml", ".json"}: continue
        try: text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError: errors.append(f"not UTF-8: {path.relative_to(root)}"); continue
        if "\ufffd" in text or "\x00" in text: errors.append(f"obvious garbling: {path.relative_to(root)}")
        try:
            if path.suffix.lower() == ".xml": ET.fromstring(text)
            elif path.suffix.lower() == ".json": json.loads(text)
            elif path.suffix.lower() in {".yaml", ".yml"}:
                try:
                    import yaml  # type: ignore
                    yaml.safe_load(text)
                except ImportError: warns.append("PyYAML unavailable; YAML syntax was not fully parsed")
                except Exception as exc: errors.append(f"YAML invalid {path.relative_to(root)}: {exc}")
        except Exception as exc: errors.append(f"{path.suffix.upper()} invalid {path.relative_to(root)}: {exc}")
    cpp = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in [pkg/"src"/"main.cpp", pkg/"src"/"brain.cpp", pkg/"src"/"brain_tree.cpp"] if p.exists())
    if not re.search(r"(?:ext_name|brain_node_ext).*make_shared|make_shared.*(?:ext_name|brain_node_ext)", cpp, re.S): errors.append("main.cpp helper _ext node is missing")
    if len(re.findall(r"create_subscription\s*<[^>]*(?:GameControlData|RoboCupGameControlData)", cpp, re.I)) > 2: warns.append("multiple GameController subscriptions detected (main + helper may be intentional)")
    if re.search(r"create_publisher\s*<[^>]*(?:GameControl|RoboCup)", cpp, re.I): errors.append("Brain creates a GameController publisher")
    if "locator->reset()" in cpp:
        locator_header = (pkg/"include"/"locator.h").read_text(encoding="utf-8", errors="ignore") if (pkg/"include"/"locator.h").is_file() else ""
        if not re.search(r"\bvoid\s+reset\s*\(\s*\)\s*;", locator_header):
            errors.append("locator->reset() is used but Locator::reset is not declared")
    if "recoveryMsecsSince" in cpp:
        decl = re.search(r"recoveryMsecsSince\s*\([^)]*\)\s*(const)?", cpp)
        definition = re.search(r"Brain::recoveryMsecsSince\s*\([^)]*\)\s*(const)?", cpp)
        if decl and definition and bool(decl.group(1)) != bool(definition.group(1)): errors.append("recoveryMsecsSince declaration/definition const mismatch")
    if not args.no_build and not errors:
        bash = shutil.which("bash")
        if not bash: errors.append("bash not found; run in WSL or pass --no-build")
        else:
            proc = subprocess.run([bash, str(root/"scripts"/("build_red_brain.sh" if args.team == "red" else "build_blue_brain.sh"))], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
            if proc.returncode: errors.append("target Brain build failed\n" + proc.stdout[-12000:])
    for item in errors: print(f"[ERROR] {item}")
    for item in warns: print(f"[WARN] {item}")
    if not errors: print(f"[OK] {PACKAGES[args.team]} validation passed")
    return 1 if errors else 0

if __name__ == "__main__": raise SystemExit(main())
