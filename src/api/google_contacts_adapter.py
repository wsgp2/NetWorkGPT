#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Адаптер для работы с Google Contacts API
Обеспечивает интеграцию между API Google и моделями базы данных

Авторы: Сергей Дышкант, Андрианов Вячеслав
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from loguru import logger

# Исправлены относительные импорты для корректного запуска бота
from src.api.google_api import GoogleContactsAPI
from src.database.database import DatabaseManager
from src.database.models import User, Contact, SocialLink


class GoogleContactsAdapter:
    """
    Класс-адаптер для интеграции Google Contacts API с базой данных.
    Обрабатывает авторизацию и синхронизацию контактов между системами.
    """
    
    def __init__(self, google_api: GoogleContactsAPI, db_manager: DatabaseManager):
        """
        Инициализация адаптера
        
        Args:
            google_api: Экземпляр GoogleContactsAPI для работы с API
            db_manager: Менеджер базы данных для сохранения информации
        """
        self.google_api = google_api
        self.db_manager = db_manager
    
    async def authorize_user(self, telegram_id: int, auth_code: str) -> Dict[str, Any]:
        """
        Авторизует пользователя в Google и сохраняет токены
        
        Args:
            telegram_id: Telegram ID пользователя
            auth_code: Код авторизации, полученный от Google
            
        Returns:
            Словарь с результатом авторизации
            
        Raises:
            Exception: При ошибке авторизации
        """
        try:
            # Получаем токены доступа
            tokens = await self.google_api.get_tokens_from_code(auth_code)
            
            # Получаем пользователя из базы данных
            user = await self.db_manager.get_user(telegram_id)
            if not user:
                raise Exception(f"Пользователь с Telegram ID {telegram_id} не найден")
            
            # Обновляем информацию о токенах
            await self.db_manager.update_google_tokens(
                telegram_id=telegram_id,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                token_expiry=tokens["expiry"]
            )
            
            return {
                "success": True,
                "message": "Авторизация в Google успешно выполнена"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при авторизации пользователя {telegram_id} в Google: {e}")
            return {
                "success": False,
                "message": f"Ошибка авторизации: {e}"
            }
    
    async def get_user_google_auth_url(self) -> str:
        """
        Получает URL для авторизации пользователя в Google
        
        Returns:
            URL для авторизации
        """
        return self.google_api.get_auth_url()
    
    async def sync_contacts_from_google(self, telegram_id: int) -> Dict[str, Any]:
        """
        Синхронизирует контакты из Google Contacts с базой данных
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Словарь с результатами синхронизации
            
        Raises:
            ValueError: Если пользователь не авторизован в Google
        """
        try:
            # Проверяем авторизацию пользователя в Google
            user = await self.db_manager.get_user_by_telegram_id(telegram_id)
            
            if not user or not user.google_token:
                logger.warning(f"Пользователь {telegram_id} не авторизован в Google")
                raise ValueError("Вы не авторизованы в Google. Пожалуйста, авторизуйтесь.")
            
            # Проверяем срок действия токена и обновляем его при необходимости
            now = datetime.utcnow()
            if user.token_expiry and user.token_expiry <= now and user.google_refresh_token:
                logger.info(f"Обновляем токен для пользователя {telegram_id}")
                tokens = await self.google_api.refresh_access_token(user.google_refresh_token)
                
                # Обновляем токены в базе данных
                update_data = {
                    "google_token": tokens["access_token"],
                    "token_expiry": datetime.utcnow().replace(microsecond=0) + \
                                    tokens.get("expires_in_timedelta", tokens.get("expires_in", 3600))
                }
                await self.db_manager.update_user(user.id, update_data)
                user.google_token = update_data["google_token"]
            
            # Создаем запись в журнале синхронизации
            sync_log = await self.db_manager.create_sync_log(user.id)
            
            # Получаем контакты из Google
            google_contacts = await self.google_api.get_contacts(user.google_token, user.google_refresh_token)
            
            # Обрабатываем контакты и сохраняем результаты в базе данных
            result = await self._process_contacts(user.id, google_contacts)
            
            # Обновляем статус синхронизации
            update_data = {
                "end_time": datetime.utcnow(),
                "success": True,
                "total_contacts": result["total"],
                "added_contacts": result["added"],
                "updated_contacts": result["updated"],
                "failed_contacts": result["failed"],
                "skipped_contacts": result["skipped"]
            }
            await self.db_manager.update_sync_log(sync_log.id, update_data)
            
            return {
                "success": True,
                "stats": result,
                "message": "Синхронизация контактов успешно выполнена"
            }
            
        except ValueError as e:
            logger.warning(f"Ошибка при синхронизации контактов: {e}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка при синхронизации контактов: {e}")
            
            # Обновляем статус синхронизации в случае ошибки
            if locals().get('sync_log'):
                update_data = {
                    "end_time": datetime.utcnow(),
                    "success": False,
                    "error_message": str(e)
                }
                await self.db_manager.update_sync_log(sync_log.id, update_data)
            
            return {
                "success": False,
                "stats": {
                    "total": 0,
                    "added": 0,
                    "updated": 0,
                    "failed": 0,
                    "skipped": 0
                },
                "message": f"Ошибка синхронизации: {str(e)}"
            }
    
    async def _create_contact(self, user_id: int, contact_data: Dict[str, Any]) -> Contact:
        """
        Создает новый контакт в базе данных на основе данных из Google
        
        Args:
            user_id: ID пользователя в базе данных
            contact_data: Данные контакта из Google Contacts
            
        Returns:
            Созданный объект контакта
        """
        # Создаем основную запись контакта
        contact = await self.db_manager.add_contact(
            user_id=user_id,
            name=contact_data["name"],
            email=contact_data["email"],
            phone=contact_data["phone"],
            google_id=contact_data["google_id"],
            company=contact_data["company"],
            position=contact_data["position"],
            notes=contact_data["notes"]
        )
        
        # Добавляем ссылки на социальные сети
        for social_link in contact_data["social_links"]:
            await self.db_manager.add_social_link(
                contact_id=contact.id,
                platform=social_link["platform"],
                url=social_link["url"]
            )
        
        return contact
    
    async def _update_contact(self, contact: Contact, contact_data: Dict[str, Any]) -> bool:
        """
        Обновляет существующий контакт данными из Google
        
        Args:
            contact: Объект контакта для обновления
            contact_data: Новые данные контакта из Google
            
        Returns:
            True если контакт был обновлен, False если изменений не было
        """
        # Проверяем, есть ли изменения в основных данных
        changes = {}
        if contact.name != contact_data["name"] and contact_data["name"]:
            changes["name"] = contact_data["name"]
        if contact.email != contact_data["email"] and contact_data["email"]:
            changes["email"] = contact_data["email"]
        if contact.phone != contact_data["phone"] and contact_data["phone"]:
            changes["phone"] = contact_data["phone"]
        if contact.company != contact_data["company"] and contact_data["company"]:
            changes["company"] = contact_data["company"]
        if contact.position != contact_data["position"] and contact_data["position"]:
            changes["position"] = contact_data["position"]
        if contact.notes != contact_data["notes"] and contact_data["notes"]:
            changes["notes"] = contact_data["notes"]
        
        # Обновляем контакт, если есть изменения
        if changes:
            await self.db_manager.update_contact(contact.id, **changes)
        
        # Обрабатываем социальные ссылки
        # Получаем текущие ссылки
        current_links = await self.db_manager.get_social_links(contact.id)
        current_urls = {link.url for link in current_links}
        
        # Добавляем новые ссылки
        for social_link in contact_data["social_links"]:
            if social_link["url"] not in current_urls:
                await self.db_manager.add_social_link(
                    contact_id=contact.id,
                    platform=social_link["platform"],
                    url=social_link["url"]
                )
                changes["social_links"] = True
        
        return bool(changes)
    
    async def _process_contacts(self, user_id: int, google_contacts: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Обрабатывает контакты из Google и сохраняет результаты в базе данных
        
        Args:
            user_id: ID пользователя в базе данных
            google_contacts: Список контактов из Google Contacts
            
        Returns:
            Словарь с результатами обработки контактов
        """
        # Статистика обработки контактов
        stats = {
            "total": len(google_contacts),
            "added": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0
        }
        
        # Обрабатываем каждый контакт
        for contact_data in google_contacts:
            try:
                # Ищем контакт в базе данных по Google ID
                existing_contact = await self.db_manager.get_contact_by_google_id(user_id, contact_data["google_id"])
                
                if existing_contact:
                    # Обновляем существующий контакт
                    updated = await self._update_contact(existing_contact, contact_data)
                    if updated:
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    # Создаем новый контакт
                    await self._create_contact(user_id, contact_data)
                    stats["added"] += 1
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке контакта: {e}")
                stats["failed"] += 1
        
        return stats
