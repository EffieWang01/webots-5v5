# Release notes

## 1.0.2

- Fixed the WSL setup script: it now stores the ROS signing key in the correct
  binary keyring format, and automatically backs up the malformed source file
  created by the 1.0.1 preview before APT runs.

## 1.0.1

- Fixed Windows PowerShell parsing of single quotes in WSL path arguments.
- Corrected direct PowerShell commands in the README to use `ExecutionPolicy Bypass`.

## 1.0.0

- Initial public release.
