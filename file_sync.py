import os
import subprocess
import json
import logging
from datetime import datetime

# Версия модуля
MODULE_VERSION = "2.1.7"

def backup_file_cid_mapping(mapping_file, logger):
    logger.info(f"MODULE_VERSION: file_sync версия {MODULE_VERSION}")
    logger.info("BACKUP_MAPPING_START: Начало создания резервной копии file_cid_mapping.json")
    try:
        if os.path.exists(mapping_file):
            backup_dir = os.path.join(os.path.dirname(mapping_file), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            backup_file = os.path.join(backup_dir, f'file_cid_mapping_{timestamp}.json')
            with open(mapping_file, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())
            logger.info(f"BACKUP_MAPPING: Создана резервная копия {backup_file}")
        else:
            logger.info("BACKUP_MAPPING: Файл file_cid_mapping.json не существует, пропуск резервного копирования")
        logger.info("BACKUP_MAPPING_END: Завершение создания резервной копии")
    except Exception as e:
        logger.error(f"BACKUP_MAPPING_ERROR: Ошибка при создании резервной копии {mapping_file}: {e}")

def load_deleted_files(deleted_files_path, logger):
    try:
        if os.path.exists(deleted_files_path):
            with open(deleted_files_path, 'r') as f:
                return json.load(f)
        logger.info(f"DELETED_FILES: Файл {deleted_files_path} не существует, возвращается пустой список")
        return []
    except Exception as e:
        logger.error(f"DELETED_FILES_ERROR: Ошибка при загрузке deleted_files.json: {e}")
        return []

def save_deleted_files(deleted_files_path, deleted_files, logger):
    logger.info(f"MODULE_VERSION: file_sync версия {MODULE_VERSION}")
    logger.info("SAVE_DELETED_FILES_START: Начало сохранения deleted_files.json")
    try:
        os.makedirs(os.path.dirname(deleted_files_path), exist_ok=True)
        with open(deleted_files_path, 'w') as f:
            json.dump(deleted_files, f, indent=2)
        logger.info(f"DELETED_FILES: Сохранён список удалённых файлов в {deleted_files_path}")
        logger.info("SAVE_DELETED_FILES_END: Завершение сохранения deleted_files.json")
    except Exception as e:
        logger.error(f"DELETED_FILES_ERROR: Ошибка при сохранении deleted_files.json: {e}")

def save_file_cid_mapping(mapping_file, file_cid_mapping, logger):
    logger.info(f"MODULE_VERSION: file_sync версия {MODULE_VERSION}")
    logger.info("SAVE_FILE_CID_MAPPING_START: Начало сохранения file_cid_mapping.json")
    try:
        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
        with open(mapping_file, 'w') as f:
            json.dump(file_cid_mapping, f, indent=2)
        logger.info(f"SAVE_FILE_CID_MAPPING: Сохранён file_cid_mapping.json в {mapping_file}")
        logger.info("SAVE_FILE_CID_MAPPING_END: Завершение сохранения file_cid_mapping.json")
    except Exception as e:
        logger.error(f"SAVE_FILE_CID_MAPPING_ERROR: Ошибка при сохранении file_cid_mapping.json: {e}")

def sync_files_to_synced_dir(ipfs_path, synced_dir, logger, file_cid_mapping, deleted_files_path):
    logger.info(f"MODULE_VERSION: file_sync версия {MODULE_VERSION}")
    logger.info("SYNC_FILES_START: Начало синхронизации файлов в Synced_dir")
    try:
        os.makedirs(synced_dir, exist_ok=True)
        deleted_files = load_deleted_files(deleted_files_path, logger)
        if not file_cid_mapping:
            logger.info("SYNC_FILES: file_cid_mapping.json пуст, синхронизация не требуется")
            logger.info("SYNC_FILES_END: Завершение синхронизации файлов в Synced_dir")
            return

        for path, cid in file_cid_mapping.items():
            relative_path = path.replace("Upload/", "", 1)
            dest_path = os.path.join(synced_dir, relative_path)
            if relative_path in deleted_files:
                logger.info(f"SYNC_FILE_SKIPPED: Файл {path} пропущен, так как он был удалён из Synced_dir")
                continue
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            if not os.path.exists(dest_path):
                try:
                    logger.debug(f"SYNC_FILE: Downloading {path} with CID {cid} to {dest_path}")
                    subprocess.run(
                        [ipfs_path, 'get', cid, '-o', dest_path],
                        capture_output=True, text=True, check=True
                    )
                    logger.info(f"SYNC_FILE: Файл {path} с CID {cid} загружен в {dest_path}")
                    subprocess.run(
                        [ipfs_path, 'pin', 'add', cid],
                        capture_output=True, text=True, check=True
                    )
                    logger.info(f"SYNC_PIN: Файл {path} запинен с CID {cid}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"SYNC_FILE_ERROR: Ошибка при загрузке файла {path} с CID {cid}: {e.stderr}")
        logger.info("SYNC_FILES_END: Завершение синхронизации файлов в Synced_dir")
    except Exception as e:
        logger.error(f"SYNC_FILES_ERROR: Ошибка при синхронизации файлов в Synced_dir: {e}")
