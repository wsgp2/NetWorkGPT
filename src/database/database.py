#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Менеджер базы данных для NetWorkGPT
Отвечает за создание соединения с базой данных и выполнение операций с данными

Авторы: Сергей Дышкант, Андрианов Вячеслав
"""

import json
from typing import Dict, Any, Optional, List, Union, Tuple
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import create_engine, and_, or_, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.future import select
from sqlalchemy.sql import text

from loguru import logger

from src.database.models import Base, User, Contact, SocialLink, Tag, Group, SyncLog


class DatabaseManager:
    """Менеджер базы данных для работы с моделями SQLAlchemy"""
    
    def __init__(self, db_url: str):
        """
        Инициализация менеджера базы данных
        
        Args:
            db_url: URL-строка подключения к базе данных
        """
        self.db_url = db_url
        
        # Преобразуем URL в асинхронный формат, если необходимо
        if not db_url.startswith('postgresql+asyncpg'):
            self.async_db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
        else:
            self.async_db_url = db_url
        
        # Создаем асинхронный движок SQLAlchemy
        self.engine = create_async_engine(self.async_db_url, echo=False)
        
        # Создаем фабрику сессий
        self.async_session = sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    
    async def initialize(self) -> None:
        """Инициализация базы данных - создание таблиц, если они не существуют"""
        async with self.engine.begin() as conn:
            # Создаем все таблицы из моделей
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("База данных инициализирована")
    
    async def get_session(self) -> AsyncSession:
        """Получение сессии для работы с базой данных"""
        return self.async_session()
    
    # Методы для работы с пользователями
    
    async def user_exists(self, telegram_id: int) -> bool:
        """Проверяет, существует ли пользователь с указанным Telegram ID
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            True, если пользователь существует, иначе False
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            return user is not None
    
    async def add_user(self, telegram_id: int, username: Optional[str], 
                     first_name: Optional[str], last_name: Optional[str]) -> User:
        """Добавляет нового пользователя в базу данных
        
        Args:
            telegram_id: ID пользователя в Telegram
            username: Имя пользователя в Telegram
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            
        Returns:
            Созданный объект пользователя
        """
        new_user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        async with self.async_session() as session:
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            
            logger.info(f"Добавлен новый пользователь: {telegram_id}, {username}")
            return new_user
    
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Получает пользователя по его Telegram ID
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Объект пользователя или None, если пользователь не найден
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalars().first()
    
    async def update_user(self, telegram_id: int, **kwargs) -> Optional[User]:
        """Обновляет информацию о пользователе
        
        Args:
            telegram_id: ID пользователя в Telegram
            **kwargs: Поля для обновления
            
        Returns:
            Обновленный объект пользователя или None, если пользователь не найден
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            
            if user:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                
                user.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(user)
                
                logger.info(f"Обновлена информация о пользователе: {telegram_id}")
                return user
            
            return None
    
    # Методы для работы с Google авторизацией
    
    async def is_google_authorized(self, telegram_id: int) -> bool:
        """Проверяет, авторизован ли пользователь в Google
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            True, если у пользователя есть действующий токен Google, иначе False
        """
        user = await self.get_user(telegram_id)
        if not user or not user.google_token or not user.token_expiry:
            return False
        
        # Проверяем срок действия токена
        return user.token_expiry > datetime.utcnow()
    
    async def update_google_tokens(self, telegram_id: int, access_token: str, refresh_token: Optional[str] = None, token_expiry: Optional[datetime] = None) -> User:
        """
        Обновляет токены Google для пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            access_token: Токен доступа Google
            refresh_token: Токен обновления Google (опционально)
            token_expiry: Срок действия токена (опционально)
            
        Returns:
            Обновленный объект пользователя
            
        Raises:
            Exception: Если пользователь не найден
        """
        async with self.async_session() as session:
            user = await self.get_user(telegram_id)
            if not user:
                raise Exception(f"Пользователь с Telegram ID {telegram_id} не найден")
            
            user.google_token = access_token
            
            if refresh_token:
                user.google_refresh_token = refresh_token
                
            if token_expiry:
                user.token_expiry = token_expiry
                
            await session.commit()
            await session.refresh(user)
            return user
    
    async def create_sync_log(self, user_id: int) -> SyncLog:
        """
        Создает новую запись в журнале синхронизации
        
        Args:
            user_id: ID пользователя в базе данных
            
        Returns:
            Созданный объект журнала синхронизации
        """
        async with self.async_session() as session:
            sync_log = SyncLog(user_id=user_id)
            session.add(sync_log)
            await session.commit()
            await session.refresh(sync_log)
            return sync_log
    
    async def update_sync_log(self, sync_log_id: int, end_time: datetime = None, 
                            success: bool = False, total_contacts: int = 0,
                            added_contacts: int = 0, updated_contacts: int = 0,
                            failed_contacts: int = 0, skipped_contacts: int = 0,
                            error_message: str = None) -> SyncLog:
        """
        Обновляет информацию о синхронизации
        
        Args:
            sync_log_id: ID записи журнала синхронизации
            end_time: Время завершения синхронизации
            success: Успешность синхронизации
            total_contacts: Общее количество контактов
            added_contacts: Количество добавленных контактов
            updated_contacts: Количество обновленных контактов
            failed_contacts: Количество контактов с ошибками
            skipped_contacts: Количество пропущенных контактов
            error_message: Сообщение об ошибке
            
        Returns:
            Обновленный объект журнала синхронизации
            
        Raises:
            Exception: Если запись журнала не найдена
        """
        async with self.async_session() as session:
            sync_log = await session.get(SyncLog, sync_log_id)
            if not sync_log:
                raise Exception(f"Запись синхронизации с ID {sync_log_id} не найдена")
            
            if end_time:
                sync_log.end_time = end_time
                
            sync_log.success = success
            sync_log.total_contacts = total_contacts
            sync_log.added_contacts = added_contacts
            sync_log.updated_contacts = updated_contacts
            sync_log.failed_contacts = failed_contacts
            sync_log.skipped_contacts = skipped_contacts
            
            if error_message:
                sync_log.error_message = error_message
                
            await session.commit()
            await session.refresh(sync_log)
            return sync_log
    
    async def get_contact_by_google_id(self, user_id: int, google_id: str) -> Optional[Contact]:
        """
        Получает контакт по ID в Google
        
        Args:
            user_id: ID пользователя в базе данных
            google_id: ID контакта в Google
            
        Returns:
            Объект контакта или None, если не найден
        """
        async with self.async_session() as session:
            query = select(Contact).where(
                and_(
                    Contact.user_id == user_id,
                    Contact.google_id == google_id
                )
            )
            result = await session.execute(query)
            return result.scalars().first()
    
    async def get_social_links(self, contact_id: int) -> List[SocialLink]:
        """
        Получает список социальных ссылок контакта
        
        Args:
            contact_id: ID контакта
            
        Returns:
            Список объектов социальных ссылок
        """
        async with self.async_session() as session:
            query = select(SocialLink).where(SocialLink.contact_id == contact_id)
            result = await session.execute(query)
            return result.scalars().all()
