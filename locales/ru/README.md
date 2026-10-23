<div align="center">

# ⚡ Prime Gate Antigravity Прокси
### `prime-gate-proxy-antigravity-lik`

**Высокопроизводительный self-hosted двухпротокольный прокси-шлюз для Google Antigravity с поддержкой протоколов OpenAI и Anthropic.**

[![NPM Version](https://img.shields.io/npm/v/prime-gate-antigravity.svg?style=for-the-badge&logo=npm&color=CB3837)](https://www.npmjs.com/package/prime-gate-antigravity)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependencies)
[![Dependents](https://img.shields.io/badge/dependents-0-blue.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Выбор языка / Select Language

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 Обзор проекта

**Prime Gate** — это легковесный и надежный двухпротокольный шлюз корпоративного уровня, который оборачивает внутренний API Google Cloud AI Companion / Antigravity в **OpenAI-совместимый** (`/v1/chat/completions`) и **нативный Anthropic Messages API** (`/v1/messages`) REST & SSE интерфейс.

Позволяет использовать ваши квоты Google Antigravity (включая **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)** и **Gemini 3.8 Flash**) в любых средах разработки: **Claude Code CLI**, **Cline**, **Roo Code**, **OpenCode**, **Cursor**, **Continue.dev**, **Aider** и **SillyTavern**.

---

## 🌟 Ключевые возможности

1. **Двухпротокольная поддержка (OpenAI и нативный Anthropic):**
   Полная совместимость со спецификациями OpenAI и Anthropic (`/v1/messages`), обеспечивающая прямую интеграцию с Claude Code CLI.
2. **Многоязычный семантический векторный кэш (Semantic Cache):**
   Локальный векторный поиск FastEmbed ONNX с сохранением в SQLite WAL (~12мс TTFT).
3. **Корпоративная безопасность (AES-256-GCM):**
   Аппаратная изоляция ключей в OS Keyring, шифрование локальных данных AES-256-GCM и гранулярные политики Client API Key (RPM / TPD).
4. **Потоковая передача рассуждений (Thinking Mode):**
   Передает чанки рассуждений через `choices[0].delta.reasoning_content` в реальном времени.
3. **Защита от ошибки 400 Bad Request:**
   Рекурсивный валидатор автоматически очищает неподдерживаемые ограничения JSON Schema (`exclusiveMinimum`, `exclusiveMaximum`, `$schema`, `additionalProperties`).
4. **Интеллектуальное распознавание тарифа и квот:**
   Автоматически определяет тариф **`Google AI Pro (Trial Tier)`** или **`Paid Tier`** и фильтрует доступные модели.
5. **Современный React 18 + TypeScript SPA интерфейс:**
   Полнофункциональная панель управления на базе Vite с маршрутизацией (`/dashboard`, `/benchmarks`, `/accounts`, `/sandbox`, `/sentinel`), живыми графиками токенов, управлением квотами и интерактивной песочницей.
6. **Полнофункциональный CLI:**
   Поддержка команд `--version`, `quota`, `auth`, а также запуск службы в фоновом режиме (daemon) на Windows.

---

## 📸 Галерея интерфейса веб-панели

👉 **[Смотреть полную галерею скриншотов высокого разрешения](../../docs/SCREENSHOTS.md)**

---

## ⚡ Быстрый старт

### 1. Мгновенный запуск через NPX (Без необходимости Git Clone)
```bash
# Фоновый запуск демона (API :52111 + Web UI :52110)
npx prime-gate-antigravity daemon start

# Просмотр квот
npx prime-gate-antigravity quota
```

### 2. Глобальная установка через NPM (Рекомендуется)
```bash
npm install -g prime-gate-antigravity
prime-gate daemon start
```

### 3. Онбординг через Web UI и подключение аккаунта
1. Откройте браузер по адресу **`http://127.0.0.1:52110`**.
2. Если учетная запись еще не подключена, откроется окно онбординга:
   - Нажмите **"Sign in with Google"** для авторизации через Google OAuth 2.0 PKCE.
   - Или нажмите **"⚡ Quick Import from OpenCode Config"** для быстрого импорта из OpenCode.
3. После авторизации откроется **главная панель управления** с радаром квот и эндпоинтом OpenAI (`http://127.0.0.1:52111/v1`).

> 💡 **Альтернатива через терминал:**
> ```bash
> python -m prime_gate.cli auth login   # Авторизация через браузер
> python -m prime_gate.cli auth import  # Импорт из OpenCode
> python -m prime_gate.cli quota        # Просмотр статуса квот
> ```

---

## 📜 Лицензия и автор

- **Автор:** [Irham Karaman](https://github.com/irhamkaraman)
- **Лицензия:** [MIT License](../../LICENSE)
