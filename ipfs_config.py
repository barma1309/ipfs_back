import os
import shutil
import subprocess
import logging

# Версия модуля
MODULE_VERSION = "2.1.8"

IPFS_DESKTOP_RELATIVE = os.path.join(
    'resources', 'app.asar.unpacked', 'node_modules', 'kubo', 'kubo', 'ipfs.exe'
)


def resolve_ipfs_path(logger=None):
    candidates = []

    env_path = os.environ.get('IPFS_PATH')
    if env_path:
        candidates.append(env_path)

    local_app = os.environ.get('LOCALAPPDATA', '')
    if local_app:
        candidates.append(os.path.join(local_app, 'Programs', 'IPFS Desktop', IPFS_DESKTOP_RELATIVE))

    program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
    candidates.append(os.path.join(program_files, 'IPFS Desktop', IPFS_DESKTOP_RELATIVE))

    program_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
    candidates.append(os.path.join(program_files_x86, 'IPFS Desktop', IPFS_DESKTOP_RELATIVE))

    which_path = shutil.which('ipfs')
    if which_path:
        candidates.append(which_path)

    seen = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path):
            if logger:
                logger.info(f"IPFS_PATH: Найден ipfs: {path}")
            return path

    searched = '\n  - '.join(seen)
    raise FileNotFoundError(
        f"ipfs.exe не найден. Проверены пути:\n  - {searched}\n"
        "Установите IPFS Desktop/Kubo или задайте переменную окружения IPFS_PATH."
    )


def ensure_ipfs_initialized(ipfs_path, logger):
    logger.info(f"MODULE_VERSION: ipfs_config версия {MODULE_VERSION}")
    try:
        ipfs_dir = os.path.expanduser("~/.ipfs")
        if not os.path.exists(ipfs_dir):
            logger.info("IPFS_INIT: Репозиторий IPFS не найден, инициализация...")
            result = subprocess.run(
                [ipfs_path, 'init'],
                capture_output=True, text=True, check=True
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
    logger.info(f"MODULE_VERSION: ipfs_config версия {MODULE_VERSION}")
    try:
        ipfs_dir = os.path.expanduser("~/.ipfs")
        swarm_key_path = os.path.join(ipfs_dir, "swarm.key")

        if os.path.exists(swarm_key_path):
            os.remove(swarm_key_path)
            logger.info(f"PUBLIC_NETWORK: Удалён swarm.key из {swarm_key_path} для работы в публичной сети")

        subprocess.run(
            [ipfs_path, 'config', 'Routing.Type', 'dhtclient'],
            capture_output=True, text=True, check=True
        )
        logger.info("PUBLIC_NETWORK: DHT включён (Routing.Type = dhtclient)")

        subprocess.run(
            [ipfs_path, 'config', 'Discovery.MDNS.Enabled', '--bool', 'true'],
            capture_output=True, text=True, check=True
        )
        logger.info("PUBLIC_NETWORK: mDNS включён (Discovery.MDNS.Enabled = true)")

    except subprocess.CalledProcessError as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Ошибка при настройке публичной сети: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Общая ошибка при настройке публичной сети: {e}")
        raise