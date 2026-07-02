import os
import subprocess
import json
import logging
from datetime import datetime

# Версия модуля
MODULE_VERSION = "2.1.8"


def backup_file_cid_mapping(mapping_file, logger):
    logger.info(f"MODULE_VERSION: file_sync версия {MODULE_VERSION}")
    logger.info("BACKUP_MAPPING_START: Начало создания резервной копии file_cid_mapping.json")
    try:
        if os.path.exists(mapping_file):
            backup_dir = os.path.join(os.path.dirname(mapping_file), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            backup_file = os.path.join(backup_dir, f'file_cid_mapping_{timestamp}.json')
            with open(mapping_file, 'r', encoding='utf-8') as src, open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            logger.info(f"BACKUP_MAPPING: Создана резервная копия {backup_file}")
        else:
            logger.info("BACKUP_MAPPING: Файл file_cid_mapping.json не существует, пропуск резервного копирования")
        logger.info("BACKUP_MAPPING_END: Завершение создания резервной копии")
    except Exception as e:
        logger.error(f"BACKUP_MAPPING_ERROR: Ошибка при создании резервной копии {mapping_file}: {e}")


def _normalize_path(path):
    return path.replace('\\', '/')


def find_cid_for_relative_path(file_cid_mapping, relative_path):
    normalized_relative = _normalize_path(relative_path)
    for mapping_path, cid in file_cid_mapping.items():
        candidates = {
            _normalize_path(mapping_path),
            _normalize_path(mapping_path.replace("Upload/", "", 1)),
            _normalize_path(mapping_path.replace("Upload\\", "", 1)),
        }
        if normalized_relative in candidates:
            return cid
    return None


def normalize_deleted_files(data, file_cid_mapping=None):
    if not isinstance(data, list):
        return []

    normalized = []
    seen_paths = set()
    for item in data:
        if isinstance(item, str):
            entry = {
                "path": item,
                "cid": find_cid_for_relative_path(file_cid_mapping or {}, item),
                "deleted_at": None,
            }
        elif isinstance(item, dict) and "path" in item:
            entry = {
                "path": item["path"],
                "cid": item.get("cid") or find_cid_for_relative_path(file_cid_mapping or {}, item["path"]),
                "deleted_at": item.get("deleted_at"),
            }
        else:
            continue

        path_key = _normalize_path(entry["path"])
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)
        normalized.append(entry)
    return normalized


def is_file_deleted(deleted_files, relative_path):
    normalized_relative = _normalize_path(relative_path)
    return any(_normalize_path(item.get("path", "")) == normalized_relative for item in deleted_files)


def add_deleted_file(deleted_files, relative_path, cid, deleted_at, logger):
    if is_file_deleted(deleted_files, relative_path):
        return False

    deleted_files.append({
        "path": relative_path,
        "cid": cid,
        "deleted_at": deleted_at,
    })
    logger.info(
        f"DELETED_FILES_ADD: Файл {relative_path} добавлен в deleted_files.json "
        f"(CID: {cid or 'неизвестно'}, удалён: {deleted_at})"
    )
    return True


def load_deleted_files(deleted_files_path, logger, file_cid_mapping=None):
    try:
        if os.path.exists(deleted_files_path):
            with open(deleted_files_path, encoding='utf-8') as f:
                data = json.load(f)
            return normalize_deleted_files(data, file_cid_mapping)
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
        with open(deleted_files_path, 'w', encoding='utf-8') as f:
            json.dump(deleted_files, f, indent=2, ensure_ascii=False)
        logger.info(f"DELETED_FILES: Сохранён список удалённых файлов в {deleted_files_path}")
        logger.info("SAVE_DELETED_FILES_END: Завершение сохранения deleted_files.json")
    except Exception as e:
        logger.error(f"DELETED_FILES_ERROR: Ошибка при сохранении deleted_files.json: {e}")


def save_file_cid_mapping(mapping_file, file_cid_mapping, logger):
    logger.info(f"MODULE_VERSION: file_sync версия {MODULE_VERSION}")
    logger.info("SAVE_FILE_CID_MAPPING_START: Начало сохранения file_cid_mapping.json")
    try:
        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(file_cid_mapping, f, indent=2, ensure_ascii=False)
        logger.info(f"SAVE_FILE_CID_MAPPING: Сохранён file_cid_mapping.json в {mapping_file}")
        logger.info("SAVE_FILE_CID_MAPPING_END: Завершение сохранения file_cid_mapping.json")
    except Exception as e:
        logger.error(f"SAVE_FILE_CID_MAPPING_ERROR: Ошибка при сохранении file_cid_mapping.json: {e}")


def sync_files_to_synced_dir(ipfs_path, synced_dir, logger, file_cid_mapping, deleted_files_path):
    logger.info(f"MODULE_VERSION: file_sync версия {MODULE_VERSION}")
    logger.info("SYNC_FILES_START: Начало синхронизации файлов в Synced_dir")
    try:
        os.makedirs(synced_dir, exist_ok=True)
        deleted_files = load_deleted_files(deleted_files_path, logger, file_cid_mapping)
        if not file_cid_mapping:
            logger.info("SYNC_FILES: file_cid_mapping.json пуст, синхронизация не требуется")
            logger.info("SYNC_FILES_END: Завершение синхронизации файлов в Synced_dir")
            return

        for path, cid in file_cid_mapping.items():
            relative_path = path.replace("Upload/", "", 1).replace("Upload\\", "", 1)
            dest_path = os.path.join(synced_dir, relative_path)
            if is_file_deleted(deleted_files, relative_path):
                logger.info(f"SYNC_FILE_SKIPPED: Файл {path} пропущен, так как он был удалён из Synced_dir")
                continue
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

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