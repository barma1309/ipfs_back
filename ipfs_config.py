# ipfs_config.py
# Инициализация репозитория и публичной сети Kubo.
# Версия 2.2.2:
#   * Discovery.MDNS.Interval удалён из конфига Kubo — больше не выставляем
#   * Routing.Type=autoclient (актуальный клиентский режим вместо dhtclient)
#   * поиск ipfs.exe: env IPFS_PATH → PATH → типичные пути Windows

import os
import shutil
import subprocess

MODULE_VERSION = "2.2.2"


def resolve_ipfs_path(logger=None):
    """
    Ищет исполняемый файл Kubo CLI.
    Приоритет:
      1. переменная окружения IPFS_PATH (полный путь к ipfs.exe / ipfs)
      2. команда ipfs / ipfs.exe в PATH
      3. известные пути IPFS Desktop и standalone Kubo на Windows
    """
    env_path = os.environ.get("IPFS_PATH")
    candidates = []
    if env_path:
        candidates.append(env_path)

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
                logger.info(f"IPFS_PATH_RESOLVED: найден CLI: {path}")
            return path

    raise FileNotFoundError(
        "Не найден ipfs.exe. Установите IPFS Desktop / Kubo, добавьте ipfs в PATH "
        "или задайте полный путь в переменной окружения IPFS_PATH."
    )


def ensure_ipfs_initialized(ipfs_path, logger):
    logger.info(f"MODULE_VERSION: ipfs_config версия {MODULE_VERSION}")
    try:
        ipfs_dir = os.path.expanduser("~/.ipfs")
        if not os.path.exists(ipfs_dir):
            logger.info("IPFS_INIT: Репозиторий IPFS не найден, инициализация...")
            result = subprocess.run(
                [ipfs_path, "init"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"IPFS_INIT: Репозиторий успешно инициализирован: {result.stdout}")
        else:
            logger.info("IPFS_INIT: Репозиторий IPFS уже существует")
    except subprocess.CalledProcessError as e:
        logger.error(f"IPFS_INIT_ERROR: Ошибка при инициализации IPFS: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"IPFS_INIT_ERROR: Общая ошибка при инициализации IPFS: {e}")
        raise


def setup_public_network(ipfs_path, logger, node_name):
    """
    Готовит узел к публичной сети Amino DHT.
    swarm.key удаляется, чтобы не остаться в приватном swarm.
    """
    logger.info(f"MODULE_VERSION: ipfs_config версия {MODULE_VERSION}")
    try:
        ipfs_dir = os.path.expanduser("~/.ipfs")
        swarm_key_path = os.path.join(ipfs_dir, "swarm.key")

        if os.path.exists(swarm_key_path):
            os.remove(swarm_key_path)
            logger.info(
                f"PUBLIC_NETWORK: Удалён swarm.key из {swarm_key_path} для работы в публичной сети"
            )

        # autoclient: публичный DHT + delegated routers, без роли DHT-сервера.
        # Ключ dhtclient ещё принимается, но default Kubo 0.38+ — auto/autoclient.
        subprocess.run(
            [ipfs_path, "config", "Routing.Type", "autoclient"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("PUBLIC_NETWORK: DHT включён (Routing.Type = autoclient)")

        subprocess.run(
            [ipfs_path, "config", "Discovery.MDNS.Enabled", "--bool", "true"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("PUBLIC_NETWORK: mDNS включён (Discovery.MDNS.Enabled = true)")

        # Discovery.MDNS.Interval REMOVED в современном Kubo (zeroconf mDNS).
        # Попытка выставить ключ даёт warning и ничего не меняет — поэтому не вызываем.
        logger.info(
            "PUBLIC_NETWORK: Discovery.MDNS.Interval не задаём (ключ удалён в Kubo)"
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Ошибка при настройке публичной сети: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Общая ошибка при настройке публичной сети: {e}")
        raise
