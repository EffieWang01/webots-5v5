# Webots 5v5 Brain Simulator

这是一个运行在 Windows + WSL2 上的 5v5 机器人足球仿真项目，可在 Webots 中对比两套独立的 ROS 2 Brain。

## 运行要求

- Windows 10/11
- WSL2，并安装 Ubuntu 22.04
- Webots（已按 R2025a 测试）
- Windows 64 位 Python 3.10 或更高版本，并勾选 `Add python.exe to PATH`
- 首次配置时可以联网

ROS 2 Humble、colcon 和 Linux 编译依赖会由脚本自动安装，不需要在 Windows 安装 ROS。

## 最快运行方式

1. 把项目解压到 Windows 本地磁盘。
2. 第一次双击 `SETUP.cmd`，按提示输入一次 Ubuntu 的 `sudo` 密码。
3. 以后每次比赛只需双击 `START.cmd`。

也可以在项目目录执行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\SETUP.ps1
powershell.exe -ExecutionPolicy Bypass -File .\START.ps1
```

## 快速替换 Brain

直接把 Brain 的 ZIP 或文件夹拖到下面任一文件上：

- `REPLACE_BLUE_BRAIN.cmd`：替换蓝队
- `REPLACE_RED_BRAIN.cmd`：替换红队

也可以执行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\REPLACE_BRAIN.ps1 -Team blue -Source "C:\path\to\my_brain.zip"
```

脚本会自动停止旧进程、检查文件、备份当前 Brain、复制策略、编译，并在失败时回滚。允许替换的文件只有行为树、配置以及 `brain_tree.cpp/.h`；ROS 接口和包名保持固定，避免外部 Brain 把通信层改坏。

## 仿真与真实部分

Webots 模拟场地、球、机器人代理身体、移动、射门、碰撞、倒地/起身和比赛计时。红蓝双方 C++ Brain 的角色逻辑、行为树、移动与射门决策是真正运行的策略代码。

通信链路是：

```text
Webots（Windows）<-> 本机 PowerShell 中继 <-> ROS 2 与双方 Brain（WSL2）
```

它只使用本机 `10081-10083` 端口，不需要手填 WSL IP。
