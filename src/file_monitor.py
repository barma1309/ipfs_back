# file_monitor.py
# Watch Upload/Synced_dir, add and pin files, and persist mappings.
# Version 2.3.1:
#   * call `ipfs provide once` after pinning (routing provide deprecated in Kubo 0.42)
#   * store CIDs, addition dates, and deleted paths in SQLite

import os
import subprocess
from datetime import datetime
from watchdog.events import FileSystemEventHandler

from file_sync import sync_files_to_synced_dir
from storage import mark_deleted_file

MODULE_VERSION = "2.3.1"


def _announce_cid(ipfs_path, cid, logger, path):
    """
    Announce the CID to the routing system.
    `ipfs routing provide` is deprecated; use `ipfs provide once` since Kubo 0.42.
    For older versions such as 0.35, fall back to routing provide and log failures.
    """
    try:
        subprocess.run(
            [ipfs_path, "provide", "once", cid],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"PROVIDE_ONCE: CID {cid} announced for {path}")
        return
    except subprocess.CalledProcessError as e:
        logger.debug(f"PROVIDE_ONCE: Command unavailable or failed: {e.stderr}")
    except FileNotFoundError:
        pass

    try:
        subprocess.run(
            [ipfs_path, "routing", "provide", cid],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"PROVIDE_FALLBACK: CID {cid} announced via routing provide for {path}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"PROVIDE_ERROR: Failed to announce CID {cid}: {e.stderr}")


class NewFileHandler(FileSystemEventHandler):
    def __init__(
        self,
        ipfs_path,
        node_name,
        logger,
        file_cid_mapping,
        synced_dir,
        database_path,
        delete_after_sync=True,
    ):
        super().__init__()
        self.ipfs_path = ipfs_path
        self.node_name = node_name
        self.logger = logger
        self.logger.info(f"MODULE_VERSION: file_monitor version {MODULE_VERSION}")
        self.file_cid_mapping = file_cid_mapping
        self.synced_dir = synced_dir
        self.database_path = database_path
        self.delete_after_sync = delete_after_sync

    def on_created(self, event):
        if not event.is_directory:
            self.logger.info(f"NEW_FILE: New file detected: {event.src_path}")
            self.add_to_ipfs(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            try:
                if self.synced_dir in event.src_path:
                    relative_path = os.path.relpath(event.src_path, self.synced_dir)
                    mark_deleted_file(self.database_path, relative_path)
                    self.logger.info(
                        f"REMOVE_FILE_SYNCED: File {relative_path} removed from Synced_dir "
                        f"at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
            except ValueError as e:
                self.logger.debug(
                    f"REMOVE_FILE_SKIPPED: Skipped file {event.src_path}: outside Synced_dir: {e}"
                )

    def add_to_ipfs(self, file_path):
        self.logger.info(f"ADD_TO_IPFS_START: Adding file {file_path} to IPFS")
        try:
            upload_dir = os.path.join(os.path.dirname(__file__), "../Upload")
            if upload_dir not in file_path:
                self.logger.warning(f"ADD_TO_IPFS_SKIPPED: Skipped file {file_path}: outside Upload")
                return

            relative_path = os.path.relpath(file_path, upload_dir)
            self.logger.debug(f"ADD_TO_IPFS: Processing file {file_path}, relative path: {relative_path}")
            result = subprocess.run(
                [self.ipfs_path, "add", "-r", file_path],
                capture_output=True,
                text=True,
                check=True,
            )
            self.logger.debug(f"ADD_OUTPUT: ipfs add output: {result.stdout}")

            for line in result.stdout.splitlines():
                if line.startswith("added"):
                    parts = line.split()
                    cid = parts[1]
                    path = parts[2] if len(parts) > 2 else relative_path
                    date_added = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.logger.info(f"ADD_FILE: File {path} added with CID {cid} at {date_added}")
                    subprocess.run(
                        [self.ipfs_path, "pin", "add", cid],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    self.logger.info(f"PIN_ADD: File {path} pinned with CID {cid}")
                    self.file_cid_mapping[path] = {"cid": cid, "date_added": date_added}
                    _announce_cid(self.ipfs_path, cid, self.logger, path)

            sync_files_to_synced_dir(
                self.ipfs_path,
                self.synced_dir,
                self.logger,
                self.file_cid_mapping,
                self.database_path,
            )

            if self.delete_after_sync:
                try:
                    os.remove(file_path)
                    self.logger.info(
                        f"DELETE_AFTER_SYNC: File {file_path} removed from Upload after synchronization"
                    )
                except Exception as e:
                    self.logger.error(f"DELETE_AFTER_SYNC_ERROR: Failed to remove file {file_path}: {e}")

            self.logger.info("ADD_TO_IPFS_END: Finished adding file to IPFS")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ADD_ERROR: Failed to add file {file_path}: {e.stderr}")
        except Exception as e:
            self.logger.error(f"ADD_ERROR: Unexpected error adding file {file_path}: {e}")


def check_new_files(ipfs_path, upload_dir, node_name, logger, file_cid_mapping, synced_dir, database_path):
    logger.info(f"MODULE_VERSION: file_monitor version {MODULE_VERSION}")
    logger.info("CHECK_NEW_FILES_START: Starting new file check")
    try:
        if not os.path.exists(upload_dir):
            logger.error(f"CHECK_NEW_FILES_ERROR: Directory {upload_dir} does not exist")
            return
        for root, _, files in os.walk(upload_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, upload_dir)
                if relative_path not in file_cid_mapping:
                    logger.debug(f"CHECK_NEW_FILES: Found new file {file_path}")
                    handler = NewFileHandler(
                        ipfs_path,
                        node_name,
                        logger,
                        file_cid_mapping,
                        synced_dir,
                        database_path,
                    )
                    handler.add_to_ipfs(file_path)
        sync_files_to_synced_dir(
            ipfs_path, synced_dir, logger, file_cid_mapping, database_path
        )
        logger.info("CHECK_NEW_FILES_END: Finished new file check")
    except Exception as e:
        logger.error(f"CHECK_NEW_FILES_ERROR: Failed to check for new files: {e}")
