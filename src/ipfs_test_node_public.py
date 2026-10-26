# ipfs_test_node_public.py
# File synchronization agent entry point using the local Kubo CLI.
# Version 2.3.1: SQLite storage and compatibility with Kubo 0.27-0.43.
#   * migrate JSON to SQLite automatically on first startup
#   * use `ipfs routing findprovs` instead of `ipfs dht *`
#   * do not call findpeer for the node's own PeerID
#   * do not configure Discovery.MDNS.Interval (removed in Kubo)
#   * set Routing.Type=autoclient instead of the older dhtclient default
#   * call `ipfs provide once` after pinning (routing provide deprecated in 0.42)

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

# Shared release version. All module versions must match.
SCRIPT_VERSION = "2.3.1"


def setup_logging(node_name):
    """Configure file and console logging; truncate the previous log on startup."""
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

    logger.info(f"MODULE_VERSION: ipfs_test_node_public version {SCRIPT_VERSION}")
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
                f"VERSION_MISMATCH: Module {module} has version {version}, "
                f"expected {expected_version}"
            )
    return logger


def initialize_file_cid_mapping(database_path, logger):
    try:
        return FileCIDMapping(database_path)
    except Exception:
        logger.exception("MAIN_ERROR: Failed to initialize SQLite or migrate JSON")
        return None


async def main():
    node_name = "local"
    upload_dir = os.path.join(os.path.dirname(__file__), "../Upload")
    synced_dir = os.path.join(os.path.dirname(__file__), "../Synced_dir")
    database_path = os.path.join(os.path.dirname(__file__), "../data", "ipfs.sqlite3")

    logger = setup_logging(node_name)
    logger.info(
        f"START: Starting script version {SCRIPT_VERSION} (public network) on node {node_name}"
    )

    logger.info("MAIN: Checking directories")
    try:
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(synced_dir, exist_ok=True)
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        logger.info(
            f"MAIN: Directories created: {upload_dir}, {synced_dir}, {os.path.dirname(database_path)}"
        )
    except Exception as e:
        logger.error(f"MAIN_ERROR: Failed to create directories: {e}")
        return

    logger.info("MAIN: Loading SQLite")
    file_cid_mapping = initialize_file_cid_mapping(database_path, logger)
    if file_cid_mapping is None:
        logger.error("MAIN_ERROR: Failed to initialize SQLite; shutting down")
        return

    logger.info("MAIN: Locating Kubo CLI (ipfs.exe)")
    try:
        ipfs_path = resolve_ipfs_path(logger)
    except FileNotFoundError as e:
        logger.error(f"MAIN_ERROR: {e}")
        return

    logger.info("MAIN: Checking IPFS daemon status")
    try:
        subprocess.run(
            [ipfs_path, "id"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        logger.info("MAIN: IPFS daemon is running")
    except subprocess.CalledProcessError as e:
        logger.error(f"MAIN_ERROR: Failed to check IPFS daemon: {e.stderr}")
        logger.info("MAIN: Attempting to start IPFS daemon")
        try:
            subprocess.Popen(
                [ipfs_path, "daemon"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await asyncio.sleep(10)
        except Exception as start_err:
            logger.error(f"MAIN_ERROR: Failed to start IPFS daemon: {start_err}")
            return
    except Exception as e:
        logger.error(f"MAIN_ERROR: Unexpected error checking IPFS daemon: {e}")
        return

    logger.info("MAIN: Initializing IPFS")
    try:
        ensure_ipfs_initialized(ipfs_path, logger)
    except Exception as e:
        logger.error(f"MAIN_ERROR: Failed to initialize IPFS: {e}")
        return

    logger.info("MAIN: Configuring public network")
    try:
        setup_public_network(ipfs_path, logger, node_name)
    except Exception as e:
        logger.error(f"MAIN_ERROR: Failed to configure public network: {e}")
        return

    logger.info("MAIN: Retrieving PeerID")
    try:
        result = subprocess.run(
            [ipfs_path, "id", "--format=<id>"],
            capture_output=True,
            text=True,
            check=True,
        )
        peer_id = result.stdout.strip()
        logger.info(f"PEER_ID: PeerID for node {node_name}: {peer_id}")
    except subprocess.CalledProcessError as e:
        logger.error(f"PEER_ID_ERROR: Failed to retrieve PeerID: {e.stderr}")
        return

    logger.info("MAIN: Checking for new files")
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
        logger.error(f"MAIN_ERROR: Failed to check for new files: {e}")
        return

    logger.info("MAIN: Configuring filesystem observer")
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
        logger.info("MAIN: Filesystem observer started")
    except Exception as e:
        logger.error(f"MAIN_ERROR: Failed to configure filesystem observer: {e}")
        if observer is not None:
            observer.stop()
        return

    logger.info("MAIN: Starting pin check and mDNS loops")
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
        logger.info("STOP: Script stopped")
    except Exception as e:
        logger.error(f"MAIN_ERROR: Error in main loop: {e}")
    finally:
        if observer is not None:
            observer.stop()
            observer.join()


async def run_pin_check_loop(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, database_path):
    while True:
        logger.info("PIN_CHECK_LOOP: Starting pin check cycle")
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
            logger.error(f"PIN_CHECK_LOOP_ERROR: Error in pin check cycle: {e}")
        logger.info("PIN_CHECK_LOOP: Waiting 60 seconds")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
