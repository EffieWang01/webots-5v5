# Brain replacement contract

The simulator keeps two stable ROS 2 packages:

| Team | Active package |
|---|---|
| RED | `src/brain_red_v3` |
| BLUE | `src/brain_blue_wangyifei_v1` |

A Brain ZIP may contain a complete package or only the strategy files. One optional top-level directory is supported. The importer copies only:

```text
src/brain_tree.cpp
include/brain_tree.h
behavior_trees/**/*.xml
config/*.yaml
config/*.yml
config/*.json
```

Files such as `package.xml`, `CMakeLists.txt`, `main.cpp`, `brain.cpp`, ROS interfaces, and bridge code are not replaced. If a strategy genuinely requires a platform API change, review and merge that change separately instead of bypassing this safety boundary.

Each import produces:

- an immutable snapshot in `brains/<team>/<version>`;
- a pre-import backup in `brain_backups/<timestamp>`;
- a JSON report in `brain_import_reports/`.

The previous working Brain is restored automatically when validation or compilation fails.
Drag-and-drop imports append a timestamp to the source name, so an updated ZIP can be imported repeatedly without overwriting its earlier snapshot.
