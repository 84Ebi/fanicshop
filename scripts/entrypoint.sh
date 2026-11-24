#!/bin/sh
# Apply migrations, then start the bot. Safe to re-run on every deploy.
set -eu
alembic upgrade head
exec python -m app.main
