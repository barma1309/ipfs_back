import os
import subprocess
import logging

# Версия модуля
MODULE_VERSION = "2.1.7"


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

        result = subprocess.run(
            [ipfs_path, 'config', 'Routing.Type', 'dhtclient'],
            capture_output=True, text=True, check=True
        )
        logger.info("PUBLIC_NETWORK: DHT включён (Routing.Type = dhtclient)")

        result = subprocess.run(
            [ipfs_path, 'config', 'Discovery.MDNS.Enabled', '--bool', 'true'],
            capture_output=True, text=True, check=True
        )
        logger.info("PUBLIC_NETWORK: mDNS включён (Discovery.MDNS.Enabled = true)")

        try:
            result = subprocess.run(
                [ipfs_path, 'config', 'Discovery.MDNS.Interval', '--json', '30'],
                capture_output=True, text=True, check=True
            )
            logger.info("PUBLIC_NETWORK: mDNS интервал установлен на 30 секунд")
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"PUBLIC_NETWORK_WARNING: Не удалось установить Discovery.MDNS.Interval: {e.stderr}. Продолжаем с настройками по умолчанию.")

    except subprocess.CalledProcessError as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Ошибка при настройке публичной сети: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"PUBLIC_NETWORK_ERROR: Общая ошибка при настройке публичной сети: {e}")
        raise
