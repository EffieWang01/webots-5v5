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

## Run the complete simulation

The simulator is launched from **Windows**, not from a standalone WSL terminal. Webots and the relay run on Windows; ROS 2 Humble, the bridge, the game controller, and both five-robot Brain teams run inside WSL2.

### 1. Install the prerequisites

Install the following before the first run:

1. Enable WSL2 and install the exact Ubuntu release used by ROS 2 Humble. Run this in an Administrator PowerShell window, then restart Windows if requested:

   ```powershell
   wsl --install -d Ubuntu-22.04
   ```

2. Open **Ubuntu 22.04** once from the Start menu and finish creating its Linux user and password. The setup script will later ask for this password through `sudo`.
3. Install Webots for Windows. The scripts have been tested with **Webots R2025a**.
4. Install 64-bit Python **3.10 or newer** for Windows and enable **Add python.exe to PATH** in the installer.
5. Confirm the required programs from Windows PowerShell:

   ```powershell
   wsl --list --verbose
   python.exe --version
   ```

   `Ubuntu-22.04` should appear in the WSL list, and Python should report version 3.10 or newer.

### 2. Download the project

Keep the project on a local Windows drive such as `C:` or `D:`. Do not place it only inside the Linux filesystem.

```powershell
git clone https://github.com/EffieWang01/webots-5v5.git
cd webots-5v5
```

Downloading and extracting the GitHub ZIP to a local Windows folder also works.

### 3. Perform the one-time setup and build

From the project root, either double-click **`SETUP.cmd`** or run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\SETUP.ps1
```

This script checks WSL, Webots, and Windows Python, then installs ROS 2 Humble, `colcon`, and the required Linux packages inside Ubuntu. Finally, it resolves the ROS dependencies and builds both Brains and the simulator bridge. Internet access is required, and Ubuntu may ask for the Linux `sudo` password.

The first setup can take several minutes. It is complete when the terminal prints:

```text
[OK] WSL setup and build completed.
[OK] Setup complete. Double-click START.cmd to run a match.
```

If the build fails, fix the reported error and run `SETUP.cmd` again. Re-running setup is safe.

### 4. Start a match

For every simulation run, either double-click **`START.cmd`** or execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\START.ps1
```

`START.ps1` performs the entire startup sequence:

1. stops stale simulator processes from the previous run;
2. starts the Windows/WSL relay on local ports `10081-10083`;
3. starts the five RED and five BLUE ROS 2 Brain nodes, the game controller, and the Webots bridge in WSL;
4. opens `sim_webots/worlds/football_5v5_brain.wbt` in Webots.

If the workspace has not been built yet, `START.cmd` automatically runs the setup first. After Webots opens, wait for all ROS 2 nodes to initialize. The robots should then begin moving under Brain control.

### 5. Verify that everything is running

A successful launcher terminal ends with:

```text
[OK] Webots 5v5 Brain Simulator is starting.
Robots should begin moving after Webots and all ROS 2 nodes are ready.
```

For a detailed ROS link check, open an Ubuntu 22.04 WSL terminal, change to the project directory, source the workspace, and run:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
./scripts/healthcheck_webots_brain_5v5.sh
```

The check verifies all ten Brain nodes, the game controller, the Webots bridge, world-state messages, and movement command topics.

### 6. Stop or restart

Close Webots when the match is finished. To stop any remaining WSL nodes manually, run this inside WSL from the project directory:

```bash
./scripts/stop_webots_brain_5v5.sh
```

Normally, starting `START.cmd` again is enough: it cleans up the previous instance before launching a new match.

### Non-default installation paths

The default WSL distribution name is `Ubuntu-22.04`. If yours has another name, use the exact name shown by `wsl --list --verbose` for both setup and startup:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SETUP.ps1 -Distro "Ubuntu-22.04"
powershell.exe -ExecutionPolicy Bypass -File .\START.ps1 -Distro "Ubuntu-22.04"
```

Webots is detected from `WEBOTS_HOME`, the standard installation locations, or `PATH`. If detection fails, pass its executable explicitly to both commands:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SETUP.ps1 -WebotsPath "C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"
powershell.exe -ExecutionPolicy Bypass -File .\START.ps1 -WebotsPath "C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"
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
