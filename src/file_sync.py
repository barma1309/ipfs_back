# file_sync.py
# Synchronize files by CID and read deleted paths from SQLite.
# Version 2.3.1: store file mappings and deleted paths in SQLite.

import os
import subprocess
from storage import load_deleted_files

MODULE_VERSION = "2.3.1"


def _entry_cid(entry):
    if isinstance(entry, dict):
        return entry.get("cid")
    return entry


def sync_files_to_synced_dir(ipfs_path, synced_dir, logger, file_cid_mapping, database_path):
    logger.info(f"MODULE_VERSION: file_sync version {MODULE_VERSION}")
    logger.info("SYNC_FILES_START: Starting file synchronization to Synced_dir")
    try:
        os.makedirs(synced_dir, exist_ok=True)
        deleted_files = load_deleted_files(database_path, logger)
        if not file_cid_mapping:
            logger.info("SYNC_FILES: SQLite file list is empty; no synchronization needed")
            logger.info("SYNC_FILES_END: Finished file synchronization to Synced_dir")
            return

        for path, entry in file_cid_mapping.items():
            cid = _entry_cid(entry)
            if not cid:
                logger.warning(f"SYNC_FILE_SKIPPED: No CID for {path}")
                continue
            relative_path = path.replace("Upload/", "", 1)
            dest_path = os.path.join(synced_dir, relative_path)
            if relative_path in deleted_files:
                logger.info(f"SYNC_FILE_SKIPPED: Skipped file {path}: previously removed from Synced_dir")
                continue
            os.makedirs(os.path.dirname(dest_path) or synced_dir, exist_ok=True)

            if not os.path.exists(dest_path):
                try:
                    logger.debug(f"SYNC_FILE: Downloading {path} with CID {cid} to {dest_path}")
                    subprocess.run(
                        [ipfs_path, "get", cid, "-o", dest_path],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    logger.info(f"SYNC_FILE: File {path} with CID {cid} downloaded to {dest_path}")
                    subprocess.run(
                        [ipfs_path, "pin", "add", cid],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    logger.info(f"SYNC_PIN: File {path} pinned with CID {cid}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"SYNC_FILE_ERROR: Failed to download or pin file {path} with CID {cid}: {e.stderr}")
        logger.info("SYNC_FILES_END: Finished file synchronization to Synced_dir")
    except Exception as e:
        logger.error(f"SYNC_FILES_ERROR: Failed to synchronize files to Synced_dir: {e}")
