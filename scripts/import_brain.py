#!/usr/bin/env python3
"""Safely import strategy files into one of the two fixed Brain packages.

The active ROS package remains stable.  An imported Brain is archived under
brains/<team>/<name>, while only the documented strategy allow-list is copied
into src/<active-package>.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

TEAM_PACKAGES = {"red": "brain_red_v3", "blue": "brain_blue_wangyifei_v1"}
FIXED_NAMES = {"main.cpp", "package.xml", "CMakeLists.txt", "launch.py"}
TEXT_EXTENSIONS = {".c", ".cc", ".cpp", ".h", ".hpp", ".py", ".xml", ".yaml", ".yml", ".json", ".md", ".txt"}


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def package_name(path: Path) -> str | None:
    try:
        return ET.parse(path / "package.xml").getroot().findtext("name")
    except (ET.ParseError, OSError):
        return None


def find_project_root(source: Path, expected: str) -> Path:
    all_dirs = [source] + [p for p in source.rglob("*") if p.is_dir()]
    package_candidates = [p for p in all_dirs if (p / "package.xml").is_file()]
    candidates = package_candidates or [
        p for p in all_dirs
        if (p / "src" / "brain_tree.cpp").is_file()
        or (p / "include" / "brain_tree.h").is_file()
        or (p / "behavior_trees").is_dir()
        or (p / "config").is_dir()
    ]
    if not candidates:
        return source

    def score(path: Path) -> tuple[int, int, int]:
        markers = sum((
            (path / "src" / "brain_tree.cpp").is_file(),
            (path / "include" / "brain_tree.h").is_file(),
            (path / "behavior_trees").is_dir(),
            (path / "config").is_dir(),
        ))
        depth = len(path.relative_to(source).parts)
        return (package_name(path) == expected, markers, -depth)

    return max(candidates, key=score)


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"unsafe ZIP path: {member.filename}")
    archive.extractall(destination)


def allowed(path: Path) -> bool:
    parts = path.as_posix().split("/")
    if parts[:1] == ["behavior_trees"] and path.suffix.lower() == ".xml":
        return True
    if parts[:1] == ["config"] and path.suffix.lower() in {".yaml", ".yml", ".json"}:
        return True
    return path.as_posix() in {"src/brain_tree.cpp", "include/brain_tree.h"}


def read_utf8(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def scan(root: Path, target: Path) -> tuple[list[str], list[str]]:
    risks: list[str] = []
    errors: list[str] = []
    patterns = {
        "brain_node_ext": re.compile(r"brain_node_ext"),
        "locator->reset()": re.compile(r"locator\s*->\s*reset\s*\(\s*\)"),
        "hard-coded ROS namespace": re.compile(r"create_(?:publisher|subscription).*namespace|\bnamespace\s*[:=]"),
        "extra GameController publisher": re.compile(r"create_publisher\s*<[^>]*(?:GameControl|RoboCup)", re.I),
        "possible malformed quote": re.compile(r"[\uFFFD\x00]|\\xEF\\xBF\\xBD"),
    }
    all_files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS]
    for path in all_files:
        text = read_utf8(path)
        if text is None:
            errors.append(f"not readable as UTF-8: {rel(path, root)}")
            continue
        for label, pattern in patterns.items():
            if pattern.search(text):
                location = rel(path, root)
                prefix = "ERROR" if allowed(path.relative_to(root)) and label == "locator->reset()" else "WARN"
                (errors if prefix == "ERROR" else risks).append(f"{label}: {location}")
        if "recoveryMsecsSince" in text and allowed(path.relative_to(root)):
            declaration = re.search(r"recoveryMsecsSince\s*\([^)]*\)\s*(const)?", text)
            definition = re.search(r"Brain::recoveryMsecsSince\s*\([^)]*\)\s*(const)?", text)
            if declaration and definition and bool(declaration.group(1)) != bool(definition.group(1)):
                errors.append(f"recoveryMsecsSince const mismatch: {rel(path, root)}")
    # Files that look like platform overrides are intentionally skipped.
    for path in all_files:
        rp = rel(path, root)
        if path.name in FIXED_NAMES or path.name in {"brain.cpp", "locator.cpp", "robot_client.cpp", "brain_communication.cpp"}:
            risks.append(f"platform file skipped: {rp}")
    return sorted(set(risks)), sorted(set(errors))


def validate_assets(files: list[Path], root: Path) -> list[str]:
    errors: list[str] = []
    for path in files:
        text = read_utf8(path)
        if text is None:
            errors.append(f"UTF-8 check failed: {rel(path, root)}")
            continue
        try:
            if path.suffix.lower() == ".xml":
                ET.fromstring(text)
            elif path.suffix.lower() == ".json":
                json.loads(text)
            elif path.suffix.lower() in {".yaml", ".yml"}:
                try:
                    import yaml  # type: ignore
                    yaml.safe_load(text)
                except ImportError:
                    if "\t" in text:
                        errors.append(f"YAML contains tabs and PyYAML is unavailable: {rel(path, root)}")
                except Exception as exc:
                    errors.append(f"YAML invalid: {rel(path, root)} ({exc})")
        except Exception as exc:
            errors.append(f"{path.suffix.upper()} invalid: {rel(path, root)} ({exc})")
    return errors


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
        return proc.returncode, proc.stdout[-20000:]
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", choices=TEAM_PACKAGES)
    parser.add_argument("--source", required=True)
    parser.add_argument("--name", required=True, help="version label: letters, digits, dot, underscore, or dash")
    parser.add_argument("--no-build", action="store_true", help="validate/copy only; useful on Windows without ROS 2")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    target = workspace / "src" / TEAM_PACKAGES[args.team]
    report: dict = {"team": args.team, "name": args.name, "target_package": TEAM_PACKAGES[args.team], "copied": [], "skipped": [], "risks": [], "errors": [], "build": {}, "rolled_back": False}
    source_arg = Path(args.source).expanduser().resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.name):
        report["errors"].append("name must be 1-64 characters: letters, digits, dot, underscore, or dash")
        return finish(workspace, report, 1)
    if not source_arg.exists():
        report["errors"].append(f"source does not exist: {source_arg}")
        return finish(workspace, report, 1)
    temp_dir: Path | None = None
    try:
        if source_arg.is_file() and source_arg.suffix.lower() == ".zip":
            temp_dir = Path(tempfile.mkdtemp(prefix="brain_import_"))
            with zipfile.ZipFile(source_arg) as archive:
                safe_extract(archive, temp_dir)
            source_root = find_project_root(temp_dir, target.name)
        elif source_arg.is_dir():
            source_root = find_project_root(source_arg, target.name)
        else:
            report["errors"].append("source must be a directory or .zip file")
            return finish(workspace, report, 1)
        if not target.is_dir():
            report["errors"].append(f"active target package missing: {target}")
            return finish(workspace, report, 1)
        imported_snapshot = workspace / "brains" / args.team / args.name
        if imported_snapshot.exists():
            report["errors"].append(f"brain version already exists: {imported_snapshot}")
            return finish(workspace, report, 1)
        source_package = package_name(source_root)
        if source_package and source_package != target.name:
            report["risks"].append(f"source package name {source_package!r} differs from active package {target.name!r}; package metadata will not be copied")
        risks, errors = scan(source_root, target)
        report["risks"].extend(risks)
        report["errors"].extend(errors)
        files = [p for p in source_root.rglob("*") if p.is_file()]
        selected = [p for p in files if allowed(p.relative_to(source_root))]
        report["skipped"] = sorted(rel(p, source_root) for p in files if p not in selected)
        report["errors"].extend(validate_assets(selected, source_root))
        if not selected:
            report["errors"].append("no allow-listed strategy files found")
        if report["errors"]:
            return finish(workspace, report, 1)
        imported_snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_root, imported_snapshot)
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = workspace / "brain_backups" / timestamp / args.team / target.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, backup)
        report["backup"] = rel(backup, workspace)
        active_file = workspace / "brains" / "active_brains.json"
        previous_active = json.loads(active_file.read_text(encoding="utf-8")) if active_file.exists() else {}
        try:
            for src in selected:
                dst = target / src.relative_to(source_root)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                report["copied"].append(rel(dst, workspace))
            active = dict(previous_active)
            active[args.team] = {"name": args.name, "package": target.name, "imported_at": dt.datetime.now(dt.timezone.utc).isoformat()}
            active_file.write_text(json.dumps(active, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            validation = subprocess.run([sys.executable, str(workspace / "scripts" / "validate_brain.py"), "--team", args.team, "--no-build"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            report["validation"] = {"returncode": validation.returncode, "output": validation.stdout[-12000:]}
            if validation.returncode != 0:
                raise RuntimeError("post-copy validation failed")
            if args.no_build:
                report["build"] = {"skipped": True, "reason": "--no-build"}
            else:
                bash = shutil.which("bash")
                if not bash:
                    raise RuntimeError("bash not found; run this importer in WSL or use --no-build")
                target_script = workspace / "scripts" / ("build_red_brain.sh" if args.team == "red" else "build_blue_brain.sh")
                code, output = run_command([bash, str(target_script)], workspace)
                report["build"]["target"] = {"returncode": code, "output": output}
                if code != 0:
                    raise RuntimeError("target Brain build failed")
                code, output = run_command([bash, str(workspace / "scripts" / "build_dual_brain.sh")], workspace)
                report["build"]["full"] = {"returncode": code, "output": output}
                if code != 0:
                    raise RuntimeError("full workspace build failed")
        except Exception as exc:
            report["errors"].append(str(exc))
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(backup, target)
            report["rolled_back"] = True
            active_file = workspace / "brains" / "active_brains.json"
            active_file.write_text(json.dumps(previous_active, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return finish(workspace, report, 1)
        report["enabled"] = {"team": args.team, "name": args.name, "package": target.name}
        return finish(workspace, report, 0)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        report["errors"].append(f"cannot read Brain source: {exc}")
        return finish(workspace, report, 1)
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def finish(workspace: Path, report: dict, code: int) -> int:
    report["risks"] = sorted(set(report.get("risks", [])))
    report["errors"] = sorted(set(report.get("errors", [])))
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = workspace / "brain_import_reports" / f"import_{report.get('team','unknown')}_{report.get('name','unknown')}_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report["report"] = rel(report_path, workspace)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[{'OK' if code == 0 else 'ERROR'}] report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
