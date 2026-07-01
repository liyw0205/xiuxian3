#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SERVER_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements.txt}"
HASH_FILE="$VENV_DIR/.requirements.sha256"

log() {
    printf '[xiuxian-migrate] %s\n' "$*"
}

fail() {
    printf '[xiuxian-migrate][error] %s\n' "$*" >&2
    exit 1
}

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    fail "未找到 $REQUIREMENTS_FILE，请确认迁移脚本位于 xiuxianserver/迁移脚本。"
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    log "创建 Python 虚拟环境：$VENV_DIR"
    if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        fail "创建虚拟环境失败。Ubuntu 可安装 python3-venv；Docker 请换用带 venv 的 Python 运行环境。"
    fi
fi

REQ_HASH="$(sha256sum "$REQUIREMENTS_FILE" | awk '{print $1}')"
OLD_HASH=""
if [ -f "$HASH_FILE" ]; then
    OLD_HASH="$(cat "$HASH_FILE")"
fi

if [ "$REQ_HASH" != "$OLD_HASH" ]; then
    log "安装或更新 Python 依赖"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
    "$VENV_DIR/bin/python" -m pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
    printf '%s\n' "$REQ_HASH" > "$HASH_FILE"
else
    log "依赖未变化，跳过安装"
fi

scripts=()
if [ "$#" -gt 0 ] && [[ "$1" == *.py ]]; then
    script_path="$1"
    shift
    if [ ! -f "$script_path" ]; then
        script_path="$SCRIPT_DIR/$script_path"
    fi
    [ -f "$script_path" ] || fail "未找到迁移脚本：$script_path"
    scripts+=("$script_path")
else
    while IFS= read -r script_path; do
        scripts+=("$script_path")
    done < <(find "$SCRIPT_DIR" -maxdepth 1 -type f -name '20*.py' | sort)
fi

if [ "${#scripts[@]}" -eq 0 ]; then
    fail "没有找到可执行的迁移脚本。"
fi

for script_path in "${scripts[@]}"; do
    log "执行迁移：$(basename "$script_path")"
    "$VENV_DIR/bin/python" "$script_path" "$@"
done

log "迁移完成"
