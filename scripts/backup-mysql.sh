#!/bin/sh
set -e

mkdir -p scripts/backups
filename="scripts/backups/event_system-$(date +%Y%m%d-%H%M%S).sql"
tmp="${filename}.tmp"

if docker compose exec -T mysql sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --databases event_system' > "$tmp"; then
  mv "$tmp" "$filename"
  echo "Backup written to $filename"
else
  rm -f "$tmp"
  echo "Backup failed" >&2
  exit 1
fi
