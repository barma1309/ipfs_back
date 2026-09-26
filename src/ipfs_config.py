# ipfs_config.py
# Инициализация репозитория и публичной сети Kubo.
# Версия 2.2.3:
#   * CLI: IPFS_BIN → PATH → Windows-пути (IPFS_PATH больше не считается бинарником)
#   * репозиторий: env IPFS_PATH → ~/.ipfs
#   * init только если нет $IPFS_PATH/config

import os
import shutil
import subprocess

MODULE_VERSION = "2.2.3"


def _repo_dir():
    return os.environ.get("IPFS_PATH") or os.path.expanduser("~/.ipfs")


def resolve_ipfs_path(logger=None):
    """
    Ищет исполняемый файл Kubo CLI.
    Приоритет:
      1. IPFS_BIN
      2. ipfs / ipfs.exe в PATH
      3. известные пути IPFS Desktop / Kubo на Windows
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
                logger.info(f"IPFS_BIN_RESOLVED: найден CLI: {path}")
            return path

    raise FileNotFoundError(
        "Не найден ipfs. Укажите IPFS_BIN или добавьте ipfs в PATH."
    )


def ensure_ipfs_initialized(ipfs_path, logger):
    logger.info(f"MODULE_VERSION: ipfs_config версия {MODULE_VERSION}")
    try:
        ipfs_dir = _repo_dir()
        config_file = os.path.join(ipfs_dir, "config")
        env = os.environ.copy()
        env["IPFS_PATH"] = ipfs_dir

        if not os.path.isfile(config_file):
            logger.info(f"IPFS_INIT: Репозиторий IPFS не найден ({ipfs_dir}), инициализация...")
            result = subprocess.run(
                [ipfs_path, "init"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            logger.info(f"IPFS_INIT: Репозиторий успешно инициализирован: {result.stdout}")
        else:
            logger.info(f"IPFS_INIT: Репозиторий IPFS уже существует: {ipfs_dir}")
    except subprocess.CalledProcessError as e:
        logger.error(f"IPFS_INIT_ERROR: Ошибка при инициализации IPFS: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"IPFS_INIT_ERROR: Общая ошибка при инициализации IPFS: {e}")
        raise


def setup_public_network(ipfs_path, logger, node_name):
    logger.info(f"MODULE_VERSION: ipfs_config версия {MODULE_VERSION}")
    try:
        ipfs_dir = _repo_dir()
        env = os.environ.copy()
        env["IPFS_PATH"] = ipfs_dir
        swarm_key_path = os.path.join(ipfs_dir, "swarm.key")

        if os.path.exists(swarm_key_path):
            os.remove(swarm_key_path)
            logger.info(
                f"PUBLIC_NETWORK: Удалён swarm.key из {swarm_key_path} для работы в публичной сети"
            )

        subprocess.run(
            [ipfs_path, "config", "Routing.Type", "autoclient"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        logger.info("PUBLIC_NETWORK: DHT включён (Routing.Type = autoclient)")

        subprocess.run(
            [ipfs_path, "config", "Discovery.MDNS.Enabled", "--bool", "true"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        logger.info("PUBLIC_NETWORK: mDNS включён (Discovery.MDNS.Enabled = true)")
        logger.info("PUBLIC_NETWORK: Discovery.MDNS.Interval не задаём (ключ удалён в Kubo)")
    except subprocess.CalledProcessError as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Ошибка при настройке публичной сети: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Общая ошибка при настройке публичной сети: {e}")
        raise