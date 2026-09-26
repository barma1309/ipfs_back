# ipfs_back 2.2.2 — Python-агент + Kubo CLI в одном образе
FROM python:3.12-slim-bookworm

ARG KUBO_VERSION=v0.38.2
ARG TARGETARCH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl wget \
    && rm -rf /var/lib/apt/lists/*

# Официальный tarball Kubo: amd64 / arm64
RUN set -eux; \
    arch="${TARGETARCH:-amd64}"; \
    case "$arch" in \
      amd64|x86_64) kubo_arch=amd64 ;; \
      arm64|aarch64) kubo_arch=arm64 ;; \
      *) kubo_arch=amd64 ;; \
    esac; \
    wget -q "https://dist.ipfs.tech/kubo/${KUBO_VERSION}/kubo_${KUBO_VERSION}_linux-${kubo_arch}.tar.gz" -O /tmp/kubo.tgz; \
    tar -xzf /tmp/kubo.tgz -C /tmp; \
    mv /tmp/kubo/ipfs /usr/local/bin/ipfs; \
    chmod +x /usr/local/bin/ipfs; \
    rm -rf /tmp/kubo /tmp/kubo.tgz; \
    ipfs version

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ipfs_test_node_public.py ipfs_config.py file_monitor.py file_sync.py network_manager.py ./
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/Upload /app/Synced_dir /app/data /data/ipfs

ENV IPFS_PATH=/data/ipfs \
    PYTHONUNBUFFERED=1

EXPOSE 4001 4001/udp 8080

VOLUME ["/app/Upload", "/app/Synced_dir", "/app/data", "/data/ipfs"]

ENTRYPOINT ["/entrypoint.sh"]
