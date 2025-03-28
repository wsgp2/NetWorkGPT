#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Основной модуль Telegram бота для NetWorkGPT
Отвечает за взаимодействие с пользователями и обработку команд

Авторы: Сергей Дышкант, Андрианов Вячеслав
"""

import asyncio
from typing import Dict, Any, Optional, List
import logging

from telegram import Update, Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import filters, ContextTypes

from loguru import logger

from src.database.database import DatabaseManager
from src.sync.sync_manager import SyncManager
from src.bot import handlers
from src.utils.config import load_config
from src.api.google_api import GoogleContactsAPI
from src.api.google_contacts_adapter import GoogleContactsAdapter


class TelegramBot:
    """Класс для управления Telegram ботом и обработки команд"""

    def __init__(self, config: Dict[str, Any], db_manager: DatabaseManager, sync_manager: SyncManager):
        """Инициализация бота

        Args:
            config: Конфигурация приложения
            db_manager: Менеджер базы данных
            sync_manager: Менеджер синхронизации
        """
        self.config = config
        self.db_manager = db_manager
        self.sync_manager = sync_manager
        self.token = config['api_keys']['telegram_token']
        self.welcome_message = config['bot']['welcome_message']
        self.admin_ids = set(config['bot']['admin_ids'])
        self.application = None
        self.is_running = False
        
        # Создаем экземпляр Google API и адаптера
        self.google_api = GoogleContactsAPI(config)
        self.google_adapter = GoogleContactsAdapter(self.google_api, db_manager)

    async def start(self) -> None:
        """Запуск бота и регистрация обработчиков команд"""
        try:
            # Создаем экземпляр приложения
            self.application = Application.builder().token(self.token).build()
            
            # Регистрируем обработчики команд
            self._register_handlers()
            
            # Запускаем бота
            logger.info("Запуск Telegram бота...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            self.is_running = True
            logger.info("Telegram бот успешно запущен!")
            
            # Блокируем завершение программы
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
        except Exception as e:
            logger.exception(f"Ошибка при запуске Telegram бота: {e}")
            raise

    def _register_handlers(self) -> None:
        """Регистрирует все обработчики команд и сообщений"""
        # Основные команды
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        
        # Команды для работы с контактами
        self.application.add_handler(CommandHandler("sync", self._handle_sync))
        self.application.add_handler(CommandHandler("contact", self._handle_contact))
        self.application.add_handler(CommandHandler("add_note", self._handle_add_note))
        self.application.add_handler(CommandHandler("add_social", self._handle_add_social))
        self.application.add_handler(CommandHandler("auth_code", self._handle_auth_code))
        
        # Обработка кнопок
        self.application.add_handler(CallbackQueryHandler(self._handle_button))
        
        # Обработка текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        
        # Обработка ошибок
        self.application.add_error_handler(self._handle_error)
    
    # Основные обработчики команд
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start - приветствие и начало работы"""
        user = update.effective_user
        await handlers.handle_start(update, context, user, self.welcome_message, self.db_manager)
    
    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help - справка по командам"""
        await handlers.handle_help(update, context)
    
    async def _handle_sync(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /sync - синхронизация контактов"""
        await handlers.handle_sync(update, context, self.sync_manager, self.db_manager, self.google_adapter)
    
    async def _handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /contact - поиск информации о контакте"""
        await handlers.handle_contact(update, context, self.db_manager)
    
    async def _handle_add_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /add_note - добавление заметки к контакту"""
        await handlers.handle_add_note(update, context, self.db_manager, self.sync_manager)
    
    async def _handle_add_social(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /add_social - добавление ссылки на соцсеть"""
        await handlers.handle_add_social(update, context, self.db_manager, self.sync_manager)
    
    async def _handle_auth_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /auth_code - авторизация Google"""
        await handlers.handle_auth_code(update, context, self.google_adapter)
    
    async def _handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на инлайн-кнопки"""
        query = update.callback_query
        query_data = query.data
        
        # Обрабатываем кнопку синхронизации
        if query_data == "sync_contacts":
            # Отправляем команду /sync для обработки
            await query.answer("Запускаем синхронизацию...")
            await self._handle_sync(update, context)
        else:
            # Передаем обработку другим кнопкам
            await handlers.handle_button(query, context, self.db_manager, self.sync_manager, self.google_adapter)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик текстовых сообщений"""
        await handlers.handle_message(update, context, self.db_manager)
    
    async def _handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        logger.error(f"Произошла ошибка: {context.error} в запросе {update}")
        
        # Отправляем сообщение об ошибке пользователю
        if update and update.effective_chat:
            await update.effective_chat.send_message(
                "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз или свяжитесь с администратором."
            )
            
            # Отправляем уведомление администраторам 
            if self.admin_ids:
                for admin_id in self.admin_ids:
                    try:
                        user_info = f"ID: {update.effective_user.id}, Username: @{update.effective_user.username}"
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"ОШИБКА В БОТЕ:\n{context.error}\n\nПользователь: {user_info}\nЗапрос: {update.message and update.message.text}"
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
