#!/bin/sh
set -eu

export IPFS_PATH="${IPFS_PATH:-/data/ipfs}"

mkdir -p "$IPFS_PATH" /app/Upload /app/Synced_dir /app/data/logs

if [ ! -f "$IPFS_PATH/config" ]; then
  echo "[entrypoint] init Kubo repo at $IPFS_PATH"
  ipfs init --profile=server
fi

# API только внутри контейнера. Swarm снаружи — для публичной сети.
ipfs config Addresses.API /ip4/127.0.0.1/tcp/5001
ipfs config Addresses.Gateway /ip4/0.0.0.0/tcp/8080
ipfs config --json Addresses.Swarm '["/ip4/0.0.0.0/tcp/4001","/ip4/0.0.0.0/udp/4001/quic-v1"]'
ipfs config Routing.Type autoclient
ipfs config --bool Discovery.MDNS.Enabled true

echo "[entrypoint] start ipfs daemon"
ipfs daemon --migrate=true --enable-gc=false &
DAEMON_PID=$$!

i=0
while [ "$i" -lt 30 ]; do
  if ipfs id >/dev/null 2>&1; then
    echo "[entrypoint] daemon ready"
    break
  fi
  i=$((i + 1))
  sleep 1
done

if ! ipfs id >/dev/null 2>&1; then
  echo "[entrypoint] daemon failed to start" >&2
  exit 1
fi

echo "[entrypoint] start agent"
exec python /app/ipfs_test_node_public.py
