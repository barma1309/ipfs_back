# ipfs_test_node_public.py
# Главный модуль агента синхронизации файлов через локальный Kubo CLI.
# Версия 2.3.0 — SQLite и совместимость с Kubo 0.27–0.43:
#   * автоматическая миграция JSON в SQLite при первом запуске
#   * routing через `ipfs routing findprovs`, не `ipfs dht *`
#   * не вызываем findpeer для собственного PeerID
#   * Discovery.MDNS.Interval больше не настраивается (ключ удалён в Kubo)
#   * Routing.Type=autoclient вместо устаревшего по смыслу dhtclient-дефолта
#   * после pin — `ipfs provide once` (routing provide deprecated с 0.42)

import os
import subprocess
import logging
import asyncio
from watchdog.observers import Observer

from ipfs_config import (
    ensure_ipfs_initialized,
    setup_public_network,
    resolve_ipfs_path,
    MODULE_VERSION as IPFS_CONFIG_VERSION,
)
from file_monitor import (
    NewFileHandler,
    check_new_files,
    MODULE_VERSION as FILE_MONITOR_VERSION,
)
from network_manager import (
    manage_mdns_connections,
    list_pinned_files,
    MODULE_VERSION as NETWORK_MANAGER_VERSION,
)
from file_sync import MODULE_VERSION as FILE_SYNC_VERSION
from storage import FileCIDMapping, MODULE_VERSION as STORAGE_VERSION

# Единая версия пакета. Все модули должны совпадать.
SCRIPT_VERSION = "2.3.0"


def setup_logging(node_name):
    """Файловый + консольный логгер. Старый лог обнуляется при старте."""
    log_dir = os.path.join(os.path.dirname(__file__), "../data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"log_{node_name}.log")
    if os.path.exists(log_file):
        with open(log_file, "w"):
            pass

    logger = logging.getLogger(node_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"MODULE_VERSION: ipfs_test_node_public версия {SCRIPT_VERSION}")
    expected_version = SCRIPT_VERSION
    for module, version in (
        ("ipfs_config", IPFS_CONFIG_VERSION),
        ("file_monitor", FILE_MONITOR_VERSION),
        ("network_manager", NETWORK_MANAGER_VERSION),
        ("file_sync", FILE_SYNC_VERSION),
        ("storage", STORAGE_VERSION),
    ):
        if version != expected_version:
            logger.warning(
                f"VERSION_MISMATCH: Модуль {module} имеет версию {version}, "
                f"ожидается {expected_version}"
            )
    return logger


def initialize_file_cid_mapping(database_path, logger):
    try:
        return FileCIDMapping(database_path)
    except Exception:
        logger.exception("MAIN_ERROR: Не удалось инициализировать SQLite или перенести JSON")
        return None


async def main():
    node_name = "local"
    upload_dir = os.path.join(os.path.dirname(__file__), "../Upload")
    synced_dir = os.path.join(os.path.dirname(__file__), "../Synced_dir")
    database_path = os.path.join(os.path.dirname(__file__), "../data", "ipfs.sqlite3")

    logger = setup_logging(node_name)
    logger.info(
        f"START: Запуск скрипта версии {SCRIPT_VERSION} (публичная сеть) с узлом {node_name}"
    )

    logger.info("MAIN: Проверка директорий")
    try:
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(synced_dir, exist_ok=True)
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        logger.info(
            f"MAIN: Директории созданы: {upload_dir}, {synced_dir}, {os.path.dirname(database_path)}"
        )
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка при создании директорий: {e}")
        return

    logger.info("MAIN: Загрузка SQLite")
    file_cid_mapping = initialize_file_cid_mapping(database_path, logger)
    if file_cid_mapping is None:
        logger.error("MAIN_ERROR: Не удалось инициализировать SQLite, завершение работы")
        return

    logger.info("MAIN: Поиск Kubo CLI (ipfs.exe)")
    try:
        ipfs_path = resolve_ipfs_path(logger)
    except FileNotFoundError as e:
        logger.error(f"MAIN_ERROR: {e}")
        return

    logger.info("MAIN: Проверка статуса демона IPFS")
    try:
        subprocess.run(
            [ipfs_path, "id"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        logger.info("MAIN: Демон IPFS активен")
    except subprocess.CalledProcessError as e:
        logger.error(f"MAIN_ERROR: Ошибка при проверке демона IPFS: {e.stderr}")
        logger.info("MAIN: Попытка запуска демона IPFS")
        try:
            subprocess.Popen(
                [ipfs_path, "daemon"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await asyncio.sleep(10)
        except Exception as start_err:
            logger.error(f"MAIN_ERROR: Не удалось запустить демон IPFS: {start_err}")
            return
    except Exception as e:
        logger.error(f"MAIN_ERROR: Неизвестная ошибка при проверке демона IPFS: {e}")
        return

    logger.info("MAIN: Инициализация IPFS")
    try:
        ensure_ipfs_initialized(ipfs_path, logger)
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка инициализации IPFS: {e}")
        return

    logger.info("MAIN: Настройка публичной сети")
    try:
        setup_public_network(ipfs_path, logger, node_name)
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка настройки публичной сети: {e}")
        return

    logger.info("MAIN: Получение PeerID")
    try:
        result = subprocess.run(
            [ipfs_path, "id", "--format=<id>"],
            capture_output=True,
            text=True,
            check=True,
        )
        peer_id = result.stdout.strip()
        logger.info(f"PEER_ID: PeerID узла {node_name}: {peer_id}")
    except subprocess.CalledProcessError as e:
        logger.error(f"PEER_ID_ERROR: Ошибка при получении PeerID: {e.stderr}")
        return

    logger.info("MAIN: Проверка новых файлов")
    try:
        check_new_files(
            ipfs_path,
            upload_dir,
            node_name,
            logger,
            file_cid_mapping,
            synced_dir,
            database_path,
        )
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка при проверке новых файлов: {e}")
        return

    logger.info("MAIN: Настройка наблюдателя за файловой системой")
    observer = None
    try:
        event_handler = NewFileHandler(
            ipfs_path,
            node_name,
            logger,
            file_cid_mapping,
            synced_dir,
            database_path,
            delete_after_sync=True,
        )
        observer = Observer()
        observer.schedule(event_handler, upload_dir, recursive=True)
        observer.schedule(event_handler, synced_dir, recursive=True)
        observer.start()
        logger.info("MAIN: Наблюдатель запущен")
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка при настройке наблюдателя: {e}")
        if observer is not None:
            observer.stop()
        return

    logger.info("MAIN: Запуск цикла проверки пинов и mDNS")
    try:
        tasks = [
            asyncio.create_task(
                manage_mdns_connections(ipfs_path, node_name, logger, file_cid_mapping)
            ),
            asyncio.create_task(
                run_pin_check_loop(
                    ipfs_path,
                    node_name,
                    logger,
                    file_cid_mapping,
                    synced_dir,
                    database_path,
                )
            ),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        logger.info("STOP: Скрипт остановлен")
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка в основном цикле: {e}")
    finally:
        if observer is not None:
            observer.stop()
            observer.join()


async def run_pin_check_loop(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, database_path):
    while True:
        logger.info("PIN_CHECK_LOOP: Начало цикла проверки пиннов")
        try:
            list_pinned_files(
                ipfs_path,
                node_name,
                logger,
                file_cid_mapping,
                synced_dir,
                database_path,
            )
        except Exception as e:
            logger.error(f"PIN_CHECK_LOOP_ERROR: Ошибка в цикле проверки пиннов: {e}")
        logger.info("PIN_CHECK_LOOP: Ожидание 60 секунд")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
