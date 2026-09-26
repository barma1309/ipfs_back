# network_manager.py
# Пиры, routing-проверка и список пинов.
# Версия 2.2.1:
#   * ipfs dht * заменён на ipfs routing findprovs (dht API снят с 0.27)
#   * не ищем собственный PeerID через findpeer
#   * list_pinned_files читает новый формат mapping {cid, date_added}

import subprocess
import asyncio

MODULE_VERSION = "2.2.2"


def _first_cid(file_cid_mapping):
    """Достаёт первый CID из mapping старого или нового формата."""
    if not file_cid_mapping:
        return None
    for entry in file_cid_mapping.values():
        if isinstance(entry, dict):
            return entry.get("cid")
        if isinstance(entry, str):
            return entry
    return None


async def manage_mdns_connections(ipfs_path, node_name, logger, file_cid_mapping=None):
    logger.info(f"MODULE_VERSION: network_manager версия {MODULE_VERSION}")
    logger.info("MDNS_CONNECTIONS_START: Начало управления mDNS соединениями")

    try:
        result = subprocess.run(
            [ipfs_path, "id", "--format=<id>"],
            capture_output=True,
            text=True,
            check=True,
        )
        own_peer_id = result.stdout.strip()
        logger.info(f"MDNS_PEER_ID: PeerID узла {node_name}: {own_peer_id}")
    except subprocess.CalledProcessError as e:
        logger.error(f"MDNS_PEER_ID_ERROR: Ошибка при получении PeerID: {e.stderr}")
        own_peer_id = None

    while True:
        try:
            result = subprocess.run(
                [ipfs_path, "swarm", "peers"],
                capture_output=True,
                text=True,
                check=True,
            )
            peers = [p for p in result.stdout.splitlines() if p.strip()]
            logger.info(f"MDNS_PEERS: Подключённые узлы: {len(peers)}")
            for peer in peers:
                logger.debug(f"MDNS_PEERS: Активное соединение: {peer}")
                try:
                    subprocess.run(
                        [ipfs_path, "swarm", "connect", peer],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    logger.debug(f"MDNS_CONNECT: Успешно подключено к {peer}")
                except (subprocess.CalledProcessError, IndexError) as e:
                    logger.warning(f"MDNS_CONNECT_ERROR: Не удалось подключиться к {peer}: {str(e)}")

            # Проверяем провайдеров CID, а не «себя в DHT».
            # ipfs routing findpeer <own_peer_id> возвращает:
            # "finding your own node in the DHT is currently not supported"
            cid = _first_cid(file_cid_mapping)
            if cid:
                try:
                    logger.debug(f"ROUTING_CHECK: Executing ipfs routing findprovs {cid}")
                    result = subprocess.run(
                        [ipfs_path, "routing", "findprovs", cid],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    providers = result.stdout.strip() or "(пусто)"
                    logger.info(f"ROUTING_CHECK: Найдены провайдеры для CID {cid}: {providers}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"ROUTING_CHECK_ERROR: Ошибка при проверке routing: {e.stderr}")
                except Exception as e:
                    logger.warning(f"ROUTING_CHECK_ERROR: Общая ошибка при проверке routing: {str(e)}")
            else:
                logger.info("ROUTING_CHECK: Нет CID в mapping — пропускаем findprovs")

            logger.info("MDNS_CONNECTIONS: Ожидание 60 секунд")
            await asyncio.sleep(60)
        except subprocess.CalledProcessError as e:
            logger.error(f"MDNS_ERROR: Ошибка при управлении mDNS: {e.stderr}")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"MDNS_ERROR: Общая ошибка при управлении mDNS: {str(e)}")
            await asyncio.sleep(60)


def list_pinned_files(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path):
    logger.info(f"MODULE_VERSION: network_manager версия {MODULE_VERSION}")
    logger.info("LIST_PINNED_START: Начало вывода списка запиненных файлов")
    try:
        result = subprocess.run(
            [ipfs_path, "pin", "ls", "--type=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        pinned_cids = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                cid, pin_type = parts[0], parts[1]
                pinned_cids[cid] = pin_type

        logger.info(f"LIST_PINNED: Список запинненных файлов и каталогов на ноде {node_name}:")
        if not file_cid_mapping:
            logger.info("LIST_PINNED: file_cid_mapping.json пуст, нет файлов для отображения")
        for path, entry in file_cid_mapping.items():
            if isinstance(entry, dict):
                cid = entry.get("cid", "")
                date_added = entry.get("date_added", "unknown")
            else:
                cid = entry
                date_added = "unknown"
            pin_type = pinned_cids.get(cid, "неизвестно")
            logger.info(
                f"LIST_PINNED: CID: {cid}, Тип: {pin_type}, Путь: {path}, Дата добавления: {date_added}"
            )

        from file_sync import sync_files_to_synced_dir

        sync_files_to_synced_dir(
            ipfs_path, synced_dir, logger, file_cid_mapping, deleted_files_path
        )
        logger.info("LIST_PINNED_END: Завершение вывода списка запиненных файлов")
    except subprocess.CalledProcessError as e:
        logger.error(f"LIST_PINNED_ERROR: Ошибка при получении списка пинов: {e.stderr}")
    except Exception as e:
        logger.error(f"LIST_PINNED_ERROR: Общая ошибка при получении списка пинов: {e}")
