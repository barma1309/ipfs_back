import os
import subprocess
import logging
from datetime import datetime
from watchdog.events import FileSystemEventHandler
from file_sync import sync_files_to_synced_dir, save_file_cid_mapping, load_deleted_files, save_deleted_files

# Версия модуля
MODULE_VERSION = "2.1.7"

class NewFileHandler(FileSystemEventHandler):
    def __init__(self, ipfs_path, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path, delete_after_sync=True):
        super().__init__()
        self.ipfs_path = ipfs_path
        self.node_name = node_name
        self.logger = logger
        self.logger.info(f"MODULE_VERSION: file_monitor версия {MODULE_VERSION}")
        self.file_cid_mapping = file_cid_mapping
        self.synced_dir = synced_dir
        self.deleted_files_path = deleted_files_path
        self.delete_after_sync = delete_after_sync

    def on_created(self, event):
        if not event.is_directory:
            self.logger.info(f"NEW_FILE: Обнаружен новый файл: {event.src_path}")
            self.add_to_ipfs(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            try:
                if self.synced_dir in event.src_path:
                    relative_path = os.path.relpath(event.src_path, self.synced_dir)
                    deleted_files = load_deleted_files(self.deleted_files_path, self.logger)
                    if relative_path not in deleted_files:
                        deleted_files.append(relative_path)
                        save_deleted_files(self.deleted_files_path, deleted_files, self.logger)
                        self.logger.info(
                            f"REMOVE_FILE_SYNCED: Файл {relative_path} удалён из Synced_dir в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            except ValueError as e:
                self.logger.debug(f"REMOVE_FILE_SKIPPED: Пропущен файл {event.src_path}, не в Synced_dir: {e}")

    def add_to_ipfs(self, file_path):
        self.logger.info(f"ADD_TO_IPFS_START: Начало добавления файла {file_path} в IPFS")
        try:
            upload_dir = os.path.join(os.path.dirname(__file__), 'Upload')
            if upload_dir not in file_path:
                self.logger.warning(f"ADD_TO_IPFS_SKIPPED: Файл {file_path} не в Upload, пропущен")
                return

            relative_path = os.path.relpath(file_path, upload_dir)
            self.logger.debug(f"ADD_TO_IPFS: Processing file {file_path}, relative path: {relative_path}")
            result = subprocess.run(
                [self.ipfs_path, 'add', '-r', file_path],
                capture_output=True, text=True, check=True
            )
            self.logger.debug(f"ADD_OUTPUT: Вывод команды ipfs add: {result.stdout}")

            for line in result.stdout.splitlines():
                if line.startswith('added'):
                    parts = line.split()
                    cid = parts[1]
                    path = parts[2] if len(parts) > 2 else relative_path
                    self.file_cid_mapping[path] = cid
                    self.logger.info(
                        f"ADD_FILE: Файл {path} добавлен с CID {cid} в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    subprocess.run(
                        [self.ipfs_path, 'pin', 'add', cid],
                        capture_output=True, text=True, check=True
                    )
                    self.logger.info(f"PIN_ADD: Файл {path} запинен с CID {cid}")

            mapping_file = os.path.join(os.path.dirname(__file__), 'data', 'file_cid_mapping.json')
            save_file_cid_mapping(mapping_file, self.file_cid_mapping, self.logger)
            sync_files_to_synced_dir(self.ipfs_path, self.synced_dir, self.logger, self.file_cid_mapping,
                                    self.deleted_files_path)

            if self.delete_after_sync:
                try:
                    os.remove(file_path)
                    self.logger.info(f"DELETE_AFTER_SYNC: Файл {file_path} удалён из Upload после синхронизации")
                except Exception as e:
                    self.logger.error(f"DELETE_AFTER_SYNC_ERROR: Ошибка при удалении файла {file_path}: {e}")

            self.logger.info("ADD_TO_IPFS_END: Завершение добавления файла в IPFS")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ADD_ERROR: Ошибка при добавлении файла {file_path}: {e.stderr}")
        except Exception as e:
            self.logger.error(f"ADD_ERROR: Общая ошибка при добавления файла {file_path}: {e}")

def check_new_files(ipfs_path, upload_dir, node_name, logger, file_cid_mapping, synced_dir, deleted_files_path):
    logger.info(f"MODULE_VERSION: file_monitor версия {MODULE_VERSION}")
    logger.info("CHECK_NEW_FILES_START: Начало проверки новых файлов")
    try:
        if not os.path.exists(upload_dir):
            logger.error(f"CHECK_NEW_FILES_ERROR: Папка {upload_dir} не существует")
            return
        for root, _, files in os.walk(upload_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, upload_dir)
                if relative_path not in file_cid_mapping:
                    logger.debug(f"CHECK_NEW_FILES: Found new file {file_path}")
                    handler = NewFileHandler(ipfs_path, node_name, logger, file_cid_mapping, synced_dir,
                                            deleted_files_path)
                    handler.add_to_ipfs(file_path)
        sync_files_to_synced_dir(ipfs_path, synced_dir, logger, file_cid_mapping, deleted_files_path)
        logger.info("CHECK_NEW_FILES_END: Завершение проверки новых файлов")
    except Exception as e:
        logger.error(f"CHECK_NEW_FILES_ERROR: Ошибка при проверке новых файлов: {e}")
