#!/usr/bin/env bash
# SQLite 备份：复制 data 目录内 db 文件到 backups/（可 cron）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$ROOT/data/backups"
mkdir -p "$OUT"
SRC="$ROOT/data/lifos.db"
if [[ ! -f "$SRC" ]]; then
  echo "no db at $SRC"
  exit 1
fi
# WAL 模式：用 sqlite3 .backup 若可用，否则 cp
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$SRC" ".backup '$OUT/lifos-$STAMP.db'"
else
  cp -a "$SRC" "$OUT/lifos-$STAMP.db"
  cp -a "${SRC}-wal" "$OUT/lifos-$STAMP.db-wal" 2>/dev/null || true
  cp -a "${SRC}-shm" "$OUT/lifos-$STAMP.db-shm" 2>/dev/null || true
fi
find "$OUT" -name 'lifos-*.db' -mtime +30 -delete
echo "backup -> $OUT/lifos-$STAMP.db"
