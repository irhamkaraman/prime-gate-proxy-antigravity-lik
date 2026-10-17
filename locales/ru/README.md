<div align="center">

# ⚡ Prime Gate Antigravity Прокси
### `prime-gate-proxy-antigravity-lik`

**Высокопроизводительный self-hosted прокси-шлюз для Google Antigravity с поддержкой протокола OpenAI.**

[![Version](https://img.shields.io/badge/version-1.0.0--beta-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Выбор языка / Select Language

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 Обзор проекта

**Prime Gate** — это легковесный и надежный шлюз, который оборачивает внутренний API Google Cloud AI Companion / Antigravity в **полноценный OpenAI-совместимый REST & SSE API** (`/v1/models`, `/v1/chat/completions`).

Позволяет использовать ваши квоты Google Antigravity (включая **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)** и **Gemini 3.8 Flash**) в любых средах разработки: **OpenCode**, **Cursor**, **Continue.dev**, **Aider**, **Cline** и **SillyTavern**.

---

## 🌟 Ключевые возможности

1. **100% Совместимость с OpenAI API:**
   Прямая замена стандартного OpenAI endpoint без изменения настроек клиента.
2. **Потоковая передача рассуждений (Thinking Mode):**
   Передает чанки рассуждений через `choices[0].delta.reasoning_content` в реальном времени.
3. **Защита от ошибки 400 Bad Request:**
   Рекурсивный валидатор автоматически очищает неподдерживаемые ограничения JSON Schema (`exclusiveMinimum`, `exclusiveMaximum`, `$schema`, `additionalProperties`).
4. **Интеллектуальное распознавание тарифа и квот:**
   Автоматически определяет тариф **`Google AI Pro (Trial Tier)`** или **`Paid Tier`** и фильтрует доступные модели.
5. **Современный Glassmorphic Web UI:**
   Панель управления на Node.js без внешних зависимостей (`http://127.0.0.1:52110`) с графиками квот и интерактивной песочницей.
6. **Полнофункциональный CLI:**
   Поддержка команд `--version`, `quota`, `auth`, а также запуск службы в фоновом режиме (daemon) на Windows.

---

## ⚡ Быстрый старт

### 1. Клонирование и установка
```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt
```
*(Пользователи Windows могут дважды кликнуть `scripts\install.bat`)*

### 2. Подключение учетной записи
```bash
# Авто-импорт из OpenCode
python -m prime_gate.cli auth import

# Или вход через браузер (OAuth 2.0 PKCE)
python -m prime_gate.cli auth login
```

### 3. Проверка квоты
```bash
python -m prime_gate.cli quota
```

### 4. Запуск прокси и Web UI
```bash
# Запуск в фоновом режиме (Windows)
scripts\start-all.bat
```
*Web-интерфейс доступен по адресу: `http://127.0.0.1:52110`.*

---

## 📜 Лицензия и автор

- **Автор:** [Irham Karaman](https://github.com/irhamkaraman)
- **Лицензия:** [MIT License](../../LICENSE)
