# Webots 5v5 Brain Simulator

A Windows + WSL2 5v5 robot-football simulator for comparing two independent ROS 2 Brain strategies in Webots.

[简体中文说明](README.zh-CN.md)

## Requirements

- Windows 10 or 11
- WSL2 with **Ubuntu 22.04**
- Webots (tested with R2025a)
- 64-bit Python **3.10 or newer** for Windows, with `python.exe` on `PATH`
- Internet access during the first setup

ROS 2 Humble, colcon, and Linux build dependencies are installed automatically inside WSL. No Windows ROS installation is needed.

## Quick start

1. Extract the project to a local Windows drive.
2. Double-click **`SETUP.cmd`** once. Enter your Ubuntu `sudo` password when requested.
3. Double-click **`START.cmd`** for every match.

`START.cmd` also launches setup automatically when the WSL workspace has not been built.

PowerShell alternative:

```powershell
cd <project-folder>
powershell.exe -ExecutionPolicy Bypass -File .\SETUP.ps1
powershell.exe -ExecutionPolicy Bypass -File .\START.ps1
```

If the WSL distro has a different name:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SETUP.ps1 -Distro "Ubuntu-22.04"
powershell.exe -ExecutionPolicy Bypass -File .\START.ps1 -Distro "Ubuntu-22.04"
```

## Replace a Brain

The easiest method is to drag a Brain `.zip` file or folder onto:

- **`REPLACE_BLUE_BRAIN.cmd`** for BLUE
- **`REPLACE_RED_BRAIN.cmd`** for RED

Or run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\REPLACE_BRAIN.ps1 -Team blue -Source "C:\path\to\my_brain.zip"
powershell.exe -ExecutionPolicy Bypass -File .\REPLACE_BRAIN.ps1 -Team red  -Source "C:\path\to\opponent_brain"
```

The importer validates the files, backs up the active Brain, installs only the strategy layer, rebuilds the affected package, and rolls back automatically if validation or compilation fails.

Accepted strategy files:

```text
src/brain_tree.cpp
include/brain_tree.h
behavior_trees/**/*.xml
config/*.yaml, *.yml, *.json
```

Platform integration files and stable ROS package names are deliberately preserved. This makes Brain swaps repeatable and prevents an uploaded Brain from replacing the simulator bridge.

See [BRAIN_REPLACEMENT.md](BRAIN_REPLACEMENT.md) for the package format and recovery locations.

## What is simulated

Webots simulates the field, ball, robot proxy bodies, motion, kicks, collisions, falling/get-up, match timing, and world truth. The C++ ROS 2 Brain packages remain the real decision layer: role logic, behavior trees, movement commands, and shooting decisions come from the active Brains.

```text
Webots (Windows) <-> local PowerShell relay <-> ROS 2 + RED/BLUE Brains (WSL2)
```

The relay uses Windows localhost ports `10081-10083`. It does not require mirrored WSL networking or a hard-coded machine IP.

## Troubleshooting

- **Webots not found:** run `START.ps1` with `-WebotsPath "C:\...\webots.exe"` through `powershell.exe -ExecutionPolicy Bypass -File`.
- **Wrong distro:** pass `-Distro` to `SETUP.ps1` and `START.ps1`.
- **Robots do not move:** close the simulator, run `START.cmd` again, and wait for both Webots and the ROS terminals to finish starting.
- **Detailed link check:** in WSL, from the project folder, run `./scripts/healthcheck_webots_brain_5v5.sh`.
- **Brain import failure:** inspect `brain_import_reports/`; the previous Brain is restored automatically.

## License

Apache License 2.0. See [LICENSE](LICENSE).
