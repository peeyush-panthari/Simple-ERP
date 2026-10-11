#!/bin/sh
# Simple ERP backups: a verified Postgres dump plus the document files, kept for N generations.
#
#   backup.sh once     take one backup and exit (non-zero on any failure)
#   backup.sh loop     take one every BACKUP_INTERVAL_SECONDS, forever (what the compose `backup` service runs)
#   backup.sh status   print the age of the last good backup and exit non-zero if it is too old (healthcheck)
#
# Connection: the standard libpq variables (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE).
# BACKUP_DIR (default /backups)            where dumps go
# BACKUP_KEEP (default 14)                 how many generations to keep
# BACKUP_INTERVAL_SECONDS (default 86400)  loop period
# BACKUP_DOCUMENTS_DIR (default /data/documents)  tarred alongside the dump when it holds files
# BACKUP_POST_HOOK                         optional command run after a good backup with the dump path as $1,
#                                          e.g. 'rclone copy "$1" remote:simple-erp-backups' (the off-site copy)
#
# A backup only counts once pg_restore can read the dump back and its checksum is written; the dump is
# written under a temporary name and renamed, so a crash never leaves a half file that looks complete.
set -eu

DIR="${BACKUP_DIR:-/backups}"
KEEP="${BACKUP_KEEP:-14}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
DOCS="${BACKUP_DOCUMENTS_DIR:-/data/documents}"

log() { printf '%s backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

take_one() {
  mkdir -p "$DIR"
  ts="$(date -u +%Y%m%d-%H%M%S)"
  base="$DIR/simple-erp-$ts"
  log "dumping ${PGDATABASE:-?} from ${PGHOST:-localhost}"
  pg_dump --format=custom --compress=6 --no-owner --file="$base.dump.partial"
  pg_restore --list "$base.dump.partial" > /dev/null   # unreadable dump == failed backup
  mv "$base.dump.partial" "$base.dump"
  ( cd "$DIR" && sha256sum "simple-erp-$ts.dump" > "simple-erp-$ts.dump.sha256" )
  size="$(du -h "$base.dump" | cut -f1)"
  if [ -d "$DOCS" ] && [ -n "$(ls -A "$DOCS" 2>/dev/null)" ]; then
    tar -czf "$base.documents.tar.gz.partial" -C "$DOCS" .
    mv "$base.documents.tar.gz.partial" "$base.documents.tar.gz"
    log "documents archived ($(du -h "$base.documents.tar.gz" | cut -f1))"
  fi
  date +%s > "$DIR/LAST_OK"
  log "ok: $base.dump ($size)"
  if [ -n "${BACKUP_POST_HOOK:-}" ]; then
    sh -c "$BACKUP_POST_HOOK" hook "$base.dump" || log "WARNING: post-hook failed (the local backup is fine)"
  fi
  prune
}

prune() {
  # newest first; everything past KEEP goes, together with its checksum and document archive
  ls -1 "$DIR"/simple-erp-*.dump 2>/dev/null | sort -r | tail -n +"$((KEEP + 1))" | while read -r old; do
    stem="${old%.dump}"
    rm -f "$old" "$old.sha256" "$stem.documents.tar.gz"
    log "pruned $(basename "$stem")"
  done
}

status() {
  [ -f "$DIR/LAST_OK" ] || { echo "no successful backup yet"; exit 1; }
  age=$(( $(date +%s) - $(cat "$DIR/LAST_OK") ))
  echo "last good backup ${age}s ago"
  [ "$age" -le $(( INTERVAL * 2 + 600 )) ]
}

case "${1:-once}" in
  once) take_one ;;
  loop)
    log "every ${INTERVAL}s, keeping ${KEEP}"
    while true; do
      take_one || log "FAILED - retrying in 300s"
      if [ -f "$DIR/LAST_OK" ] && [ $(( $(date +%s) - $(cat "$DIR/LAST_OK") )) -lt 60 ]; then sleep "$INTERVAL"; else sleep 300; fi
    done ;;
  status) status ;;
  *) echo "usage: backup.sh once|loop|status" >&2; exit 2 ;;
esac
