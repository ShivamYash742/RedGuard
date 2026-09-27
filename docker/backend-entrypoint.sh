#!/bin/sh
# Prepare the database, then run the given command.
#
#   1. First start: seed $DATABASE_URL from the image's committed demo data.
#   2. Every start: `prisma db push` — additive — brings it up to the current
#      schema. The committed dev.db has no Mode B lab_* tables; this adds them
#      to the *copy*, so /lab works out of the box.
#
# The committed seed file itself is never written: if DATABASE_URL points at
# it, the push is skipped with a warning.
set -e

SCHEMA=/app/backend/prisma/schema.prisma
SEED=/app/backend/prisma/dev.db

db_file="${DATABASE_URL#file:}"
case "$db_file" in
  /*) ;;
  *) db_file="/app/backend/prisma/${db_file#./}" ;;  # Prisma resolves relative to the schema
esac

if [ "$(realpath -m "$db_file")" = "$(realpath -m "$SEED")" ]; then
  echo "redguard: DATABASE_URL points at the committed demo database; not migrating it." >&2
  echo "redguard: set DATABASE_URL=file:/data/redguard.db to use a writable copy." >&2
else
  if [ ! -f "$db_file" ]; then
    mkdir -p "$(dirname "$db_file")"
    cp "$SEED" "$db_file"
    echo "redguard: seeded $db_file from the demo database"
  fi
  prisma db push --schema "$SCHEMA" --skip-generate
fi

exec "$@"
