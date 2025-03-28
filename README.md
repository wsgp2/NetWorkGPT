# 🌐 NetWorkGPT

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Интеллектуальная система управления контактами, объединяющая Telegram и Google Contacts с AI-аналитикой

## 📊 О проекте

NetWorkGPT решает проблему эффективного управления деловыми контактами для предпринимателей и активных нетворкеров. Приложение синхронизирует контакты из Telegram с Google Contacts, предоставляя богатый набор функций для управления сетью контактов и аналитики социальных взаимодействий.

### 🎯 Ключевые возможности

- **Автоматическая синхронизация** контактов между Telegram и Google Contacts
- **Обогащение профилей** дополнительной информацией: заметки, соцсети, теги
- **AI-анализ коммуникаций** для автоматического создания саммари и выявления ключевых моментов
- **Удобный доступ к данным** через Telegram-бота в один клик
- **Мониторинг активности** контактов в социальных сетях
- **Интеллектуальные напоминания** о важных событиях и договоренностях

## 🖥️ Техническая реализация

### Архитектура

```
NetWorkGPT/
├── src/                       # Исходный код
│   ├── bot/                   # Telegram бот
│   ├── api/                   # Интеграции с Telegram API и Google API
│   ├── sync/                  # Система синхронизации
│   ├── database/              # Работа с базой данных
│   ├── ai/                    # AI компоненты и аналитика
├── configs/                   # Конфигурационные файлы
├── docs/                      # Документация
└── tests/                     # Тесты
```

### Технологический стек

- **Язык программирования**: Python 3.9+
- **Telegram API**: python-telegram-bot, Telethon
- **Google API**: Google People API (контакты)
- **База данных**: PostgreSQL
- **AI и NLP**: OpenAI API, spaCy, NLTK
- **Контейнеризация**: Docker
- **CI/CD**: GitHub Actions

## ⚙️ Установка и настройка

### Предварительные требования

- Python 3.9 или выше
- Pip (менеджер пакетов Python)
- PostgreSQL
- Доступ к Telegram API (Bot Token)
- Доступ к Google API (OAuth2 credentials)

### Установка

1. Клонируйте репозиторий:

```bash
git clone https://github.com/yourusername/networkgpt.git
cd networkgpt
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Настройте конфигурацию:

```bash
cp configs/config.example.yaml configs/config.yaml
# Отредактируйте configs/config.yaml, внеся свои API ключи и настройки
```

4. Запустите приложение:

```bash
python src/main.py
```

## 🚀 Дорожная карта развития

### Phase 1: MVP (Q2 2025)
- [x] Базовая архитектура и интеграции
- [x] Telegram бот с основными командами
- [x] Синхронизация контактов Telegram → Google
- [x] Добавление заметок к контактам
- [ ] Система поиска информации о контактах

### Phase 2: AI Enhancement (Q3 2025)
- [ ] AI-анализ диалогов
- [ ] Автоматическое создание саммари коммуникаций
- [ ] Отслеживание активности в социальных сетях
- [ ] Рекомендательная система для нетворкинга

### Phase 3: Enterprise (Q4 2025)
- [ ] Интеграция с популярными CRM
- [ ] Командная работа с контактами
- [ ] Расширенная аналитика и метрики
- [ ] API для сторонних разработчиков

## 👥 Команда

- **Сергей Дышкант** - Разработчик [@sergei_dyshkant](https://t.me/sergei_dyshkant)
- **Андрианов Вячеслав** - Инициатор проекта [@viacheslav_andrianov](https://t.me/viacheslav_andrianov)

## 📮 Контакты

Для вопросов и предложений: [email@example.com](mailto:email@example.com)

## 📝 Лицензия

Проект распространяется под лицензией MIT. Подробности в файле [LICENSE](LICENSE).
