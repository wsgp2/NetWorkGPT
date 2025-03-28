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

from telegram import Update, User, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from loguru import logger

# Исправленные импорты на абсолютные
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
        try:
            await update.message.reply_html(
                f"С возвращением, {user.mention_html()}! 👋\n\n"
                f"Что бы вы хотели сделать сегодня?",
                reply_markup=reply_markup
            )
            # Обновляем информацию о пользователе, если она изменилась
            await db_manager.update_user(
                user.id, 
                username=user.username, 
                first_name=user.first_name, 
                last_name=user.last_name
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке существующего пользователя: {e}")
            await update.message.reply_text(
                "Извините, произошла ошибка при обработке вашего запроса.\n"
                "Пожалуйста, попробуйте еще раз или свяжитесь с администратором."
            )
    else:
        # Если это новый пользователь
        try:
            # Сначала добавляем пользователя в базу данных
            user_data = await db_manager.add_user(user.id, user.username, user.first_name, user.last_name)
            
            if not user_data:
                raise ValueError("Не удалось добавить пользователя в базу данных")
            
            # Затем отправляем приветственное сообщение
            await update.message.reply_html(
                f"Добро пожаловать, {user.mention_html()}! 👋\n\n"
                f"{welcome_message}\n\n"
                f"Для начала работы, авторизуйтесь в Google, чтобы синхронизировать контакты.",
                reply_markup=reply_markup
            )
            
            # Отправляем уведомление администратору о новом пользователе
            try:
                admin_chat_id = 531712920  # ID чата @sergei_dyshkant
                admin_message = (
                    f"Новый пользователь в NetWorkGPT!\n\n"
                    f"Имя: {user.first_name or '-'} {user.last_name or ''}\n"
                    f"Username: @{user.username or '-'}\n"
                    f"Telegram ID: {user.id}\n"
                    f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                )
                
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=admin_message
                )
                logger.info(f"Отправлено уведомление администратору о новом пользователе: {user.id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления администратору: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении нового пользователя: {e}")
            await update.message.reply_text(
                "Извините, произошла ошибка при регистрации.\n"
                "Пожалуйста, попробуйте еще раз или свяжитесь с администратором."
            )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    help_text = (
        "📱 NetWorkGPT - ваш помощник для управления контактами.\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/sync - Синхронизировать контакты с Google\n"
        "/contact [имя] - Поиск информации о контакте\n"
        "/add_note [имя] [текст] - Добавить заметку к контакту\n"
        "/add_social [имя] [тип] [ссылка] - Добавить ссылку на соцсеть\n"
        "/auth_code [код] - Ввести код авторизации Google\n\n"
        "Для начала работы, синхронизируйте ваши контакты с Google."
    )
    
    # Формируем кнопки
    keyboard = [
        [InlineKeyboardButton("Синхронизировать с Google", callback_data="auth_google")],
        [InlineKeyboardButton("О проекте", callback_data="about")]
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


async def handle_button(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, 
                       db_manager: DatabaseManager, google_adapter: GoogleContactsAdapter = None, 
                       sync_manager: SyncManager = None) -> None:
    """Обработчик нажатий на инлайн-кнопки
    
    Args:
        query: Объект запроса обратного вызова
        context: Контекст бота
        db_manager: Менеджер базы данных
        google_adapter: Адаптер для работы с Google Contacts API
        sync_manager: Менеджер синхронизации
    """
    # Получаем данные из кнопки
    data = query.data
    user = query.from_user
    
    try:
        # Обрабатываем разные типы кнопок
        if data == "help":
            # Отвечаем на нажатие кнопки
            await query.answer("Открываю справку...")
            
            # Формируем сообщение справки
            help_text = (
                "📱 NetWorkGPT - ваш помощник для управления контактами.\n\n"
                "Доступные команды:\n"
                "/start - Начать работу с ботом\n"
                "/help - Показать эту справку\n"
                "/sync - Синхронизировать контакты с Google\n"
                "/contact [имя] - Поиск информации о контакте\n"
                "/add_note [имя] [текст] - Добавить заметку к контакту\n"
                "/add_social [имя] [тип] [ссылка] - Добавить ссылку на соцсеть\n"
                "/auth_code [код] - Ввести код авторизации Google\n\n"
                "Для начала работы, синхронизируйте ваши контакты с Google."
            )
            
            # Формируем кнопки
            keyboard = [
                [InlineKeyboardButton("Синхронизировать с Google", callback_data="auth_google")],
                [InlineKeyboardButton("О проекте", callback_data="about")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Редактируем исходное сообщение
            await query.edit_message_text(
                text=help_text,
                reply_markup=reply_markup
            )
            
        elif data == "auth_google":
            # Отвечаем на нажатие кнопки
            await query.answer("Начинаем авторизацию в Google...")
            
            if not google_adapter:
                logger.error("Google адаптер не инициализирован")
                await query.message.reply_text(
                    "Извините, произошла ошибка при настройке Google API.\n"
                    "Пожалуйста, попробуйте позже или свяжитесь с администратором."
                )
                return
            
            # Проверяем, авторизован ли пользователь
            is_authorized = await db_manager.is_google_authorized(user.id)
            
            if is_authorized:
                # Если пользователь уже авторизован, предлагаем синхронизацию
                await query.message.reply_text(
                    "Вы уже авторизованы в Google.\n"
                    "Хотите начать синхронизацию контактов?",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Синхронизировать", callback_data="sync_contacts")]
                    ])
                )
            else:
                # Если пользователь не авторизован, отправляем ссылку для авторизации
                auth_url = google_adapter.google_api.get_auth_url()
                
                await query.message.reply_text(
                    "Для синхронизации контактов, необходимо авторизоваться в Google.\n\n"
                    "1. Перейдите по ссылке ниже\n"
                    "2. Войдите в свой аккаунт Google и разрешите доступ\n"
                    "3. Скопируйте полученный код авторизации\n"
                    "4. Отправьте код боту с командой /auth_code [ваш_код]\n\n"
                    f"[Авторизоваться в Google]({auth_url})",
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
        
        elif data == "about":
            # Отвечаем на нажатие кнопки
            await query.answer("Информация о проекте")
            
            about_text = (
                "🤖 NetWorkGPT\n\n"
                "Умный бот для управления контактами с интеграцией Google Contacts "
                "и аналитикой на базе ИИ.\n\n"
                "📊 Возможности:\n"
                "• Синхронизация контактов с Google\n"
                "• Умный поиск по контактам\n"
                "• Добавление заметок и связей\n"
                "• Аналитика вашей сети контактов\n\n"
                "👨‍💻 Разработчики: Сергей Дышкант, Андрианов Вячеслав\n"
                "🌐 Версия: 1.0"
            )
            
            await query.edit_message_text(
                text=about_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Назад", callback_data="help")]
                ])
            )
        
        else:
            # Если кнопка не распознана
            await query.answer("Неизвестная команда")
            logger.warning(f"Получена неизвестная команда кнопки: {data}")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке нажатия кнопки: {e}")
        await query.answer("Произошла ошибка при обработке запроса")
        
        # Уведомляем пользователя об ошибке
        try:
            await query.message.reply_text(
                "Извините, произошла ошибка при обработке вашего запроса.\n"
                "Пожалуйста, попробуйте еще раз или свяжитесь с администратором."
            )
        except Exception:
            pass  # Игнорируем ошибки при отправке сообщения об ошибке


# Обработчики новых команд

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db_manager: DatabaseManager) -> None:
    """
    Обработчик текстовых сообщений
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        db_manager: Менеджер базы данных
    """
    user = update.effective_user
    message_text = update.message.text.strip()
    logger.info(f"Получено текстовое сообщение от {user.id}: {message_text}")
    
    # Проверяем, является ли сообщение кодом авторизации Google OAuth
    if message_text.startswith('4/') and '/' in message_text and len(message_text) > 20:
        # Это код авторизации Google
        await update.message.reply_text(
            f"Я получил код авторизации Google. Пожалуйста, используйте команду /auth_code, чтобы ввести код: \n`{message_text[:10]}...`"
        )
        context.user_data['auth_code'] = message_text
    else:
        # Другое текстовое сообщение
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я пока не могу обработать ваше сообщение. Используйте команды /help для получения списка доступных команд.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Помощь", callback_data="help")]
            ])
        )

async def handle_auth_code(update: Update, context: ContextTypes.DEFAULT_TYPE, sync_manager: SyncManager) -> None:
    """
    Обработчик команды /auth_code - обработка кода авторизации Google
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        sync_manager: Менеджер синхронизации
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.id} запросил обработку кода авторизации")
    
    # Проверяем, есть ли в контексте сохраненный код авторизации
    auth_code = context.user_data.get('auth_code')
    
    if not auth_code:
        # Нет сохраненного кода авторизации
        await update.message.reply_text(
            "Пожалуйста, введите код авторизации после команды, например:\n"
            "`/auth_code ваш_код_авторизации`"
        )
        return
    
    try:
        # Обрабатываем код авторизации
        await update.message.reply_text("Выполняю авторизацию в Google...")
        # Здесь должна быть реализована логика авторизации с помощью кода
        # result = await sync_manager.exchange_auth_code(auth_code, user.id)
        
        # Временный ответ, пока функция не реализована
        await update.message.reply_text(
            f"Код авторизации принят! {auth_code[:10]}..."
        )
        # Очищаем сохраненный код авторизации
        del context.user_data['auth_code']
    except Exception as e:
        logger.error(f"Ошибка при обработке кода авторизации: {e}")
        await update.message.reply_text(
            f"Произошла ошибка при обработке кода авторизации: {str(e)}"
        )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE, db_manager: DatabaseManager):
    """
    Обработчик команды /contact - управление контактами
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        db_manager: Менеджер базы данных
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.id} запросил управление контактами")
    
    # Временный ответ, пока функция не реализована
    await update.message.reply_text(
        f"Привет, {user.first_name}! Команда /contact пока в разработке.\n\n"
        "Здесь будет реализовано управление контактами.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Помощь", callback_data="help")]
        ])
    )

async def handle_add_note(update: Update, context: ContextTypes.DEFAULT_TYPE, db_manager: DatabaseManager, sync_manager: SyncManager):
    """
    Обработчик команды /add_note - добавление заметки к контакту
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        db_manager: Менеджер базы данных
        sync_manager: Менеджер синхронизации
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.id} запросил добавление заметки")
    
    # Временный ответ, пока функция не реализована
    await update.message.reply_text(
        f"Привет, {user.first_name}! Команда /add_note пока в разработке.\n\n"
        "Здесь будет реализовано добавление заметок к контактам.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Помощь", callback_data="help")]
        ])
    )

async def handle_add_social(update: Update, context: ContextTypes.DEFAULT_TYPE, db_manager: DatabaseManager, sync_manager: SyncManager):
    """
    Обработчик команды /add_social - добавление ссылки на соцсеть
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        db_manager: Менеджер базы данных
        sync_manager: Менеджер синхронизации
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.id} запросил добавление ссылки на соцсеть")
    
    # Временный ответ, пока функция не реализована
    await update.message.reply_text(
        f"Привет, {user.first_name}! Команда /add_social пока в разработке.\n\n"
        "Здесь будет реализовано добавление ссылок на соцсети.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Помощь", callback_data="help")]
        ])
    )


# Остальные обработчики будут добавлены в следующих файлах
# Из-за ограничений на размер файла генерации
