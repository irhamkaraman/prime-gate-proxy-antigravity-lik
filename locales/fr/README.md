<div align="center">

# ⚡ Proxy Prime Gate Antigravity
### `prime-gate-proxy-antigravity-lik`

**Une passerelle proxy auto-hébergée de niveau production compatible OpenAI et Anthropic pour Google Antigravity.**

[![Version](https://img.shields.io/badge/version-1.2.4-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Sélectionner la langue / Select Language

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](README.md)

---

</div>

## 📖 Vue d'ensemble

**Prime Gate** est une passerelle API haute performance qui encapsule le service interne Google Cloud AI Companion / Antigravity dans une **API REST & SSE double protocole**, compatible **OpenAI** (`/v1/chat/completions`) et **native Anthropic Messages API** (`/v1/messages`).

Utilisez vos quotas Google Antigravity – y compris **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)** et **Gemini 3.8 Flash** – directement dans vos environnements de développement IA préférés : **Claude Code CLI**, **Cline**, **Roo Code**, **OpenCode**, **Cursor**, **Continue.dev**, **Aider** et **SillyTavern**.

---

## 🌟 Fonctionnalités clés

1. **Prise en charge double protocole (OpenAI & Anthropic Native) :**
   Compatibilité native avec les clients OpenAI et Anthropic (`/v1/messages`), connectant directement Claude Code CLI.
2. **Cache vectoriel sémantique multilingue (Semantic Cache) :**
   Moteur vectoriel FastEmbed ONNX local avec persistance SQLite WAL (~12ms TTFT).
3. **Sécurité Entreprise renforcée (AES-256-GCM) :**
   Chiffrement matériel des identifiants locaux via OS Keyring et contrôle d'accès granulaire par clé API (RPM / TPD).
4. **Streaming du raisonnement en temps réel (Thinking Mode) :**
   Transmet les blocs de réflexion via `choices[0].delta.reasoning_content` pour Claude 4.6 et Gemini 3.8.
3. **Zéro erreur 400 Bad Request (Nettoyeur de schéma récursif) :**
   Supprime automatiquement les contraintes JSON Schema non supportées (`exclusiveMinimum`, `$schema`, `additionalProperties`) pour une exécution stable des outils.
4. **Détection intelligente des quotas et abonnements :**
   Distingue automatiquement **`Google AI Pro (Trial Tier)`** de la version **`Paid Tier`**.
5. **Tableau de bord SPA moderne React 18 + TypeScript :**
   Application web modulaire sous Vite avec routes dédiées (`/dashboard`, `/benchmarks`, `/accounts`, `/sandbox`, `/sentinel`), graphiques de tokens en direct, gestion multi-comptes et bac à sable interactif.
6. **Suite CLI complète :**
   Commandes interactives `--version`, `quota`, `auth`, et gestion du démon en arrière-plan sous Windows.

---

## 📸 Interface utilisateur & Démonstration

Interface moderne en dark glassmorphism conçue avec React 18, TypeScript et WebSockets temps réel :

### 1. Tableau de bord & Télémétrie en temps réel (`/dashboard`)
Surveillance en direct de la vitesse de génération (tokens/s), consommation sur 24 heures glissantes, latence moyenne (TTFT), graphique segmenté (`1m`, `1h`, `1d`, `1month`) et classement des modèles les plus consommateurs.
![Tableau de bord & Télémétrie](../../docs/images/dashboard-telemetry.png)

### 2. Utilisation & Benchmarks des modèles (`/benchmarks`)
Registre persistant SQLite WAL consignant chaque requête API en direct. Affiche les statistiques par modèle, latences, répartition des tokens et score pondéré d'impact sur le quota (Claude 3x, GPT 2x, Gemini 1x) avec recherche instantanée.
![Utilisation & Benchmarks](../../docs/images/usage-benchmarks.png)

### 3. Gestionnaire de comptes & Catalogue de modèles (`/accounts`)
Gestion multi-comptes Google OAuth avec rotation du compte actif, indicateurs de quotas en direct et découverte automatique des modèles avec badges de capacités (Thinking, Vision/Multimodal, Contexte, Streaming).
![Gestionnaire de comptes & Modèles](../../docs/images/accounts-models.png)

### 4. Bac à sable de prompts (`/sandbox`)
Banc d'essai interactif pour tester l'inférence en streaming. Configurez les prompts système, la température et les limites de tokens avec mesures en direct (TTFT, durée totale, tokens/seconde).
![Bac à sable de prompts](../../docs/images/prompt-sandbox.png)

### 5. Sentinelle système & Base de données (`/sentinel`)
Console de contrôle du stockage binaire SQLite en mode WAL : vérification d'intégrité CRC32, allocation du cache de pages, compactage VACUUM et journal d'audit du démon en direct via WebSockets.
![Sentinelle système & Base de données](../../docs/images/system-sentinel.png)

---

## ⚡ Démarrage rapide

```bash
# Démarrage instantané via NPX (Aucun clone Git requis)
npx prime-gate-antigravity daemon start

# Afficher les quotas
npx prime-gate-antigravity quota

# Ou installer globalement via NPM
npm install -g prime-gate-antigravity
prime-gate daemon start
```

### Intégration via l'interface Web (Onboarding)
1. Ouvrez votre navigateur sur **`http://127.0.0.1:52110`**.
2. Si aucun compte n'est configuré, l'écran d'accueil s'affiche automatiquement :
   - Cliquez sur **"Sign in with Google"** pour vous connecter via Google OAuth 2.0 PKCE.
   - Ou cliquez sur **"⚡ Quick Import from OpenCode Config"** pour importer votre compte existant.
3. Une fois l'authentification réussie, l'accès au tableau de bord complet est déverrouillé, affichant le radar des quotas et le point de terminaison OpenAI (`http://127.0.0.1:52111/v1`).

> 💡 **En ligne de commande :** `python -m prime_gate.cli auth login` ou `python -m prime_gate.cli quota`.

---

## 📜 Licence et auteur

- **Auteur :** [Irham Karaman](https://github.com/irhamkaraman)
- **Licence :** [MIT License](../../LICENSE)
