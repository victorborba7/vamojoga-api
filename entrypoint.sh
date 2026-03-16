#!/bin/sh
set -e

# Wait for PostgreSQL to be ready
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for database..."
  retries=30
  while [ $retries -gt 0 ]; do
    python -c "
import sys, asyncio, asyncpg, os, re
url = os.environ['DATABASE_URL']
# Convert SQLAlchemy URL to asyncpg format
url = re.sub(r'^postgresql\+asyncpg://', 'postgresql://', url)
async def check():
    conn = await asyncpg.connect(url, timeout=5)
    await conn.close()
try:
    asyncio.run(check())
    sys.exit(0)
except Exception:
    sys.exit(1)
" && break
    retries=$((retries - 1))
    echo "  Database not ready, retrying ($retries attempts left)..."
    sleep 2
  done
  if [ $retries -eq 0 ]; then
    echo "ERROR: Could not connect to database after 60s"
    exit 1
  fi
  echo "Database is ready!"
fi

echo "Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000