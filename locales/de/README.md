<div align="center">

# ⚡ Prime Gate Antigravity Proxy
### `prime-gate-proxy-antigravity-lik`

**Ein produktionsreifer, selbst gehosteter OpenAI- und Anthropic-kompatibler Dual-Protokoll-Proxy-Gateway für Google Antigravity.**

[![NPM Version](https://img.shields.io/npm/v/prime-gate-antigravity.svg?style=for-the-badge&logo=npm&color=CB3837)](https://www.npmjs.com/package/prime-gate-antigravity)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependencies)
[![Dependents](https://img.shields.io/badge/dependents-0-blue.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Sprache auswählen / Select Language

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 Übersicht

**Prime Gate** ist eine schlanke und robuste API-Bridge, die den internen Cloud AI Companion / Antigravity-Dienst von Google in eine **OpenAI-konforme** (`/v1/chat/completions`) und **native Anthropic Messages API-kompatible** (`/v1/messages`) REST- & SSE-Schnittstelle kapselt.

Nutzen Sie Ihre Google Antigravity-Kontingente – darunter **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)** und **Gemini 3.8 Flash** – direkt in Ihren bevorzugten AI-Entwicklungswerkzeugen wie **Claude Code CLI**, **Cline**, **Roo Code**, **OpenCode**, **Cursor**, **Continue.dev**, **Aider** und **SillyTavern**.

---

## 🌟 Hauptfunktionen

1. **Dual-Protokoll-Unterstützung (OpenAI & Anthropic Native):**
   Vollständige Unterstützung für OpenAI- und native Anthropic-Endpunkte (`/v1/messages`) zur direkten Anbindung von Claude Code CLI.
2. **Mehrsprachiger semantischer Vektor-Cache:**
   Lokaler FastEmbed ONNX-Vektor-Cache mit SQLite WAL-Persistenz (~12ms TTFT).
3. **Enterprise-Sicherheit (AES-256-GCM):**
   Lokale Anmeldedaten werden mit AES-256-GCM und OS-Keyring geschützt; granulare Client-API-Key-Richtlinien (RPM / TPD).
4. **Echtzeit-Denkprozess-Streaming (Thinking Mode):**
   Liefert Reasoning-Chunks via `choices[0].delta.reasoning_content` in Echtzeit.
3. **Keine 400 Bad Request Fehler (Schema Sanitizer):**
   Bereinigt automatisch nicht unterstützte JSON-Schema-Einschränkungen (`exclusiveMinimum`, `$schema`, `additionalProperties`) für stabile Tool Calls.
4. **Automatische Kontingent- und Tariferkennung:**
   Erkennt **`Google AI Pro (Trial Tier)`** vs **`Paid Tier`** und listet nur verfügbare Modelle auf.
5. **Modernes React 18 + TypeScript SPA-Dashboard:**
   Vite-gestützte modulare Web-App mit dedizierten Routen (`/dashboard`, `/benchmarks`, `/accounts`, `/sandbox`, `/sentinel`), Echtzeit-Token-Radar, Konten-Verwaltung und interaktiver Test-Sandbox.
6. **Leistungsstarke CLI:**
   Befehle wie `--version`, `quota`, `auth` und Hintergrund-Daemon-Verwaltung für Windows.

---

## 📸 Web UI Dashboard Galerie

👉 **[Vollständige hochauflösende Screenshot-Galerie ansehen](../../docs/SCREENSHOTS.md)**

---

## ⚡ Schnellstart

```bash
# Sofortiger Start via NPX (Kein Git Clone erforderlich)
npx prime-gate-antigravity daemon start

# Quota anzeigen
npx prime-gate-antigravity quota

# Oder global via NPM installieren
npm install -g prime-gate-antigravity
prime-gate daemon start
```

### Web-UI-Onboarding
1. Öffnen Sie Ihren Browser unter **`http://127.0.0.1:52110`**.
2. Falls noch kein Konto verknüpft ist, erscheint das Anthropic-Setup-Overlay:
   - Klicken Sie auf **"Sign in with Google"** für Google OAuth 2.0 PKCE.
   - Oder wählen Sie **"⚡ Quick Import from OpenCode Config"**.
3. Nach der Anmeldung schaltet das Dashboard automatisch um und aktiviert das Kontingente-Radar sowie den OpenAI-Endpunkt (`http://127.0.0.1:52111/v1`).

> 💡 **Terminal-Alternative:** `python -m prime_gate.cli auth login` oder `python -m prime_gate.cli quota`.

---

## 📜 Lizenz & Autor

- **Autor:** [Irham Karaman](https://github.com/irhamkaraman)
- **Lizenz:** [MIT License](../../LICENSE)
