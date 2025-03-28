#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Модуль для работы с Google Contacts API
Реализует функции для авторизации и получения контактов из Google

Авторы: Сергей Дышкант, Андрианов Вячеслав
"""

import os
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

import httpx
from loguru import logger


class GoogleContactsAPI:
    """Класс для работы с Google Contacts API через REST API"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация API клиента
        
        Args:
            config: Конфигурация приложения с параметрами для Google API
        """
        self.client_id = config['google_api']['client_id']
        self.client_secret = config['google_api']['client_secret']
        self.redirect_uri = config['google_api']['redirect_uri']
        self.scopes = config['google_api']['scopes']
        
        # URL для API запросов
        self.auth_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.contacts_url = "https://people.googleapis.com/v1/people/me/connections"
        
    def get_auth_url(self) -> str:
        """
        Формирует URL для авторизации пользователя в Google
        
        Returns:
            URL для авторизации
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "scope": " ".join(self.scopes)
        }
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        return auth_url
        
    async def get_tokens_from_code(self, auth_code: str) -> Dict[str, Any]:
        """
        Обменивает код авторизации на токены доступа
        
        Args:
            auth_code: Код авторизации, полученный после подтверждения пользователем
            
        Returns:
            Словарь с токенами доступа и их сроком действия
            
        Raises:
            Exception: При ошибке получения токенов
        """
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=params)
                response.raise_for_status()
                data = response.json()
                
                # Вычисляем время истечения токена
                expires_in = data.get("expires_in", 3600)  # По умолчанию 1 час
                expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                
                return {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", ""),  # Может отсутствовать, если пользователь уже авторизован
                    "expiry": expiry
                }
        
        except Exception as e:
            logger.error(f"Ошибка при получении токенов Google: {e}")
            raise Exception(f"Не удалось получить токены доступа: {e}")
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Обновляет токен доступа используя refresh token
        
        Args:
            refresh_token: Токен обновления
            
        Returns:
            Словарь с новым токеном доступа и сроком его действия
            
        Raises:
            Exception: При ошибке обновления токена
        """
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=params)
                response.raise_for_status()
                data = response.json()
                
                # Вычисляем время истечения токена
                expires_in = data.get("expires_in", 3600)  # По умолчанию 1 час
                expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                
                return {
                    "access_token": data["access_token"],
                    "expiry": expiry
                }
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении токена Google: {e}")
            raise Exception(f"Не удалось обновить токен доступа: {e}")
    
    async def get_contacts(self, access_token: str, refresh_token: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получает список контактов пользователя из Google Contacts
        
        Args:
            access_token: Токен доступа
            refresh_token: Токен обновления (опционально)
            
        Returns:
            Список контактов пользователя
            
        Raises:
            Exception: При ошибке получения контактов
        """
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        params = {
            "personFields": "names,emailAddresses,phoneNumbers,organizations,biographies,urls",
            "pageSize": 100  # Максимальный размер страницы
        }
        
        contacts = []
        next_page_token = None
        
        try:
            async with httpx.AsyncClient() as client:
                # Получаем контакты постранично
                while True:
                    if next_page_token:
                        params["pageToken"] = next_page_token
                    
                    response = await client.get(self.contacts_url, headers=headers, params=params)
                    
                    # Если токен истек, пробуем обновить его
                    if response.status_code == 401 and refresh_token:
                        tokens = await self.refresh_access_token(refresh_token)
                        headers["Authorization"] = f"Bearer {tokens['access_token']}"
                        response = await client.get(self.contacts_url, headers=headers, params=params)
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # Обрабатываем полученные контакты
                    connections = data.get("connections", [])
                    contacts.extend(self._process_contact_data(connection) for connection in connections)
                    
                    # Проверяем наличие следующей страницы
                    next_page_token = data.get("nextPageToken")
                    if not next_page_token:
                        break
                        
                return contacts
                
        except Exception as e:
            logger.error(f"Ошибка при получении контактов Google: {e}")
            raise Exception(f"Не удалось получить контакты: {e}")
    
    def _process_contact_data(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает данные контакта из Google API
        
        Args:
            contact_data: Данные контакта из Google API
            
        Returns:
            Обработанные данные контакта в удобном формате
        """
        result = {
            "google_id": contact_data.get("resourceName", "").replace("people/", ""),
            "name": "",
            "email": "",
            "phone": "",
            "company": "",
            "position": "",
            "notes": "",
            "social_links": []
        }
        
        # Обрабатываем имя
        names = contact_data.get("names", [])
        if names:
            primary_name = next((name for name in names if name.get("metadata", {}).get("primary", False)), names[0])
            result["name"] = primary_name.get("displayName", "")
        
        # Обрабатываем email
        emails = contact_data.get("emailAddresses", [])
        if emails:
            primary_email = next((email for email in emails if email.get("metadata", {}).get("primary", False)), emails[0])
            result["email"] = primary_email.get("value", "")
        
        # Обрабатываем телефон
        phones = contact_data.get("phoneNumbers", [])
        if phones:
            primary_phone = next((phone for phone in phones if phone.get("metadata", {}).get("primary", False)), phones[0])
            result["phone"] = primary_phone.get("value", "")
        
        # Обрабатываем организацию
        organizations = contact_data.get("organizations", [])
        if organizations:
            primary_org = next((org for org in organizations if org.get("metadata", {}).get("primary", False)), organizations[0])
            result["company"] = primary_org.get("name", "")
            result["position"] = primary_org.get("title", "")
        
        # Обрабатываем заметки
        biographies = contact_data.get("biographies", [])
        if biographies:
            primary_bio = next((bio for bio in biographies if bio.get("metadata", {}).get("primary", False)), biographies[0])
            result["notes"] = primary_bio.get("value", "")
        
        # Обрабатываем ссылки на соцсети
        urls = contact_data.get("urls", [])
        for url in urls:
            social_link = {
                "platform": url.get("type", "website"),
                "url": url.get("value", "")
            }
            result["social_links"].append(social_link)
        
        return result
