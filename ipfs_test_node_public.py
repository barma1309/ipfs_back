import os
import subprocess
import json
import logging
import asyncio
from watchdog.observers import Observer
from ipfs_config import ensure_ipfs_initialized, setup_public_network, MODULE_VERSION as IPFS_CONFIG_VERSION
from file_monitor import NewFileHandler, check_new_files, MODULE_VERSION as FILE_MONITOR_VERSION
from network_manager import manage_mdns_connections, list_pinned_files, MODULE_VERSION as NETWORK_MANAGER_VERSION
from file_sync import MODULE_VERSION as FILE_SYNC_VERSION

# Версия скрипта
SCRIPT_VERSION = "2.1.7"

# Настройка логирования
def setup_logging(node_name):
    log_dir = os.path.join(os.path.dirname(__file__), 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'log_{node_name}.log')
    if os.path.exists(log_file):
        with open(log_file, 'w'):
            pass
    logger = logging.getLogger(node_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info(f"MODULE_VERSION: ipfs_test_node_public версия {SCRIPT_VERSION}")
    # Check module versions
    expected_version = SCRIPT_VERSION
    for module, version in [
        ("ipfs_config", IPFS_CONFIG_VERSION),
        ("file_monitor", FILE_MONITOR_VERSION),
        ("network_manager", NETWORK_MANAGER_VERSION),
        ("file_sync", FILE_SYNC_VERSION)
    ]:
        if version != expected_version:
            logger.warning(f"VERSION_MISMATCH: Модуль {module} имеет версию {version}, ожидается {expected_version}")
    return logger

def initialize_file_cid_mapping(mapping_file, logger):
    try:
        if not os.path.exists(mapping_file):
            logger.info(f"MAIN: file_cid_mapping.json not found, creating new file at {mapping_file}")
            with open(mapping_file, 'w') as f:
                json.dump({}, f, indent=4)
            return {}
        logger.info(f"MAIN: Loading file_cid_mapping.json from {mapping_file}")
        with open(mapping_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"MAIN_ERROR: Failed to initialize file_cid_mapping.json: {str(e)}")
        return None

async def main():
    node_name = 'local'
    ipfs_path = r"C:\Program Files\IPFS Desktop\resources\app.asar.unpacked\node_modules\kubo\kubo\ipfs.exe"
    upload_dir = os.path.join(os.path.dirname(__file__), 'Upload')
    synced_dir = os.path.join(os.path.dirname(__file__), 'Synced_dir')
    mapping_file = os.path.join(os.path.dirname(__file__), 'data', 'file_cid_mapping.json')
    deleted_files_path = os.path.join(os.path.dirname(__file__), 'data', 'deleted_files.json')

    logger = setup_logging(node_name)
    logger.info(f"START: Запуск скрипта версии {SCRIPT_VERSION} (публичная сеть) с узлом {node_name}")

    logger.info("MAIN: Проверка директорий")
    try:
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(synced_dir, exist_ok=True)
        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
        logger.info(f"MAIN: Директории созданы: {upload_dir}, {synced_dir}, {os.path.dirname(mapping_file)}")
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка при создании директорий: {e}")
        return

    logger.info("MAIN: Загрузка file_cid_mapping.json")
    file_cid_mapping = initialize_file_cid_mapping(mapping_file, logger)
    if file_cid_mapping is None:
        logger.error("MAIN_ERROR: Не удалось инициализировать file_cid_mapping.json, завершение работы")
        return

    logger.info("MAIN: Проверка статуса демона IPFS")
    try:
        result = subprocess.run(
            [ipfs_path, 'id'],
            capture_output=True, text=True, check=True, timeout=30
        )
        logger.info("MAIN: Демон IPFS активен")
    except subprocess.CalledProcessError as e:
        logger.error(f"MAIN_ERROR: Ошибка при проверке демона IPFS: {e.stderr}")
        logger.info("MAIN: Попытка запуска демона IPFS")
        try:
            subprocess.Popen(
                [ipfs_path, 'daemon'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"MAIN_ERROR: Не удалось запустить демон IPFS: {e}")
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
            [ipfs_path, 'id', '--format=<id>'],
            capture_output=True, text=True, check=True
        )
        peer_id = result.stdout.strip()
        logger.info(f"PEER_ID: PeerID узла local: {peer_id}")
    except subprocess.CalledProcessError as e:
        logger.error(f"PEER_ID_ERROR: Ошибка при получении PeerID: {e.stderr}")
        return

    logger.info("MAIN: Проверка новых файлов")
    try:
        check_new_files(ipfs_path, upload_dir, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path)
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка при проверке новых файлов: {e}")
        return

    logger.info("MAIN: Настройка наблюдателя за файловой системой")
    try:
        event_handler = NewFileHandler(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path, delete_after_sync=True)
        observer = Observer()
        observer.schedule(event_handler, upload_dir, recursive=True)
        observer.schedule(event_handler, synced_dir, recursive=True)
        observer.start()
        logger.info("MAIN: Наблюдатель запущен")
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка при настройке наблюдателя: {e}")
        observer.stop()
        return

    logger.info("MAIN: Запуск цикла проверки пинов и mDNS")
    try:
        tasks = [
            asyncio.create_task(manage_mdns_connections(ipfs_path, node_name, logger)),
            asyncio.create_task(run_pin_check_loop(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path))
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        logger.info("STOP: Скрипт остановлен")
    except Exception as e:
        logger.error(f"MAIN_ERROR: Ошибка в основном цикле: {e}")
    finally:
        observer.stop()
        observer.join()

async def run_pin_check_loop(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path):
    while True:
        logger.info("PIN_CHECK_LOOP: Начало цикла проверки пиннов")
        try:
            list_pinned_files(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path)
        except Exception as e:
            logger.error(f"PIN_CHECK_LOOP_ERROR: Ошибка в цикле проверки пиннов: {e}")
        logger.info("PIN_CHECK_LOOP: Ожидание 60 секунд")
        await asyncio.sleep(60)

if __name__ == '__main__':
    asyncio.run(main())
