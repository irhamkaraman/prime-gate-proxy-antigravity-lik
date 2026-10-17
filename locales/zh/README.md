<div align="center">

# ⚡ Prime Gate Antigravity 代理网关
### `prime-gate-proxy-antigravity-lik`

**专为 Google Antigravity 打造的企业级、自托管 OpenAI 兼容代理网关。**

[![Version](https://img.shields.io/badge/version-1.0.0--beta-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 语言选择 / Language Selection

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 项目简介

**Prime Gate** 是一款轻量级高性能代理网关，将 Google 内部的 Cloud AI Companion / Antigravity 接口封装为 **100% 兼容 OpenAI 标准的 REST & SSE API**（`/v1/models` 和 `/v1/chat/completions`）。

通过该工具，您可以将 Google Antigravity 配额中的 **Claude Sonnet 4.6 (Thinking)**、**Claude Opus 4.6 (Thinking)** 和 **Gemini 3.8 Flash** 模型直接无缝接入主流开发工具，如 **OpenCode**、**Cursor**、**Continue.dev**、**Aider**、**Cline** 和 **SillyTavern**。

---

## 🌟 核心特性

1. **100% 兼容 OpenAI 协议：**
   完全兼容 OpenAI API 规范，即插即用，无需修改客户端调用逻辑。
2. **实时思维链（Reasoning / Thinking）流式传输：**
   原生支持通过 `choices[0].delta.reasoning_content` 输出 Claude 4.6 及 Gemini 3.8 的深度推理过程。
3. **零 400 报错（递归 Schema 清洗）：**
   自动清理 Google Antigravity 不支持的 JSON 约束（如 `exclusiveMinimum`, `exclusiveMaximum`, `$schema`, `additionalProperties`），确保函数与工具调用（Tool Calling）100% 稳定运行。
4. **智能配额与套餐识别：**
   自动识别 **`Google AI Pro (Trial / Reliance Jio 18个月促销)`** 与 **`Paid 付费版`**，精准呈现可用模型。
5. **毛玻璃风现代化 Web UI：**
   基于 Node.js 构建，零第三方 npm 依赖，在 `http://127.0.0.1:52110` 提供实时配额仪表盘与交互式测试沙箱。
6. **丰富的终端 CLI 支持：**
   包含 `--version`、`quota`（可视化配额表）、`auth`（账号导入与 OAuth 登录）以及 Windows 后台守护进程（Daemon）管理。

---

## ⚡ 快速开始

### 1. 克隆与安装
```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt
```
*(Windows 用户可直接双击运行 `scripts\install.bat`)*

### 2. 连接 Google Antigravity 账号
- **从已有 OpenCode 配置导入：**
  ```bash
  python -m prime_gate.cli auth import
  ```
- **或通过浏览器进行 Google OAuth 授权：**
  ```bash
  python -m prime_gate.cli auth login
  ```

### 3. 查看实时配额
```bash
python -m prime_gate.cli quota
```

### 4. 启动服务与 Web 控制台
- **一键后台启动（Windows）：**
  ```bash
  scripts\start-all.bat
  ```
- **前台启动 API 服务：**
  ```bash
  python -m prime_gate.cli start --port 52111
  ```
- **启动 Web 控制台：**
  ```bash
  python -m prime_gate.cli ui --port 52110
  ```
  *在浏览器中访问：`http://127.0.0.1:52110`。*

---

## 🔌 客户端配置示例（OpenCode）

在 `~/.config/opencode/opencode.json` 中添加：

```json
{
  "providers": {
    "antigravity": {
      "baseUrl": "http://127.0.0.1:52111/v1",
      "apiKey": "prime-gate-proxy",
      "models": [
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gemini-3.8-flash",
        "gemini-2.5-pro"
      ]
    }
  }
}
```

---

## 📜 开源许可与作者

- **作者：** [Irham Karaman](https://github.com/irhamkaraman)
- **开源协议：** [MIT License](../../LICENSE)
