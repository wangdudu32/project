#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
fi

MODE="${1:-web}"
case "$MODE" in
  help|--help|-h)
    printf '%s\n' '用法：bash run.sh [web|backend|cli 文件.pdf --num 3]' \
      '启动前请复制 .env.example 为 .env，并安装后端依赖和前端依赖。'
    exit 0 ;;
  cli)
    shift
    exec "$PYTHON_BIN" "$PROJECT_DIR/cli_app.py" "$@" ;;
  backend|web) ;;
  *)
    printf '%s\n' '未知模式，请使用 web、backend 或 cli。'
    exit 1 ;;
esac

export PYTHONPATH="$PROJECT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"
if [[ "$MODE" == backend ]]; then
  exec "$PYTHON_BIN" -m app.main
fi
if ! command -v npm >/dev/null 2>&1 || [[ ! -d frontend/node_modules ]]; then
  printf '%s\n' '请安装 Node.js 22，并在 frontend 目录执行 npm ci。'
  exit 1
fi

backend_pid=''
frontend_pid=''
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$backend_pid" ]] || kill "$backend_pid" 2>/dev/null || true
  [[ -z "$frontend_pid" ]] || kill "$frontend_pid" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"$PYTHON_BIN" -m app.main &
backend_pid=$!
(cd "$PROJECT_DIR/frontend" && exec npm run dev) &
frontend_pid=$!
printf '%s\n' '面试服务正在启动，访问地址见下方日志。按 Ctrl+C 停止。'
wait -n "$backend_pid" "$frontend_pid"
