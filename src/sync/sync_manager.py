#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Менеджер синхронизации для NetWorkGPT
Отвечает за синхронизацию контактов между Telegram и Google Contacts

Авторы: Сергей Дышкант, Андрианов Вячеслав
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
import json

from loguru import logger

from src.database.database import DatabaseManager
from src.database.models import User, Contact, SocialLink, SyncLog
from src.api.google_api import GoogleContactsAPI


class SyncManager:
    """Менеджер для синхронизации контактов между Telegram и Google Contacts"""
    
    def __init__(self, config: Dict[str, Any], db_manager: DatabaseManager):
        """
        Инициализация менеджера синхронизации
        
        Args:
            config: Конфигурация приложения
            db_manager: Менеджер базы данных
        """
        self.config = config
        self.db_manager = db_manager
        self.google_api = GoogleContactsAPI(config)
        self.sync_interval = config['sync']['interval']  # в минутах
        self.batch_size = config['sync']['batch_size']
        self.sync_fields = config['sync']['fields']
    
    async def sync_contacts(self, telegram_id: int) -> Dict[str, int]:
        """
        Выполняет синхронизацию контактов для пользователя
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Словарь с результатами синхронизации: 
            {"total": общее количество, "added": добавлено, "updated": обновлено, "skipped": пропущено}
            
        Raises:
            ValueError: Если пользователь не авторизован в Google
        """
        # Получаем пользователя из БД
        user = await self.db_manager.get_user(telegram_id)
        if not user or not user.google_token:
            raise ValueError("Пользователь не авторизован в Google")
        
        # Создаем запись о начале синхронизации
        sync_log = await self._create_sync_log(user.id)
        
        try:
            # Получаем контакты из Google
            google_contacts = await self.google_api.get_contacts(user.google_token, user.google_refresh_token)
            
            # Обрабатываем контакты и сохраняем в БД
            result = await self._process_contacts(user.id, google_contacts)
            
            # Обновляем статус синхронизации
            await self._update_sync_log(sync_log.id, True, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при синхронизации контактов для пользователя {telegram_id}: {e}")
            await self._update_sync_log(sync_log.id, False, error_message=str(e))
            raise
    
    # Дополнительные методы будут добавлены в следующем файле
