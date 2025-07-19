#!/bin/bash
set -e

# Default to UID and GID 1000 if not passed as env vars
PUID=${PUID:-1000}
PGID=${PGID:-1000}

USERNAME=appuser
GROUPNAME=appgroup

# Check if group with PGID exists; if not, create it
if ! getent group "$PGID" >/dev/null 2>&1; then
    addgroup --gid "$PGID" "$GROUPNAME"
else
    GROUPNAME=$(getent group "$PGID" | cut -d: -f1)
fi

# Check if user with PUID exists; if not, create it
if ! id -u "$PUID" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" --uid "$PUID" --gid "$PGID" "$USERNAME"
else
    USERNAME=$(getent passwd "$PUID" | cut -d: -f1)
fi

# Fix ownership of /app directory to match the user/group
chown -R "$USERNAME:$GROUPNAME" /app

# Drop privileges and execute CMD
exec gosu "$USERNAME" "$@"
