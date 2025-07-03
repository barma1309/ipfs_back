import subprocess
import logging
import asyncio

# Версия модуля
MODULE_VERSION = "2.1.5"

async def manage_mdns_connections(ipfs_path, node_name, logger):
    logger.info(f"MODULE_VERSION: network_manager версия {MODULE_VERSION}")
    try:
        # Периодическая проверка подключённых узлов
        while True:
            try:
                # Получение списка подключённых узлов
                result = subprocess.run(
                    [ipfs_path, 'swarm', 'peers'],
                    capture_output=True, text=True, check=True
                )
                peers = result.stdout.splitlines()
                logger.info(f"MDNS_PEERS: Подключённые узлы: {len(peers)}")
                for peer in peers:
                    logger.info(f"MDNS_PEERS: Активное соединение: {peer}")

                # Попытка обнаружения новых узлов через mDNS и DHT
                for peer in peers:
                    peer_id = peer.split('/')[-1]
                    logger.info(f"MDNS_DISCOVERY: Обнаружен узел: {peer}")
                    try:
                        subprocess.run(
                            [ipfs_path, 'swarm', 'connect', peer],
                            capture_output=True, text=True, check=True
                        )
                        logger.info(f"MDNS_CONNECT: Успешно подключено к {peer}")
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"MDNS_CONNECT_ERROR: Не удалось подключиться к {peer}: {e.stderr}")

                # Проверка DHT (публичная сеть)
                try:
                    if peers:  # Проверяем, есть ли пиры
                        result = subprocess.run(
                            [ipfs_path, 'dht', 'findpeers', peers[0].split('/')[-1]],
                            capture_output=True, text=True, check=True
                        )
                        logger.info(f"DHT_CHECK: Найдены пиры в публичной сети: {result.stdout}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"DHT_CHECK_ERROR: Ошибка при проверке DHT: {e.stderr}")

                # Ожидание 30 секунд перед следующей проверкой
                await asyncio.sleep(30)
            except subprocess.CalledProcessError as e:
                logger.error(f"MDNS_ERROR: Ошибка при управлении mDNS: {e.stderr}")
    except Exception as e:
        logger.error(f"MDNS_ERROR: Общая ошибка при управлении mDNS: {e}")

def list_pinned_files(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path):
    logger.info(f"MODULE_VERSION: network_manager версия {MODULE_VERSION}")
    try:
        result = subprocess.run(
            [ipfs_path, 'pin', 'ls', '--type=all'],
            capture_output=True, text=True, check=True
        )
        pinned_cids = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                cid, pin_type = parts[0], parts[1]
                pinned_cids[cid] = pin_type
        
        logger.info(f"LIST_PINNED: Список запинненных файлов и каталогов на ноде {node_name}:")
        for path, cid in file_cid_mapping.items():
            pin_type = pinned_cids.get(cid, 'неизвестно')
            logger.info(f"LIST_PINNED: CID: {cid}, Тип: {pin_type}, Путь: {path}")
        
        # Синхронизация файлов в Synced_dir
        from file_sync import sync_files_to_synced_dir
        sync_files_to_synced_dir(ipfs_path, synced_dir, logger, file_cid_mapping, deleted_files_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"LIST_PINNED_ERROR: Ошибка при получении списка пинов: {e.stderr}")
