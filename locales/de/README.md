<div align="center">

# ⚡ Prime Gate Antigravity Proxy
### `prime-gate-proxy-antigravity-lik`

**Ein produktionsreifer, selbst gehosteter OpenAI-kompatibler Proxy-Gateway für Google Antigravity.**

[![Version](https://img.shields.io/badge/version-1.0.0--beta-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Sprache auswählen / Select Language

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 Übersicht

**Prime Gate** ist eine schlanke und robuste API-Bridge, die den internen Cloud AI Companion / Antigravity-Dienst von Google in eine **100% OpenAI-konforme REST- & SSE-API** (`/v1/models`, `/v1/chat/completions`) kapselt.

Nutzen Sie Ihre Google Antigravity-Kontingente – darunter **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)** und **Gemini 3.8 Flash** – direkt in Ihren bevorzugten AI-Entwicklungswerkzeugen wie **OpenCode**, **Cursor**, **Continue.dev**, **Aider**, **Cline** und **SillyTavern**.

---

## 🌟 Hauptfunktionen

1. **100% OpenAI-Spezifikationskonform:**
   Nahtloser Drop-in-Ersatz für Standard-OpenAI-Clients.
2. **Echtzeit-Denkprozess-Streaming (Thinking Mode):**
   Liefert Reasoning-Chunks via `choices[0].delta.reasoning_content` in Echtzeit.
3. **Keine 400 Bad Request Fehler (Schema Sanitizer):**
   Bereinigt automatisch nicht unterstützte JSON-Schema-Einschränkungen (`exclusiveMinimum`, `$schema`, `additionalProperties`) für stabile Tool Calls.
4. **Automatische Kontingent- und Tariferkennung:**
   Erkennt **`Google AI Pro (Trial / Jio 18M Promo)`** vs **`Paid`** und listet nur verfügbare Modelle auf.
5. **Modernes Web-Dashboard:**
   Reaktionsschnelles Glassmorphic UI auf Node.js-Basis (`http://127.0.0.1:52110`) mit Live-Radar und Test-Sandbox.
6. **Leistungsstarke CLI:**
   Befehle wie `--version`, `quota`, `auth` und Hintergrund-Daemon-Verwaltung für Windows.

---

## ⚡ Schnellstart

```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt

# Account aus OpenCode importieren
python -m prime_gate.cli auth import

# Kontingente prüfen
python -m prime_gate.cli quota

# Im Hintergrund starten (Windows)
scripts\start-all.bat
```
*Web-Dashboard öffnen: `http://127.0.0.1:52110`*

---

## 📜 Lizenz & Autor

- **Autor:** [Irham Karaman](https://github.com/irhamkaraman)
- **Lizenz:** [MIT License](../../LICENSE)
