#!/bin/sh
i=0
while ! docker info >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "Docker daemon did not start within 30 seconds" >&2
    exit 1
  fi
  sleep 1
done
