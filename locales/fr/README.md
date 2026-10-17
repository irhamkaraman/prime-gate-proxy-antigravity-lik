<div align="center">

# ⚡ Proxy Prime Gate Antigravity
### `prime-gate-proxy-antigravity-lik`

**Une passerelle proxy auto-hébergée de niveau production compatible OpenAI pour Google Antigravity.**

[![Version](https://img.shields.io/badge/version-1.0.0--beta-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Sélectionner la langue / Select Language

[🇺🇸 English](../../README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](README.md)

---

</div>

## 📖 Vue d'ensemble

**Prime Gate** est une passerelle API haute performance qui encapsule le service interne Google Cloud AI Companion / Antigravity dans une **API REST & SSE 100% compatible OpenAI** (`/v1/models`, `/v1/chat/completions`).

Utilisez vos quotas Google Antigravity – y compris **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)** et **Gemini 3.8 Flash** – directement dans vos environnements de développement IA préférés : **OpenCode**, **Cursor**, **Continue.dev**, **Aider**, **Cline** et **SillyTavern**.

---

## 🌟 Fonctionnalités clés

1. **100% Conforme aux spécifications OpenAI :**
   Remplacement direct sans modification de vos clients IA habituels.
2. **Streaming du raisonnement en temps réel (Thinking Mode) :**
   Transmet les blocs de réflexion via `choices[0].delta.reasoning_content` pour Claude 4.6 et Gemini 3.8.
3. **Zéro erreur 400 Bad Request (Nettoyeur de schéma récursif) :**
   Supprime automatiquement les contraintes JSON Schema non supportées (`exclusiveMinimum`, `$schema`, `additionalProperties`) pour une exécution stable des outils.
4. **Détection intelligente des quotas et abonnements :**
   Distingue automatiquement **`Google AI Pro (Trial Tier)`** de la version **`Paid Tier`**.
5. **Tableau de bord Web Glassmorphic :**
   Interface visuelle en Node.js sans dépendances externes (`http://127.0.0.1:52110`) avec indicateurs de quotas et bac à sable de test.
6. **Suite CLI complète :**
   Commandes interactives `--version`, `quota`, `auth`, et gestion du démon en arrière-plan sous Windows.

---

## ⚡ Démarrage rapide

```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt

# Démarrer en arrière-plan (Windows)
scripts\start-all.bat
# Ou via le démon CLI
python -m prime_gate.cli daemon start
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
