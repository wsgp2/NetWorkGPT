#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
NetWorkGPT - интеллектуальная система управления контактами
Объединяет Telegram и Google Contacts с AI-аналитикой

Автор: Сергей Дышкант (c) 2025
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from loguru import logger

# Изменение импортов для корректной работы
from bot.telegram_bot import TelegramBot
from database.database import DatabaseManager
from sync.sync_manager import SyncManager
from utils.config import load_config


async def main():
    """Основная функция запуска приложения"""
    parser = argparse.ArgumentParser(description="NetWorkGPT - интеллектуальная система управления контактами")
    parser.add_argument("--config", type=str, default="configs/config.yaml", help="Путь к файлу конфигурации")
    parser.add_argument("--debug", action="store_true", help="Включить режим отладки")
    args = parser.parse_args()
    
    # Загрузка конфигурации
    config_path = Path(root_dir) / args.config
    config = load_config(config_path)
    
    # Настройка логирования
    log_level = "DEBUG" if args.debug else config["logging"]["level"]
    log_file = Path(root_dir) / config["logging"]["file"]
    log_file.parent.mkdir(exist_ok=True, parents=True)
    
    # Конфигурация логгера
    logger.remove()  # Удаление стандартного обработчика
    logger.add(sys.stderr, level=log_level)  # Вывод в консоль
    logger.add(
        str(log_file),
        rotation=f"{config['logging']['max_size_mb']} MB",
        retention=config['logging']['backup_count'],
        encoding="utf-8"
    )
    
    logger.info(f"NetWorkGPT запускается... Режим отладки: {args.debug}")
    
    try:
        # Инициализация базы данных
        db_config = config["database"]
        # Используем SQLite вместо PostgreSQL для локальной разработки
        db_url = db_config["url"]
        db_manager = DatabaseManager(db_url)
        await db_manager.initialize()
        
        logger.info("База данных успешно инициализирована")
        
        # Инициализация менеджера синхронизации
        sync_manager = SyncManager(config, db_manager)
        
        # Запуск Telegram бота
        bot = TelegramBot(config, db_manager, sync_manager)
        await bot.start()
        
    except Exception as e:
        logger.exception(f"Ошибка при запуске приложения: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        # Создание и запуска цикла событий
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
        sys.exit(0)
