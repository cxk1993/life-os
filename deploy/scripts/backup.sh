#!/usr/bin/env bash
# B3 · SQLite 备份巡检：备份 + integrity_check + 保留策略 + 本地异地副本（可选）
# 用法：bash deploy/scripts/backup.sh
# 环境变量（可选）：
#   BACKUP_OFFSITE_DIR  异地目录（如 /mnt/e/... 或主人网盘路径）；未设则跳过异地
#   BACKUP_RETENTION_DAYS  保留天数，默认 30
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$ROOT/data/backups"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"
OFFSITE="${BACKUP_OFFSITE_DIR:-}"
mkdir -p "$OUT"
SRC="$ROOT/data/lifos.db"
if [[ ! -f "$SRC" ]]; then
  echo "FAIL: no db at $SRC"
  exit 1
fi
DEST="$OUT/lifos-$STAMP.db"
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$SRC" ".backup '$DEST'"
else
  cp -a "$SRC" "$DEST"
  cp -a "${SRC}-wal" "$DEST-wal" 2>/dev/null || true
  cp -a "${SRC}-shm" "$DEST-shm" 2>/dev/null || true
fi
# 完整性
if command -v sqlite3 >/dev/null 2>&1; then
  CHECK=$(sqlite3 "$DEST" "PRAGMA integrity_check;" | head -1)
  if [[ "$CHECK" != "ok" ]]; then
    echo "FAIL: integrity_check=$CHECK"
    exit 1
  fi
  echo "integrity_check: ok"
fi
# 保留
find "$OUT" -name 'lifos-*.db' -mtime "+$RETENTION" -delete 2>/dev/null || true
# 异地副本
if [[ -n "$OFFSITE" ]]; then
  mkdir -p "$OFFSITE"
  cp -a "$DEST" "$OFFSITE/"
  echo "offsite -> $OFFSITE/$(basename "$DEST")"
fi
echo "backup -> $DEST"
echo "retention_days=$RETENTION"
