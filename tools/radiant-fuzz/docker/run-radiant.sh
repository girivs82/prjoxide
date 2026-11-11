#!/usr/bin/env bash
# Start (or re-enter) THE Radiant fuzzing container.
#
# Node-locked licence rules:
#  * Exactly one container may carry the licence host ID (MAC). This script
#    always uses the fixed name below, so Docker itself refuses a second one,
#    and it also refuses to start if any other container already uses the MAC.
#  * The MAC is read from docker/licence-mac (one line, e.g. 02:00:00:00:00:00).
#    That file is git-ignored: never commit the host ID.
set -euo pipefail

NAME=radiant-fuzz
IMAGE=radiant-fuzz:latest
HERE="$(cd "$(dirname "$0")" && pwd)"
LSCC="${LSCC:-$HOME/lscc}"                          # Radiant install + licence (host side)
PRJOXIDE="${PRJOXIDE:-$(cd "$HERE/../../.." && pwd)}"   # this prjoxide checkout
WORK="${WORK:-$HOME/src/radiant-work}"              # amd64 cargo target, installers, scratch

cmd="${1:-shell}"

case "$cmd" in
  build)
    docker build --platform linux/amd64 -t "$IMAGE" "$HERE"
    exit 0 ;;
  stop)
    docker stop "$NAME" >/dev/null && echo "stopped $NAME"
    exit 0 ;;
  rm)
    docker rm -f "$NAME" >/dev/null && echo "removed $NAME"
    exit 0 ;;
esac

MACFILE="$HERE/licence-mac"
if [[ ! -f "$MACFILE" ]]; then
  echo "ERROR: $MACFILE not found. Put the licence host ID there as a MAC address" >&2
  echo "       (e.g. 'echo 02:xx:xx:xx:xx:xx > $MACFILE'). It is git-ignored." >&2
  exit 1
fi
MAC="$(tr -d ' \t\r\n' < "$MACFILE" | tr 'A-F' 'a-f')"
if [[ ! "$MAC" =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]]; then
  echo "ERROR: $MACFILE does not contain a MAC address like 02:xx:xx:xx:xx:xx" >&2
  exit 1
fi

# Refuse if some other container already has the licence MAC.
for c in $(docker ps -aq); do
  n=$(docker container inspect -f '{{.Name}}' "$c" | sed 's#^/##')
  # Search the whole inspect JSON: where the MAC is recorded differs between
  # Docker API versions (.Config.MacAddress was removed in API 1.44+).
  if [[ "$n" != "$NAME" ]] && docker container inspect "$c" | grep -qi "$MAC"; then
    echo "ERROR: container '$n' already uses the licence MAC; remove it first." >&2
    exit 1
  fi
done

mkdir -p "$LSCC" "$WORK"
if ! docker container inspect "$NAME" >/dev/null 2>&1; then
  docker create --name "$NAME" --hostname radiant-fuzz \
    --platform linux/amd64 --mac-address "$MAC" \
    -v "$LSCC":/opt/lscc \
    -v "$WORK":/work \
    -v "$PRJOXIDE":/work/prjoxide \
    -it "$IMAGE" sleep infinity >/dev/null
  echo "created $NAME"
fi
[[ "$(docker container inspect -f '{{.State.Running}}' "$NAME")" == true ]] || docker start "$NAME" >/dev/null

case "$cmd" in
  shell) exec docker exec -it "$NAME" bash ;;
  exec)  shift; exec docker exec -i "$NAME" "$@" ;;
  *) echo "usage: $0 [build|shell|exec CMD...|stop|rm]" >&2; exit 2 ;;
esac
