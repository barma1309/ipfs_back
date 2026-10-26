# ipfs_back 2.3.0

Python-агент + Kubo в одном контейнере: файлы из `Upload/` пинятся в публичную сеть IPFS и раскладываются в `Synced_dir/` на узлах.

## Что делает
- поднимает Kubo (`IPFS_PATH=/data/ipfs`)
- следит за `Upload/`
- пинит CID, сохраняет пути, CID и даты добавления в SQLite `data/ipfs.sqlite3`
- забирает файлы пиров в `Synced_dir/`


При первом запуске существующие `data/file_cid_mapping.json` и
`data/deleted_files.json` автоматически импортируются в SQLite одной транзакцией.
Поддерживаются оба формата mapping: строка CID и объект `{cid, date_added}`.
Исходные JSON остаются на диске, но после миграции больше не читаются и не обновляются.
Если JSON повреждён, запуск останавливается: исправьте файл и повторите запуск.
Список удалённых файлов также хранится в БД. Дополнительные зависимости не нужны:
используется стандартный модуль Python `sqlite3`.

Для переноса данных при остановленном агенте копируйте `data/ipfs.sqlite3`
вместе с файлами `ipfs.sqlite3-wal` и `ipfs.sqlite3-shm`, если они присутствуют.

Сборка из DOCKER/V2, перед build копировать все `src/*.py`, включая `storage.py`.

## Тесты

Из корня проекта, используя Python из окружения проекта:

```bash
python -m unittest discover -s tests -v
```

Тесты используют временные SQLite-БД и каталоги. Вызовы Kubo подменены:
запущенный IPFS и доступ к сети не требуются, рабочие данные не изменяются.


## Запуск (Podman / Docker)

```bash
cd DOCKER/V2
mkdir -p Upload Synced_dir data ipfs-repo
podman compose -f docker-compose.yml up -d --build
podman logs -f ipfs-back
