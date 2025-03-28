#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Обработчики команд Telegram бота
Содержит функции для обработки команд и взаимодействия с пользователем

Авторы: Сергей Дышкант, Андрианов Вячеслав
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
import re
from datetime import datetime

from telegram import Update, User, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from loguru import logger

from src.database.database import DatabaseManager
from src.sync.sync_manager import SyncManager
from src.api.google_contacts_adapter import GoogleContactsAdapter

# Обработчики основных команд

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                      user: User, welcome_message: str, db_manager: DatabaseManager) -> None:
    """Обработчик команды /start
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        user: Пользователь, отправивший команду
        welcome_message: Приветственное сообщение из конфигурации
        db_manager: Менеджер базы данных
    """
    # Проверяем, существует ли пользователь в базе
    user_exists = await db_manager.user_exists(user.id)
    
    # Формируем клавиатуру
    keyboard = [
        [InlineKeyboardButton("Синхронизировать с Google", callback_data="auth_google")],
        [InlineKeyboardButton("Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if user_exists:
        # Если пользователь уже существует
        await update.message.reply_html(
            f"С возвращением, {user.mention_html()}! 👋\n\n"
            f"Что бы вы хотели сделать сегодня?",
            reply_markup=reply_markup
        )
    else:
        # Если это новый пользователь
        await update.message.reply_html(
            f"Добро пожаловать, {user.mention_html()}! 👋\n\n"
            f"{welcome_message}\n\n"
            f"Для начала работы, авторизуйтесь в Google, чтобы синхронизировать контакты.",
            reply_markup=reply_markup
        )
        
        # Добавляем пользователя в базу данных
        await db_manager.add_user(user.id, user.username, user.first_name, user.last_name)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    help_text = (
        "*NetWorkGPT - ваш личный помощник по управлению контактами* 📇\n\n"
        "*Основные команды:*\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать справку по командам\n"
        "/sync - Синхронизировать контакты с Google\n"
        "/contact [имя] - Найти информацию о контакте\n"
        "/add_note [имя] [текст] - Добавить заметку к контакту\n"
        "/add_social [имя] [тип] [ссылка] - Добавить ссылку на соцсеть\n\n"
        
        "*Примеры использования:*\n"
        "`/contact Иван` - поиск контакта с именем Иван\n"
        "`/add_note Иван Встретились на конференции по AI` - добавляет заметку к контакту\n"
        "`/add_social Иван instagram https://instagram.com/ivan` - добавляет ссылку на Instagram"
    )
    
    keyboard = [
        [InlineKeyboardButton("Синхронизировать контакты", callback_data="sync")],
        [InlineKeyboardButton("Найти контакт", callback_data="search_contact")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_markdown(
        help_text,
        reply_markup=reply_markup
    )


async def handle_sync(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                     sync_manager: SyncManager, db_manager: DatabaseManager,
                     google_adapter: GoogleContactsAdapter) -> None:
    """Обработчик команды /sync - синхронизация контактов
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        sync_manager: Менеджер синхронизации данных
        db_manager: Менеджер базы данных
        google_adapter: Адаптер для работы с Google Contacts API
    """
    user_id = update.effective_user.id
    
    # Проверяем, авторизован ли пользователь в Google
    is_authorized = await db_manager.is_google_authorized(user_id)
    
    if not is_authorized:
        # Если пользователь не авторизован, предлагаем авторизоваться
        auth_url = await google_adapter.get_user_google_auth_url()
        
        keyboard = [
            [InlineKeyboardButton("Авторизоваться в Google", url=auth_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Для синхронизации контактов необходимо авторизоваться в Google.\n"
            "Нажмите кнопку ниже, чтобы начать процесс авторизации.",
            reply_markup=reply_markup
        )
        return
    
    # Отправляем сообщение о начале синхронизации
    progress_message = await update.message.reply_text("Начинаю синхронизацию контактов... ⏳")
    
    try:
        # Запускаем процесс синхронизации
        result = await google_adapter.sync_contacts_from_google(user_id)
        
        if result["success"]:
            # Обновляем сообщение с результатами
            stats = result["stats"]
            await progress_message.edit_text(
                f"✅ Синхронизация завершена!\n\n"
                f"📊 Статистика:\n"
                f"- Всего контактов: {stats['total']}\n"
                f"- Добавлено: {stats['added']}\n"
                f"- Обновлено: {stats['updated']}\n"
                f"- Пропущено: {stats['skipped']}\n"
                f"- Ошибок: {stats['failed']}"
            )
            
            # Предлагаем просмотреть контакты
            keyboard = [
                [InlineKeyboardButton("Просмотреть контакты", callback_data="list_contacts")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Теперь вы можете просмотреть свои контакты и управлять ими.",
                reply_markup=reply_markup
            )
        else:
            # Если синхронизация не удалась
            await progress_message.edit_text(
                f"❌ Произошла ошибка при синхронизации: {result['message']}"
            )
    except Exception as e:
        logger.error(f"Ошибка при синхронизации контактов: {e}")
        await progress_message.edit_text(
            f"❌ Произошла ошибка при синхронизации: {str(e)}"
        )


async def handle_auth_code(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         google_adapter: GoogleContactsAdapter) -> None:
    """
    Обработчик команды /auth_code - обработка кода авторизации Google
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        google_adapter: Адаптер для работы с Google Contacts API
    """
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Извлекаем код авторизации из сообщения
    try:
        # Формат команды: /auth_code XXXX
        auth_code = message_text.split("/auth_code", 1)[1].strip()
        
        if not auth_code:
            await update.message.reply_text(
                "Пожалуйста, укажите код авторизации после команды, например:\n"
                "`/auth_code ваш_код_авторизации`"
            )
            return
        
        # Отправляем сообщение о процессе авторизации
        progress_message = await update.message.reply_text("Выполняю авторизацию в Google... ⏳")
        
        # Авторизуем пользователя с полученным кодом
        result = await google_adapter.authorize_user(user_id, auth_code)
        
        if result["success"]:
            await progress_message.edit_text(
                "✅ Авторизация в Google успешно выполнена!\n\n"
                "Теперь вы можете синхронизировать контакты с помощью команды /sync"
            )
            
            # Предлагаем сразу выполнить синхронизацию
            keyboard = [
                [InlineKeyboardButton("Синхронизировать контакты", callback_data="sync_contacts")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Хотите выполнить синхронизацию контактов сейчас?",
                reply_markup=reply_markup
            )
        else:
            await progress_message.edit_text(
                f"❌ Ошибка авторизации: {result['message']}\n\n"
                "Пожалуйста, попробуйте получить новый код авторизации."
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке кода авторизации: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке кода авторизации.\n"
            "Пожалуйста, убедитесь, что вы правильно указали код.\n\n"
            "Формат команды: `/auth_code ваш_код_авторизации`"
        )


# Остальные обработчики будут добавлены в следующих файлах
# Из-за ограничений на размер файла генерации
