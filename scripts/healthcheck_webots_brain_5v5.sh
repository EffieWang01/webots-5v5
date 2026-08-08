#!/usr/bin/env bash
set -o pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
ok(){ echo "[OK] $1"; }
warn(){ echo "[WARN] $1"; }
err(){ echo "[ERROR] $1"; fail=1; }

if ! command -v ros2 >/dev/null 2>&1; then err "ros2 command not found (source ROS 2 Humble first)"; exit $fail; fi
nodes="$(ros2 node list 2>/dev/null || true)"
for team in red blue; do
  count=0
  for i in 1 2 3 4 5; do
    if grep -qx "/brain_${team}_${i}" <<<"$nodes"; then count=$((count+1)); else warn "missing /brain_${team}_${i}"; fi
  done
  [[ $count -eq 5 ]] && ok "$team: 5 Brain nodes" || err "$team: $count/5 Brain nodes"
done
grep -qx "/sim_game_controller" <<<"$nodes" && ok "sim_game_controller exists" || err "sim_game_controller missing"
grep -qx "/webots_ros2_bridge" <<<"$nodes" && ok "webots_ros2_bridge exists" || err "webots_ros2_bridge missing"

gc_info="$(ros2 topic info -v /robocup/game_controller 2>/dev/null || true)"
pub_count="$(grep -E '^Publisher count:' "$gc_info" | awk '{print $3}' | head -1)"
[[ "$pub_count" == "1" ]] && ok "/robocup/game_controller has one publisher" || err "/robocup/game_controller publisher count: ${pub_count:-unknown}"

if timeout 8 ros2 topic hz --window 3 /webots/world_state >/tmp/webots_5v5_world_hz.txt 2>&1; then ok "/webots/world_state has normal frequency"; else err "/webots/world_state has no measurable frequency"; fi
topics="$(ros2 topic list 2>/dev/null || true)"
move_count=0
for team in red blue; do for i in 1 2 3 4 5; do grep -qE "(/LocoApiTopic/${team}_${i}Req|/LocoApiTopic/${team}_${i}Req)" <<<"$topics" && move_count=$((move_count+1)) || true; done; done
[[ $move_count -ge 10 ]] && ok "red/blue movement command topics visible ($move_count)" || warn "movement command topics visible: $move_count/10 (topic naming may be remapped)"
sample_topic="/LocoApiTopic/red_1Req"
if grep -qx "$sample_topic" <<<"$topics" && timeout 6 ros2 topic echo --once "$sample_topic" >/tmp/webots_5v5_red_cmd.txt 2>&1; then
  ok "red movement command has messages"
else
  warn "no sample red movement command message within 6 seconds"
fi
if grep -qE '^/kick_ball/(red|blue)_[1-5]$' <<<"$topics"; then ok "kick command topics visible"; else warn "kick command topics not currently visible (kick is event-driven)"; fi
echo "Healthcheck complete."
exit $fail
