import subprocess
import logging
import asyncio

# Версия модуля
MODULE_VERSION = "2.1.8"

DHT_CHECK_TIMEOUT = 25


async def manage_mdns_connections(ipfs_path, node_name, logger):
    logger.info(f"MODULE_VERSION: network_manager версия {MODULE_VERSION}")
    try:
        while True:
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    [ipfs_path, 'swarm', 'peers'],
                    capture_output=True, text=True, check=True
                )
                peers = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                logger.info(f"MDNS_PEERS: Подключённые узлы: {len(peers)}")

                if peers:
                    peer_id = peers[0].split('/')[-1]
                    try:
                        dht_result = await asyncio.to_thread(
                            subprocess.run,
                            [ipfs_path, 'routing', 'findpeer', peer_id],
                            capture_output=True, text=True, check=True, timeout=DHT_CHECK_TIMEOUT
                        )
                        addrs = [line.strip() for line in dht_result.stdout.splitlines() if line.strip()]
                        logger.info(f"DHT_CHECK: DHT ответил для {peer_id}, адресов: {len(addrs)}")
                    except subprocess.TimeoutExpired:
                        logger.warning(f"DHT_CHECK_TIMEOUT: DHT не ответил за {DHT_CHECK_TIMEOUT} секунд для {peer_id}")
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"DHT_CHECK_ERROR: Ошибка при проверке DHT: {e.stderr}")

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

        from file_sync import sync_files_to_synced_dir
        sync_files_to_synced_dir(ipfs_path, synced_dir, logger, file_cid_mapping, deleted_files_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"LIST_PINNED_ERROR: Ошибка при получении списка пинов: {e.stderr}")