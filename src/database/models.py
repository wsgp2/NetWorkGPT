#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Модели данных для базы данных NetWorkGPT
Определяет структуры данных для хранения информации о пользователях и контактах

Авторы: Сергей Дышкант, Андрианов Вячеслав
"""

from datetime import datetime
from typing import List, Dict, Optional, Any, Union

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Базовый класс для моделей SQLAlchemy
Base = declarative_base()

# Промежуточная таблица для связи между контактами и тегами (многие-ко-многим)
contact_tags = Table(
    'contact_tags',
    Base.metadata,
    Column('contact_id', Integer, ForeignKey('contacts.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

# Промежуточная таблица для связи между контактами и группами (многие-ко-многим)
contact_groups = Table(
    'contact_groups',
    Base.metadata,
    Column('contact_id', Integer, ForeignKey('contacts.id')),
    Column('group_id', Integer, ForeignKey('groups.id'))
)


class User(Base):
    """Модель для хранения информации о пользователях бота"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(64), nullable=True)
    last_name = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Токены авторизации для Google API
    google_token = Column(Text, nullable=True)
    google_refresh_token = Column(String(255), nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    
    # Настройки пользователя
    settings = Column(Text, nullable=True)  # JSON с настройками
    
    # Дата регистрации и последнего обновления
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи с другими таблицами
    contacts = relationship("Contact", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.telegram_id} ({self.username or 'No username'})>"


class Contact(Base):
    """Модель для хранения информации о контактах пользователя"""
    __tablename__ = 'contacts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Основная информация
    name = Column(String(128), nullable=False, index=True)
    phone = Column(String(64), nullable=True)
    email = Column(String(128), nullable=True)
    
    # Идентификаторы контакта во внешних системах
    google_id = Column(String(255), nullable=True, index=True)
    telegram_id = Column(Integer, nullable=True, index=True)
    
    # Дополнительная информация
    notes = Column(Text, nullable=True)  # Заметки о контакте
    meeting_place = Column(String(255), nullable=True)  # Где познакомились
    birthday = Column(DateTime, nullable=True)  # День рождения
    company = Column(String(128), nullable=True)  # Компания
    position = Column(String(128), nullable=True)  # Должность
    network_level = Column(Integer, default=0)  # Уровень нетворкинга (0-5)
    
    # Метаданные
    last_interaction = Column(DateTime, nullable=True)  # Последнее взаимодействие
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи с другими таблицами
    user = relationship("User", back_populates="contacts")
    social_links = relationship("SocialLink", back_populates="contact", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=contact_tags, back_populates="contacts")
    groups = relationship("Group", secondary=contact_groups, back_populates="contacts")
    
    def __repr__(self):
        return f"<Contact {self.id} - {self.name}>"


class SocialLink(Base):
    """Модель для хранения ссылок на социальные сети контакта"""
    __tablename__ = 'social_links'
    
    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=False)
    
    # Тип соцсети (instagram, facebook, linkedin и т.д.)
    platform = Column(String(64), nullable=False)
    
    # URL или идентификатор
    url = Column(String(255), nullable=False)
    username = Column(String(128), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с контактом
    contact = relationship("Contact", back_populates="social_links")
    
    def __repr__(self):
        return f"<SocialLink {self.platform} - {self.url}>"


class Tag(Base):
    """Модель для хранения тегов, которыми можно отмечать контакты"""
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True, index=True)
    color = Column(String(16), nullable=True)  # Цвет тега в HEX формате
    
    # Связь с контактами
    contacts = relationship("Contact", secondary=contact_tags, back_populates="tags")
    
    def __repr__(self):
        return f"<Tag {self.name}>"


class Group(Base):
    """Модель для хранения групп контактов"""
    __tablename__ = 'groups'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с контактами
    contacts = relationship("Contact", secondary=contact_groups, back_populates="groups")
    
    def __repr__(self):
        return f"<Group {self.name}>"


class SyncLog(Base):
    """Модель для хранения информации о синхронизациях"""
    __tablename__ = 'sync_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Информация о синхронизации
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    success = Column(Boolean, default=False)
    
    # Статистика
    total_contacts = Column(Integer, default=0)
    added_contacts = Column(Integer, default=0)
    updated_contacts = Column(Integer, default=0)
    failed_contacts = Column(Integer, default=0)
    skipped_contacts = Column(Integer, default=0)
    
    # Дополнительная информация
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<SyncLog {self.id} - {self.start_time} {'success' if self.success else 'failed'}>"
