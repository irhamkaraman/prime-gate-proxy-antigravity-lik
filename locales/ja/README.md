<div align="center">

# ⚡ Prime Gate Antigravity プロキシ
### `prime-gate-proxy-antigravity-lik`

**Google Antigravity向け本番グレード・セルフホスト型 OpenAI 互換プロキシゲートウェイ。**

[![Version](https://img.shields.io/badge/version-1.0.0--beta-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 言語を選択 / Select Language

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 概要

**Prime Gate** は、Google の内部 Cloud AI Companion / Antigravity API を **100% OpenAI 互換の REST & SSE API**（`/v1/models`, `/v1/chat/completions`）としてラップする高性能プロキシゲートウェイです。

**Claude Sonnet 4.6 (Thinking)**、**Claude Opus 4.6 (Thinking)**、**Gemini 3.8 Flash** などの強力なモデルを、**OpenCode**、**Cursor**、**Continue.dev**、**Aider**、**Cline**、**SillyTavern** などのお好みの開発環境で直接利用できます。

---

## 🌟 主な機能

1. **100% OpenAI API 互換:**
   クライアント側の設定を変更することなく、標準の OpenAI エンドポイントとしてシームレスに機能します。
2. **リアルタイム思考プロセス（Thinking Mode）ストリーミング:**
   Claude 4.6 および Gemini 3.8 の深い推論プロセスを `choices[0].delta.reasoning_content` 経由でリアルタイム配信。
3. **400 Bad Request エラー防止（再帰的スキーマサニタイザー）:**
   Google Antigravity でサポートされていない JSON 制約（`exclusiveMinimum`、`$schema` 等）を自動除去し、ツール呼び出しを安定動作させます。
4. **アカウントクォータ＆プラン自動判定:**
   **`Google AI Pro (Trial Tier)`** と **`Paid Tier`** を自動判別し、利用可能なモデルのみを動的に提示します。
5. **グラスモーフィズムデザインの Web UI:**
   Node.js 製の軽量ダッシュボード（`http://127.0.0.1:52110`）でクォータ残量メーターや対話型プロンプトテストを提供。
6. **高機能 CLI スイート:**
   `quota`（クォータ一覧表示）、`auth`（アカウント管理・OAuth ログイン）、Windows 向けバックグラウンドデーモン管理に対応。

---

## ⚡ クイックスタート

```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt

# バックグラウンドで起動 (Windows)
scripts\start-all.bat
# または CLI デーモンで起動
python -m prime_gate.cli daemon start
```

### Web UI オンボーディング
1. ブラウザで **`http://127.0.0.1:52110`** を開きます。
2. アカウント未設定の場合、セットアップ画面が表示されます：
   - **"Sign in with Google"** をクリックして OAuth 2.0 PKCE でログイン。
   - または **"⚡ Quick Import from OpenCode Config"** をクリックして既存設定をインポート。
3. 認証完了後、自動的にメインダッシュボードへ遷移し、リアルタイムクォータと OpenAI エンドポイント (`http://127.0.0.1:52111/v1`) が利用可能になります。

> 💡 **ターミナル操作:** `python -m prime_gate.cli auth login` または `python -m prime_gate.cli quota` もご利用いただけます。

---

## 📜 ライセンス＆開発者

- **開発者:** [Irham Karaman](https://github.com/irhamkaraman)
- **ライセンス:** [MIT License](../../LICENSE)
