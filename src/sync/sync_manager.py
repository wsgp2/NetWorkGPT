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

# Исправлены относительные импорты для корректного запуска бота
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
    
    async def exchange_auth_code(self, auth_code: str, telegram_id: int) -> Dict[str, Any]:
        """
        Обменивает код авторизации Google на токены доступа и сохраняет их в БД
        
        Args:
            auth_code: Код авторизации полученный от Google
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Словарь с результатами обмена кода авторизации
            
        Raises:
            Exception: Если произошла ошибка при обмене кода авторизации
        """
        try:
            # Получаем токены из Google API
            tokens = await self.google_api.get_tokens_from_code(auth_code)
            
            # Получаем пользователя из БД
            user = await self.db_manager.get_user(telegram_id)
            
            if not user:
                # Создаем нового пользователя, если его нет в БД
                user_data = {
                    'telegram_id': telegram_id,
                    'google_token': tokens.get('access_token'),
                    'google_refresh_token': tokens.get('refresh_token'),
                    'token_expiry': tokens.get('expiry').isoformat() if tokens.get('expiry') else None,
                }
                await self.db_manager.add_user(user_data)
                logger.info(f"Создан новый пользователь с Telegram ID {telegram_id}")
            else:
                # Обновляем токены пользователя, если он уже существует в БД
                update_data = {
                    'google_token': tokens.get('access_token'),
                    'google_refresh_token': tokens.get('refresh_token'),
                    'token_expiry': tokens.get('expiry').isoformat() if tokens.get('expiry') else None,
                }
                await self.db_manager.update_user(user.id, update_data)
                logger.info(f"Обновлены токены для пользователя с Telegram ID {telegram_id}")
            
            return {
                'success': True,
                'message': "Авторизация успешна завершена",
                'tokens': {
                    'access_token': tokens.get('access_token'),
                    'expires_in': tokens.get('expires_in'),
                    'has_refresh_token': bool(tokens.get('refresh_token'))
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обмене кода авторизации на токены: {e}")
            return {
                'success': False,
                'message': f"Произошла ошибка при авторизации: {str(e)}"
            }
    
    async def refresh_tokens(self, telegram_id: int) -> bool:
        """
        Обновляет токены доступа для пользователя, используя refresh_token
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            True, если токены успешно обновлены, иначе False
        """
        try:
            # Получаем пользователя из БД
            user = await self.db_manager.get_user(telegram_id)
            if not user or not user.google_refresh_token:
                logger.warning(f"Нет refresh_token для пользователя {telegram_id}")
                return False
                
            # Получаем новые токены из Google API
            tokens = await self.google_api.refresh_access_token(user.google_refresh_token)
            
            # Обновляем токены в БД
            update_data = {
                'google_token': tokens.get('access_token'),
                'token_expiry': tokens.get('expiry').isoformat() if tokens.get('expiry') else None,
            }
            await self.db_manager.update_user(user.id, update_data)
            
            logger.info(f"Токены для пользователя {telegram_id} успешно обновлены")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении токенов: {e}")
            return False
    
    async def _create_sync_log(self, user_id: int) -> SyncLog:
        """
        Создает запись о начале синхронизации в логе
        
        Args:
            user_id: ID пользователя в БД
            
        Returns:
            Объект SyncLog
        """
        sync_log_data = {
            'user_id': user_id,
            'status': 'in_progress',
            'start_time': datetime.utcnow().isoformat(),
        }
        return await self.db_manager.add_sync_log(sync_log_data)
        
    async def _update_sync_log(self, sync_log_id: int, success: bool, result: Dict[str, int] = None, error_message: str = None) -> None:
        """
        Обновляет запись о синхронизации в логе
        
        Args:
            sync_log_id: ID записи в логе
            success: Успешность синхронизации
            result: Результат синхронизации (опционально)
            error_message: Сообщение об ошибке (опционально)
        """
        update_data = {
            'status': 'completed' if success else 'failed',
            'end_time': datetime.utcnow().isoformat(),
        }
        
        if result:
            update_data['result'] = json.dumps(result)
            
        if error_message:
            update_data['error_message'] = error_message
            
        await self.db_manager.update_sync_log(sync_log_id, update_data)

    async def _process_contacts(self, user_id: int, google_contacts: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Обрабатывает контакты из Google и сохраняет их в БД
        
        Args:
            user_id: ID пользователя в БД
            google_contacts: Список контактов из Google
            
        Returns:
            Словарь с результатами обработки контактов
        """
        # Счетчики для результатов обработки
        result = {
            "total": len(google_contacts),
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }
        
        # Получаем существующие контакты пользователя из БД
        existing_contacts = await self.db_manager.get_contacts_by_user_id(user_id)
        
        # Создаем словарь для быстрого доступа к существующим контактам по google_id
        existing_by_google_id = {contact.google_id: contact for contact in existing_contacts if contact.google_id}
        
        # Обрабатываем каждый контакт из Google
        for contact_data in google_contacts:
            try:
                google_id = contact_data.get('resourceName') or contact_data.get('id')
                
                if not google_id:
                    logger.warning(f"Пропускаем контакт без ID: {contact_data}")
                    result["skipped"] += 1
                    continue
                
                # Извлекаем необходимую информацию из контакта
                contact_info = self._extract_contact_info(contact_data)
                
                # Проверяем, существует ли контакт в БД
                if google_id in existing_by_google_id:
                    # Обновляем существующий контакт
                    existing_contact = existing_by_google_id[google_id]
                    await self.db_manager.update_contact(existing_contact.id, contact_info)
                    result["updated"] += 1
                else:
                    # Добавляем новый контакт
                    contact_info['user_id'] = user_id
                    contact_info['google_id'] = google_id
                    await self.db_manager.add_contact(contact_info)
                    result["added"] += 1
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке контакта: {e}")
                result["failed"] += 1
        
        return result
    
    def _extract_contact_info(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлекает необходимую информацию из контакта Google
        
        Args:
            contact_data: Данные контакта из Google API
            
        Returns:
            Словарь с извлеченной информацией
        """
        # Инициализируем словарь для хранения извлеченной информации
        result = {
            'name': '',
            'email': None,
            'phone': None,
            'notes': None,
            'company': None,
            'position': None,
        }
        
        # Извлекаем имя контакта
        names = contact_data.get('names', [])
        if names and len(names) > 0:
            name_info = names[0]
            full_name = name_info.get('displayName')
            if full_name:
                result['name'] = full_name
        
        # Извлекаем email контакта
        emails = contact_data.get('emailAddresses', [])
        if emails and len(emails) > 0:
            email_info = emails[0]
            email = email_info.get('value')
            if email:
                result['email'] = email
        
        # Извлекаем телефон контакта
        phones = contact_data.get('phoneNumbers', [])
        if phones and len(phones) > 0:
            phone_info = phones[0]
            phone = phone_info.get('value')
            if phone:
                result['phone'] = phone
        
        # Извлекаем заметки контакта
        biographies = contact_data.get('biographies', [])
        if biographies and len(biographies) > 0:
            bio_info = biographies[0]
            notes = bio_info.get('value')
            if notes:
                result['notes'] = notes
        
        # Извлекаем компанию и должность контакта
        organizations = contact_data.get('organizations', [])
        if organizations and len(organizations) > 0:
            org_info = organizations[0]
            company = org_info.get('name')
            position = org_info.get('title')
            
            if company:
                result['company'] = company
            if position:
                result['position'] = position
        
        return result
