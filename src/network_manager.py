# network_manager.py
# Manage peers, check routing, and list pinned files.
# Version 2.3.1:
#   * use ipfs routing findprovs (the dht API was removed in 0.27)
#   * do not look up the node's own PeerID with findpeer
#   * list_pinned_files reads {cid, date_added} mappings from SQLite

import subprocess
import asyncio

MODULE_VERSION = "2.3.1"


def _first_cid(file_cid_mapping):
    """Return the first CID from a legacy or current mapping."""
    if not file_cid_mapping:
        return None
    for entry in file_cid_mapping.values():
        if isinstance(entry, dict):
            return entry.get("cid")
        if isinstance(entry, str):
            return entry
    return None


async def manage_mdns_connections(ipfs_path, node_name, logger, file_cid_mapping=None):
    logger.info(f"MODULE_VERSION: network_manager version {MODULE_VERSION}")
    logger.info("MDNS_CONNECTIONS_START: Starting mDNS connection management")

    try:
        result = subprocess.run(
            [ipfs_path, "id", "--format=<id>"],
            capture_output=True,
            text=True,
            check=True,
        )
        own_peer_id = result.stdout.strip()
        logger.info(f"MDNS_PEER_ID: PeerID for node {node_name}: {own_peer_id}")
    except subprocess.CalledProcessError as e:
        logger.error(f"MDNS_PEER_ID_ERROR: Failed to retrieve PeerID: {e.stderr}")
        own_peer_id = None

    while True:
        try:
            result = subprocess.run(
                [ipfs_path, "swarm", "peers"],
                capture_output=True,
                text=True,
                check=True,
            )
            peers = [p for p in result.stdout.splitlines() if p.strip()]
            logger.info(f"MDNS_PEERS: Connected peers: {len(peers)}")
            for peer in peers:
                logger.debug(f"MDNS_PEERS: Active connection: {peer}")
                try:
                    subprocess.run(
                        [ipfs_path, "swarm", "connect", peer],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    logger.debug(f"MDNS_CONNECT: Successfully connected to {peer}")
                except (subprocess.CalledProcessError, IndexError) as e:
                    logger.warning(f"MDNS_CONNECT_ERROR: Failed to connect to {peer}: {str(e)}")

            # Check CID providers rather than looking up this node in the DHT.
            # ipfs routing findpeer <own_peer_id> returns:
            # "finding your own node in the DHT is currently not supported"
            cid = _first_cid(file_cid_mapping)
            if cid:
                try:
                    logger.debug(f"ROUTING_CHECK: Executing ipfs routing findprovs {cid}")
                    result = subprocess.run(
                        [ipfs_path, "routing", "findprovs", cid],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    providers = result.stdout.strip() or "(empty)"
                    logger.info(f"ROUTING_CHECK: Providers found for CID {cid}: {providers}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"ROUTING_CHECK_ERROR: Routing check failed: {e.stderr}")
                except Exception as e:
                    logger.warning(f"ROUTING_CHECK_ERROR: Unexpected routing check error: {str(e)}")
            else:
                logger.info("ROUTING_CHECK: No CID in mapping; skipping findprovs")

            logger.info("MDNS_CONNECTIONS: Waiting 60 seconds")
            await asyncio.sleep(60)
        except subprocess.CalledProcessError as e:
            logger.error(f"MDNS_ERROR: Failed to manage mDNS connections: {e.stderr}")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"MDNS_ERROR: Unexpected error managing mDNS connections: {str(e)}")
            await asyncio.sleep(60)


def list_pinned_files(ipfs_path, node_name, logger, file_cid_mapping, synced_dir, database_path):
    logger.info(f"MODULE_VERSION: network_manager version {MODULE_VERSION}")
    logger.info("LIST_PINNED_START: Starting pinned file listing")
    try:
        result = subprocess.run(
            [ipfs_path, "pin", "ls", "--type=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        pinned_cids = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                cid, pin_type = parts[0], parts[1]
                pinned_cids[cid] = pin_type

        logger.info(f"LIST_PINNED: Pinned files and directories on node {node_name}:")
        if not file_cid_mapping:
            logger.info("LIST_PINNED: SQLite file list is empty; no files to display")
        for path, entry in file_cid_mapping.items():
            if isinstance(entry, dict):
                cid = entry.get("cid", "")
                date_added = entry.get("date_added", "unknown")
            else:
                cid = entry
                date_added = "unknown"
            pin_type = pinned_cids.get(cid, "unknown")
            logger.info(
                f"LIST_PINNED: CID: {cid}, Type: {pin_type}, Path: {path}, Date added: {date_added}"
            )

        from file_sync import sync_files_to_synced_dir

        sync_files_to_synced_dir(
            ipfs_path, synced_dir, logger, file_cid_mapping, database_path
        )
        logger.info("LIST_PINNED_END: Finished pinned file listing")
    except subprocess.CalledProcessError as e:
        logger.error(f"LIST_PINNED_ERROR: Failed to list pins: {e.stderr}")
    except Exception as e:
        logger.error(f"LIST_PINNED_ERROR: Unexpected error listing pins: {e}")
