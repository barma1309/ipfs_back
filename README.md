# ipfs_back

Python-агент + Kubo в одном контейнере: файлы из `Upload/` пинятся в публичную сеть IPFS и раскладываются в `Synced_dir/` на узлах.

## Что делает
- поднимает Kubo (`IPFS_PATH=/data/ipfs`)
- следит за `Upload/`
- пинит CID, пишет mapping в `data/`
- забирает файлы пиров в `Synced_dir/`

## Запуск (Podman / Docker)

```bash
cd DOCKER/V2
mkdir -p Upload Synced_dir data ipfs-repo
podman compose -f docker-compose.yml up -d --build
podman logs -f ipfs-back
