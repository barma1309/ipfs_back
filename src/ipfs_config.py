# ipfs_config.py
# Initialize the Kubo repository and configure the public network.
# Version 2.3.1:
#   * CLI: IPFS_BIN -> PATH -> Windows locations (IPFS_PATH is a repository path)
#   * repository: IPFS_PATH environment variable -> ~/.ipfs
#   * initialize only when $IPFS_PATH/config is missing

import os
import shutil
import subprocess

MODULE_VERSION = "2.3.1"


def _repo_dir():
    return os.environ.get("IPFS_PATH") or os.path.expanduser("~/.ipfs")


def resolve_ipfs_path(logger=None):
    """
    Locate the Kubo CLI executable.
    Search order:
      1. IPFS_BIN
      2. ipfs / ipfs.exe on PATH
      3. Common IPFS Desktop / Kubo installation paths on Windows
    """
    candidates = []
    env_bin = os.environ.get("IPFS_BIN")
    if env_bin:
        candidates.append(env_bin)

    which = shutil.which("ipfs") or shutil.which("ipfs.exe")
    if which:
        candidates.append(which)

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates.extend(
        [
            os.path.join(
                program_files,
                "IPFS Desktop",
                "resources",
                "app.asar.unpacked",
                "node_modules",
                "kubo",
                "kubo",
                "ipfs.exe",
            ),
            os.path.join(
                program_files_x86,
                "IPFS Desktop",
                "resources",
                "app.asar.unpacked",
                "node_modules",
                "kubo",
                "kubo",
                "ipfs.exe",
            ),
            os.path.join(program_files, "Kubo", "ipfs.exe"),
            os.path.join(program_files, "ipfs", "ipfs.exe"),
            os.path.join(local_app, "Programs", "ipfs", "ipfs.exe") if local_app else "",
        ]
    )

    seen = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path):
            if logger:
                logger.info(f"IPFS_BIN_RESOLVED: CLI found: {path}")
            return path

    raise FileNotFoundError(
        "ipfs not found. Set IPFS_BIN or add ipfs to PATH."
    )


def ensure_ipfs_initialized(ipfs_path, logger):
    logger.info(f"MODULE_VERSION: ipfs_config version {MODULE_VERSION}")
    try:
        ipfs_dir = _repo_dir()
        config_file = os.path.join(ipfs_dir, "config")
        env = os.environ.copy()
        env["IPFS_PATH"] = ipfs_dir

        if not os.path.isfile(config_file):
            logger.info(f"IPFS_INIT: IPFS repository not found ({ipfs_dir}); initializing...")
            result = subprocess.run(
                [ipfs_path, "init"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            logger.info(f"IPFS_INIT: Repository initialized successfully: {result.stdout}")
        else:
            logger.info(f"IPFS_INIT: IPFS repository already exists: {ipfs_dir}")
    except subprocess.CalledProcessError as e:
        logger.error(f"IPFS_INIT_ERROR: Failed to initialize IPFS: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"IPFS_INIT_ERROR: Unexpected error initializing IPFS: {e}")
        raise


def setup_public_network(ipfs_path, logger, node_name):
    logger.info(f"MODULE_VERSION: ipfs_config version {MODULE_VERSION}")
    try:
        ipfs_dir = _repo_dir()
        env = os.environ.copy()
        env["IPFS_PATH"] = ipfs_dir
        swarm_key_path = os.path.join(ipfs_dir, "swarm.key")

        if os.path.exists(swarm_key_path):
            os.remove(swarm_key_path)
            logger.info(
                f"PUBLIC_NETWORK: Removed swarm.key from {swarm_key_path} to use the public network"
            )

        subprocess.run(
            [ipfs_path, "config", "Routing.Type", "autoclient"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        logger.info("PUBLIC_NETWORK: DHT enabled (Routing.Type = autoclient)")

        subprocess.run(
            [ipfs_path, "config", "Discovery.MDNS.Enabled", "--bool", "true"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        logger.info("PUBLIC_NETWORK: mDNS enabled (Discovery.MDNS.Enabled = true)")
        logger.info("PUBLIC_NETWORK: Skipping Discovery.MDNS.Interval (setting removed in Kubo)")
    except subprocess.CalledProcessError as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Failed to configure public network: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Unexpected error configuring public network: {e}")
        raise
