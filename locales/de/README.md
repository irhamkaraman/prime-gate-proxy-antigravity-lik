<div align="center">

# ⚡ Prime Gate Antigravity Proxy
### `prime-gate-proxy-antigravity-lik`

**Ein produktionsreifer, selbst gehosteter OpenAI- und Anthropic-kompatibler Dual-Protokoll-Proxy-Gateway für Google Antigravity.**

[![Version](https://img.shields.io/badge/version-1.2.4-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
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

## 📸 Benutzeroberfläche & Demonstration

Elegantes Dark-Glassmorphism-Interface auf Basis von React 18, TypeScript und Echtzeit-WebSockets:

### 1. Dashboard & Echtzeit-Telemetrie (`/dashboard`)
Echtzeit-Analyse der Token-Durchsatzrate, rollierende 24h-Verbrauchssummen, durchschnittliche Latenz (TTFT), segmentierte Verbrauchsdiagramme (`1m`, `1h`, `1d`, `1month`) sowie Bestenliste der Modelle nach Kontingentverbrauch.
![Dashboard & Telemetrie](../../docs/images/dashboard-telemetry.png)

### 2. Nutzung & Modell-Benchmarks (`/benchmarks`)
Persistentes SQLite-WAL-Transaktionsbuch aller eingehenden API-Anfragen in Echtzeit. Zeigt Modell-Laufzeiten, Latenzen, Token-Anteile und gewichtete Quota-Impact-Scores (Claude 3x, GPT 2x, Gemini 1x) mit Schnellsuche und Filterfunktionen.
![Nutzung & Modell-Benchmarks](../../docs/images/usage-benchmarks.png)

### 3. Konten-Manager & Dynamischer Modellkatalog (`/accounts`)
Verwaltung mehrerer Google OAuth-Konten mit aktiver Rotation, Kontingentstand und automatischem Modellkatalog inklusive Feature-Badges (Thinking, Vision/Multimodal, Kontextfenster, Streaming).
![Konten-Manager & Modelle](../../docs/images/accounts-models.png)

### 4. Prompt-Sandbox & Testumgebung (`/sandbox`)
Interaktive Testumgebung für Streaming-Inferenz. Konfiguration von System-Prompts, Benutzeranweisungen, Temperatur und Token-Limits mit Live-Metriken (TTFT, Gesamtdauer, Token/Sekunde).
![Prompt-Sandbox](../../docs/images/prompt-sandbox.png)

### 5. System & Datenbank-Sentinel (`/sentinel`)
Diagnosekonsole für den binären SQLite-Speicher im WAL-Modus: CRC32-Integritätsprüfung, Page-Cache-Nutzung, VACUUM-Optimierung und Echtzeit-Auditprotokoll des Hintergrundwächters via WebSockets.
![System & Datenbank-Sentinel](../../docs/images/system-sentinel.png)

---

## ⚡ Schnellstart

```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt

# Im Hintergrund starten (Windows)
scripts\start-all.bat
# Oder via CLI Daemon
python -m prime_gate.cli daemon start
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
