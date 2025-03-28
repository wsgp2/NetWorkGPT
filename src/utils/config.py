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


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Загружает конфигурацию из YAML файла
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        Словарь с конфигурацией
        
    Raises:
        FileNotFoundError: Если файл конфигурации не найден
        yaml.YAMLError: При ошибке парсинга YAML
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        # Проверяем наличие переменных окружения и заменяем значения
        _replace_env_vars(config)
        
        logger.info(f"Конфигурация успешно загружена из {config_path}")
        return config
    
    except yaml.YAMLError as e:
        logger.error(f"Ошибка при загрузке конфигурации: {e}")
        raise


def _replace_env_vars(config: Dict[str, Any]) -> None:
    """
    Рекурсивно заменяет переменные вида ${ENV_VAR} на значения из переменных окружения
    
    Args:
        config: Словарь конфигурации для обработки
    """
    for key, value in config.items():
        if isinstance(value, dict):
            _replace_env_vars(value)
        elif isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var = value[2:-1]
            env_value = os.environ.get(env_var)
            
            if env_value is not None:
                config[key] = env_value
                logger.debug(f"Переменная ${env_var} заменена на значение из окружения")
            else:
                logger.warning(f"Переменная окружения {env_var} не найдена")


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """
    Сохраняет конфигурацию в YAML файл
    
    Args:
        config: Словарь с конфигурацией
        config_path: Путь для сохранения файла
        
    Raises:
        yaml.YAMLError: При ошибке сериализации в YAML
    """
    try:
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
            
        logger.info(f"Конфигурация успешно сохранена в {config_path}")
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфигурации: {e}")
        raise
