#!/usr/bin/env bash
# GASF V1 七组 ROS 2 bag 一键实验脚本
# 用法: ./run_gasf.sh 1~7 [--no-rviz]
# 每次执行都会启动一个全新的 GASF 在线学习节点；不会修改原始 ROS bag。

set -e -o pipefail

usage() {
  cat <<'USAGE'
用法: ./run_gasf.sh <序号> [--no-rviz]

序号和实验对应关系：
  1 / 01   01_static       无外笼体静止
  2 / 02   02_static_A     笼体 A 静止
  3 / 03   03_arc_A        笼体 A 圆弧运动
  4 / 04   04_loop_A       笼体 A 回环运动（有雷达相对位移）
  5 / 05   05_static_B     笼体 B 静止
  6 / 06   06_arc_B        笼体 B 圆弧运动
  7 / 07   07_loop_B       笼体 B 回环运动

选项:
  --no-rviz   不启动 RViz2，适合纯 SSH / 无显示器测试
  -h, --help  显示帮助

示例:
  ./run_gasf.sh 3
  ./run_gasf.sh 07
  ./run_gasf.sh 4 --no-rviz

提示：开始前请停止手工启动的 GASF / bag 回放，避免同名节点或话题冲突。
USAGE
}

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

if [[ "$1" == "-h" || "$1" == "--help" || "$1" == "list" ]]; then
  usage
  exit 0
fi

case "$1" in
  1|01) EXPERIMENT="01_static" ;;
  2|02) EXPERIMENT="02_static_A" ;;
  3|03) EXPERIMENT="03_arc_A" ;;
  4|04) EXPERIMENT="04_loop_A" ;;
  5|05) EXPERIMENT="05_static_B" ;;
  6|06) EXPERIMENT="06_arc_B" ;;
  7|07) EXPERIMENT="07_loop_B" ;;
  *) echo "错误：无效序号 '$1'（只能选 1~7）" >&2; usage; exit 2 ;;
esac
shift

ENABLE_RVIZ=true
for arg in "$@"; do
  case "$arg" in
    --no-rviz) ENABLE_RVIZ=false ;;
    *) echo "错误：不支持的参数 '$arg'" >&2; usage; exit 2 ;;
  esac
done

# 如未来工作空间位置变化，可通过环境变量覆盖。
GASF_WS="${GASF_WS:-$HOME/cage_filter_ws}"
LIVOX_WS="${LIVOX_WS:-$HOME/livox_ros2_ws}"
BAG_ROOT="${GASF_BAG_ROOT:-$HOME/cage_bags}"
BAG_DIR="$BAG_ROOT/$EXPERIMENT"
RVIZ_CONFIG="$GASF_WS/rviz/gasf_v1.rviz"

for setup in /opt/ros/humble/setup.bash "$LIVOX_WS/install/setup.bash" "$GASF_WS/install/local_setup.bash"; do
  if [[ ! -f "$setup" ]]; then
    echo "错误：找不到环境文件 $setup" >&2
    echo "请先确认 ROS 2 Humble、Livox 驱动及 GASF 均已编译安装。" >&2
    exit 1
  fi
done
if [[ ! -f "$BAG_DIR/metadata.yaml" ]]; then
  echo "错误：未找到 ROS 2 bag 的 metadata.yaml：$BAG_DIR" >&2
  echo "请检查 ~/cage_bags/ 下的实验名称。" >&2
  exit 1
fi

# ROS 的 setup 脚本可能依赖未设置的可选环境变量，所以不启用 set -u。
source /opt/ros/humble/setup.bash
source "$LIVOX_WS/install/setup.bash"
source "$GASF_WS/install/local_setup.bash"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "错误：未找到 ros2 命令。" >&2
  exit 1
fi

if [[ "$ENABLE_RVIZ" == true && -z "${DISPLAY:-}" ]]; then
  echo "提示：当前没有 DISPLAY，自动切换为无 RViz2 模式。"
  ENABLE_RVIZ=false
fi
if [[ "$ENABLE_RVIZ" == true && ! -f "$RVIZ_CONFIG" ]]; then
  echo "提示：未找到 RViz 配置 $RVIZ_CONFIG，将跳过 RViz2。"
  ENABLE_RVIZ=false
fi
if [[ "$ENABLE_RVIZ" == true ]] && ! command -v rviz2 >/dev/null 2>&1; then
  echo "提示：未找到 rviz2 命令，将跳过 RViz2。"
  ENABLE_RVIZ=false
fi

RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
RUN_DIR="$GASF_WS/analysis/results/online_controls/runs/${EXPERIMENT}/${RUN_ID}"
mkdir -p "$RUN_DIR"
STATS_LOG="$RUN_DIR/stats.log"
NODE_LOG="$RUN_DIR/gasf_node.log"
BAG_LOG="$RUN_DIR/bag_play.log"
RVIZ_LOG="$RUN_DIR/rviz.log"
touch "$STATS_LOG"

NODE_PID=""
STATS_PID=""
RVIZ_PID=""
BAG_PID=""
TAIL_PID=""

cleanup() {
  trap - EXIT INT TERM
  echo
  echo "[GASF] 正在结束本次实验的进程……"
  # 向 ROS 2 进程发送 SIGINT，允许 ros2 launch 优雅关闭其子节点。
  for pid in "$TAIL_PID" "$BAG_PID" "$STATS_PID" "$RVIZ_PID" "$NODE_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  # 对仍未退出的进程发送 SIGTERM；不操作任何外部 ROS 进程。
  for pid in "$TAIL_PID" "$BAG_PID" "$STATS_PID" "$RVIZ_PID" "$NODE_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$TAIL_PID" "$BAG_PID" "$STATS_PID" "$RVIZ_PID" "$NODE_PID"; do
    if [[ -n "$pid" ]]; then wait "$pid" 2>/dev/null || true; fi
  done
  echo "[GASF] 实验记录保存在：$RUN_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '\n%s\n' '=================================================='
echo "实验：$EXPERIMENT"
echo "Bag：$BAG_DIR"
echo "模式：online（全新进程，空 Mask 冷启动）"
echo "RViz2：$ENABLE_RVIZ"
echo "日志：$RUN_DIR"
printf '%s\n\n' '=================================================='

# 先启动在线过滤器。
ros2 launch gasf_filter online.launch.py >"$NODE_LOG" 2>&1 &
NODE_PID=$!

# 等待统计话题创建，避免 bag 在节点启动之前开始播放。
READY=false
for i in $(seq 1 20); do
  if ! kill -0 "$NODE_PID" 2>/dev/null; then
    echo "错误：GASF 节点进程提前退出，请查看：$NODE_LOG" >&2
    tail -n 25 "$NODE_LOG" >&2 || true
    exit 1
  fi
  if [[ "$(ros2 topic type /gasf/stats 2>/dev/null || true)" == "std_msgs/msg/String" ]]; then
    READY=true
    break
  fi
  sleep 1
done
if [[ "$READY" != true ]]; then
  echo "错误：等待 /gasf/stats 超时。请检查：$NODE_LOG" >&2
  tail -n 25 "$NODE_LOG" >&2 || true
  exit 1
fi

echo "[GASF] 节点已启动，正在记录统计话题……"
ros2 topic echo /gasf/stats std_msgs/msg/String --field data >"$STATS_LOG" 2>&1 &
STATS_PID=$!
# 让 CLI 订阅进程先完成 DDS 发现，尽量避免丢失最初几条统计记录。
sleep 2
if ! kill -0 "$STATS_PID" 2>/dev/null; then
  echo "错误：统计订阅启动失败。请查看：$STATS_LOG" >&2
  exit 1
fi
# 在当前终端实时打印记录的统计信息。
tail -n 0 -f "$STATS_LOG" &
TAIL_PID=$!

if [[ "$ENABLE_RVIZ" == true ]]; then
  echo "[GASF] 加载 RViz2 配置：$RVIZ_CONFIG"
  rviz2 -d "$RVIZ_CONFIG" --ros-args -p use_sim_time:=true >"$RVIZ_LOG" 2>&1 &
  RVIZ_PID=$!
  sleep 2
  if ! kill -0 "$RVIZ_PID" 2>/dev/null; then
    echo "提示：RViz2 提前退出；回放仍将继续。查看：$RVIZ_LOG"
  fi
fi

echo "[GASF] 开始回放 $EXPERIMENT（Ctrl+C 可提前停止）……"
ros2 bag play "$BAG_DIR" --clock >"$BAG_LOG" 2>&1 &
BAG_PID=$!
if wait "$BAG_PID"; then
  BAG_PID=""
  echo "[GASF] ROS bag 播放结束。"
  sleep 1  # 留一点时间冲刷最后的统计日志。
else
  rc=$?
  BAG_PID=""
  echo "[GASF] ROS bag 回放异常退出（状态码 $rc），详情：$BAG_LOG" >&2
  exit "$rc"
fi
