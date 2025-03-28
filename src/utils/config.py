#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Модуль для работы с конфигурацией приложения
"""

import os
from pathlib import Path
from typing import Dict, Any

import yaml
from loguru import logger

# Попытка импортировать dotenv для загрузки .env файла
try:
    from dotenv import load_dotenv
    # Загружаем переменные окружения из .env файла
    load_dotenv()
    logger.info("Переменные окружения загружены из .env файла")
except ImportError:
    logger.warning("python-dotenv не установлен, .env файл не будет загружен")


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Загружает конфигурацию из YAML файла или создает конфигурацию из переменных окружения
    
    Args:
        config_path: Путь к файлу конфигурации (опционально)
        
    Returns:
        Словарь с конфигурацией
        
    Raises:
        FileNotFoundError: Если файл конфигурации не найден и нет переменных окружения
    """
    config = {}
    
    # Пробуем загрузить из файла, если путь указан
    if config_path:
        config_file = Path(config_path)
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as file:
                    config = yaml.safe_load(file) or {}
                logger.info(f"Конфигурация загружена из {config_path}")
            except yaml.YAMLError as e:
                logger.error(f"Ошибка при загрузке конфигурации из файла: {e}")
    
    # Дополняем или заменяем значениями из переменных окружения
    env_config = _load_from_env()
    
    # Объединяем конфигурации, env имеет приоритет
    if env_config:
        _merge_configs(config, env_config)
        logger.info("Конфигурация дополнена из переменных окружения")
    
    # Если конфигурация пуста, выдаем ошибку
    if not config:
        raise FileNotFoundError("Не удалось загрузить конфигурацию ни из файла, ни из переменных окружения")
    
    return config


def _load_from_env() -> Dict[str, Any]:
    """
    Создает конфигурацию из переменных окружения
    
    Returns:
        Словарь с конфигурацией из переменных окружения
    """
    config = {}
    
    # API ключи
    if os.environ.get('TELEGRAM_TOKEN'):
        if 'api_keys' not in config:
            config['api_keys'] = {}
        config['api_keys']['telegram_token'] = os.environ.get('TELEGRAM_TOKEN')
    
    # Google API настройки
    if any([os.environ.get('GOOGLE_CLIENT_ID'), os.environ.get('GOOGLE_CLIENT_SECRET'), os.environ.get('GOOGLE_REDIRECT_URI')]):
        if 'google_api' not in config:
            config['google_api'] = {}
        
        if os.environ.get('GOOGLE_CLIENT_ID'):
            config['google_api']['client_id'] = os.environ.get('GOOGLE_CLIENT_ID')
            
        if os.environ.get('GOOGLE_CLIENT_SECRET'):
            config['google_api']['client_secret'] = os.environ.get('GOOGLE_CLIENT_SECRET')
            
        if os.environ.get('GOOGLE_REDIRECT_URI'):
            config['google_api']['redirect_uri'] = os.environ.get('GOOGLE_REDIRECT_URI')
            
        # Стандартные области доступа, если не указано иное
        if 'scopes' not in config['google_api']:
            config['google_api']['scopes'] = [
                "https://www.googleapis.com/auth/contacts.readonly"
                # "https://www.googleapis.com/auth/contacts",
                # "https://www.googleapis.com/auth/userinfo.email",
                # "https://www.googleapis.com/auth/userinfo.profile"
            ]
    
    # Настройки бота
    if 'bot' not in config:
        config['bot'] = {}
        config['bot']['welcome_message'] = os.environ.get('BOT_WELCOME_MESSAGE', 
                                                    "Добро пожаловать в NetWorkGPT! Я помогу вам управлять контактами и синхронизировать их с Google.")
        # Пустой список админов по умолчанию
        config['bot']['admin_ids'] = []
    
    return config


def _merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> None:
    """
    Рекурсивно объединяет два словаря конфигураций
    
    Args:
        base_config: Базовая конфигурация
        override_config: Конфигурация с приоритетными значениями
    """
    for key, value in override_config.items():
        if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
            _merge_configs(base_config[key], value)
        else:
            base_config[key] = value


def _replace_env_vars(config: Dict[str, Any]) -> None:
    """Заменяет placeholder'ы на значения из переменных окружения
    
    Args:
        config: Словарь с конфигурацией для обработки
    """
    for key, value in config.items():
        if isinstance(value, dict):
            _replace_env_vars(value)
        elif isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var = value[2:-1]
            env_value = os.environ.get(env_var)
            if env_value:
                config[key] = env_value
            else:
                logger.warning(f"Переменная окружения {env_var} не найдена")


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """Сохраняет конфигурацию в YAML файл
    
    Args:
        config: Словарь с конфигурацией
        config_path: Путь для сохранения файла
        
    Raises:
        yaml.YAMLError: При ошибке сериализации в YAML
    """
    try:
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
            
        logger.info(f"Конфигурация сохранена в {config_path}")
    
    except (yaml.YAMLError, IOError) as e:
        logger.error(f"Ошибка при сохранении конфигурации: {e}")
        raise
