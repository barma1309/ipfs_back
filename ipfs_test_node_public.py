import os
import subprocess
import json
import logging
import time
import threading
import asyncio
from watchdog.observers import Observer
from ipfs_config import ensure_ipfs_initialized, setup_public_network
from file_monitor import NewFileHandler, check_new_files
from network_manager import manage_mdns_connections, list_pinned_files

# Версия скрипта
SCRIPT_VERSION = "2.1.5"

# Настройка логирования
def setup_logging(node_name):
    log_dir = os.path.join(os.path.dirname(__file__), 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'log_{node_name}.log')
    # Очистка файла лога при запуске
    if os.path.exists(log_file):
        with open(log_file, 'w'):
            pass
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(node_name)
    logger.info(f"MODULE_VERSION: ipfs_test_node_public версия {SCRIPT_VERSION}")
    return logger

# Основная функция
def main():
    node_name = 'local'  # Измените на 'node2' или 'node3' для других нод
    ipfs_path = r"C:\Program Files\IPFS Desktop\resources\app.asar.unpacked\node_modules\kubo\kubo\ipfs.exe"
    upload_dir = os.path.join(os.path.dirname(__file__), 'Upload')
    synced_dir = os.path.join(os.path.dirname(__file__), 'Synced_dir')
    mapping_file = os.path.join(os.path.dirname(__file__), 'data', 'file_cid_mapping.json')
    deleted_files_path = os.path.join(os.path.dirname(__file__), 'data', 'deleted_files.json')

    # Создание директорий
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(synced_dir, exist_ok=True)
    os.makedirs(os.path.dirname(mapping_file), exist_ok=True)

    # Загрузка или создание file_cid_mapping
    file_cid_mapping = {}
    if os.path.exists(mapping_file):
        with open(mapping_file, 'r') as f:
            file_cid_mapping = json.load(f)

    logger = setup_logging(node_name)
    
    # Логирование старта скрипта
    logger.info(f"START: Запуск скрипта версии {SCRIPT_VERSION} (публичная сеть) с узлом {node_name}")
    print(f"Запуск скрипта версии {SCRIPT_VERSION} (публичная сеть) с узлом {node_name}")

    # Проверка и инициализация IPFS
    ensure_ipfs_initialized(ipfs_path, logger)

    # Настройка публичной сети
    setup_public_network(ipfs_path, logger, node_name)

    # Получение PeerID
    try:
        result = subprocess.run(
            [ipfs_path, 'id', '--format=<id>'],
            capture_output=True, text=True, check=True
        )
        peer_id = result.stdout.strip()
        logger.info(f"PEER_ID: PeerID узла {node_name}: {peer_id}")
        print(f"PeerID узла {node_name}: {peer_id}")
    except subprocess.CalledProcessError as e:
        logger.error(f"PEER_ID_ERROR: Ошибка при получении PeerID: {e.stderr}")
        return

    # Проверка новых файлов и синхронизация
    check_new_files(ipfs_path, upload_dir, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path)

    # Настройка наблюдателя за файловой системой
    event_handler = NewFileHandler(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path)
    observer = Observer()
    observer.schedule(event_handler, upload_dir, recursive=True)
    observer.schedule(event_handler, synced_dir, recursive=True)
    observer.start()

    # Запуск асинхронной функции для mDNS
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    threading.Thread(target=lambda: loop.run_until_complete(manage_mdns_connections(ipfs_path, node_name, logger)), daemon=True).start()

    try:
        while True:
            list_pinned_files(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path)
            time.sleep(60)  # Проверка каждую минуту
    except KeyboardInterrupt:
        logger.info("STOP: Скрипт остановлен")
        print("Скрипт остановлен")
        observer.stop()
    observer.join()

if __name__ == '__main__':
    main()
