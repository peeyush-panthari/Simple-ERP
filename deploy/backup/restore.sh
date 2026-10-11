#!/bin/sh
# Restore a Simple ERP dump.
#
#   restore.sh <dump-file> [target-database]      restore into a NEW database (default: <PGDATABASE>_restore)
#   restore.sh <dump-file> <db> --replace         drop and recreate <db> first (stop the api and worker before this)
#   restore.sh <dump-file> --documents-into <dir> also unpack the matching documents archive into <dir>
#
# Uses the libpq variables (PGHOST, PGPORT, PGUSER, PGPASSWORD). The dump's checksum is verified first.
# Restoring into a fresh database is the safe default: check it, then point DATABASE_URL at it or swap names.
set -eu

DUMP="${1:?usage: restore.sh <dump-file> [target-database] [--replace] [--documents-into <dir>]}"
shift
TARGET="${PGDATABASE:-simple_erp}_restore"
REPLACE=0
DOCDIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --replace) REPLACE=1 ;;
    --documents-into) shift; DOCDIR="$1" ;;
    *) TARGET="$1" ;;
  esac
  shift
done

if [ -f "$DUMP.sha256" ]; then
  ( cd "$(dirname "$DUMP")" && sha256sum -c "$(basename "$DUMP").sha256" ) || { echo "checksum mismatch - refusing to restore" >&2; exit 1; }
fi

MAINT="${PGMAINTDB:-postgres}"
exists="$(psql -d "$MAINT" -Atc "select 1 from pg_database where datname='$TARGET'")"
if [ -n "$exists" ]; then
  [ "$REPLACE" = 1 ] || { echo "database $TARGET already exists; pass --replace to drop it" >&2; exit 1; }
  psql -d "$MAINT" -qc "select pg_terminate_backend(pid) from pg_stat_activity where datname='$TARGET' and pid<>pg_backend_pid()" > /dev/null
  psql -d "$MAINT" -qc "drop database \"$TARGET\""
fi
psql -d "$MAINT" -qc "create database \"$TARGET\""
pg_restore --no-owner --exit-on-error --dbname="$TARGET" "$DUMP"
echo "restored $(basename "$DUMP") into $TARGET"

if [ -n "$DOCDIR" ]; then
  docs="${DUMP%.dump}.documents.tar.gz"
  if [ -f "$docs" ]; then mkdir -p "$DOCDIR" && tar -xzf "$docs" -C "$DOCDIR" && echo "documents unpacked into $DOCDIR"; else echo "no documents archive next to the dump"; fi
fi
