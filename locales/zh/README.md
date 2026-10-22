<div align="center">

# ⚡ Prime Gate Antigravity 代理网关
### `prime-gate-proxy-antigravity-lik`

**专为 Google Antigravity 打造的企业级、自托管 OpenAI 与 Anthropic 双协议兼容代理网关。**

[![Version](https://img.shields.io/badge/version-1.2.4-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 语言选择 / Language Selection

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 项目简介

**Prime Gate** 是一款轻量级高性能企业级双协议代理网关，将 Google 内部的 Cloud AI Companion / Antigravity 接口封装为 **100% 兼容 OpenAI 标准**（`/v1/chat/completions`）与 **原生 Anthropic Messages API**（`/v1/messages`）的 REST & SSE API。

通过该工具，您可以将 Google Antigravity 配额中的 **Claude Sonnet 4.6 (Thinking)**、**Claude Opus 4.6 (Thinking)** 和 **Gemini 3.8 Flash** 模型直接无缝接入主流开发工具，如 **Claude Code CLI**、**Cline**、**Roo Code**、**OpenCode**、**Cursor**、**Continue.dev**、**Aider** 和 **SillyTavern**。

---

## 🌟 核心特性

1. **OpenAI 与 Anthropic 双协议原生支持：**
   全面支持 OpenAI (`/v1/chat/completions`) 与 Anthropic (`/v1/messages`) 规范，可无缝直连 Claude Code CLI。
2. **多语言语义向量缓存 (Semantic Cache)：**
   内置 FastEmbed ONNX 向量缓存与 SQLite WAL 存储，降低重复请求延迟至 ~12ms。
3. **企业级安全架构 (AES-256-GCM)：**
   本地凭据使用 AES-256-GCM 硬件加密隔离保护，全面支持 Client API Key 速率与配额管控。
4. **实时思维链（Reasoning / Thinking）流式传输：**
   原生支持通过 `choices[0].delta.reasoning_content` 输出 Claude 4.6 及 Gemini 3.8 的深度推理过程。
3. **零 400 报错（递归 Schema 清洗）：**
   自动清理 Google Antigravity 不支持的 JSON 约束（如 `exclusiveMinimum`, `exclusiveMaximum`, `$schema`, `additionalProperties`），确保函数与工具调用（Tool Calling）100% 稳定运行。
4. **智能配额与套餐识别：**
   自动识别 **`Google AI Pro (Trial Tier 体验版)`** 与 **`Paid 付费版`**，精准呈现可用模型。
5. **现代化 React 18 + TypeScript SPA 控制台：**
   采用 Vite 构建，支持独立页面路由（`/dashboard`、`/benchmarks`、`/accounts`、`/sandbox`、`/sentinel`），提供实时 Token 柱状雷达图、账号配额监控与交互式测试沙箱。
6. **丰富的终端 CLI 支持：**
   包含 `--version`、`quota`（可视化配额表）、`auth`（账号导入与 OAuth 登录）以及 Windows 后台守护进程（Daemon）管理。

---

## 📸 界面演示与视觉概览

基于 React 18、TypeScript 和实时 WebSocket 构建的 Anthropic 风格暗色毛玻璃控制台：

### 1. 仪表盘与实时遥测 (`/dashboard`)
实时监控 Token 吞吐速率、24小时滑动消耗统计、平均响应延迟（TTFT）、分段 Token 消耗柱状图（`1m`、`1h`、`1d`、`1month`）以及高消耗模型排行榜预览。
![仪表盘与实时遥测](../../docs/images/dashboard-telemetry.png)

### 2. 用量统计与模型基准 (`/benchmarks`)
基于 SQLite WAL 持久化账本实时记录每次 API 调用。直观展示各模型的请求量、延迟基准、Token 占比份额以及加权配额消耗评分（Claude 3x、GPT 2x、Gemini 1x），支持实时搜索过滤与请求 ID 一键复制。
![用量统计与模型基准](../../docs/images/usage-benchmarks.png)

### 3. 账号管理与动态模型目录 (`/accounts`)
多账号 OAuth 集中管理，支持多账号轮询与实时配额状态监控；自动探测 Google Antigravity 可用模型并展示特性标签（思维链支持、多模态视觉、上下文长度、流式输出）。
![账号管理与模型目录](../../docs/images/accounts-models.png)

### 4. 交互式提示词沙箱 (`/sandbox`)
用于测试流式模型输出的交互式工作台。可自由配置系统提示词、用户指令、采样温度与最大 Token 上限，并在右侧实时查看推理速度（TTFT、总耗时、每秒输出 Token 数）。
![提示词沙箱](../../docs/images/prompt-sandbox.png)

### 5. 系统与数据库哨兵 (`/sentinel`)
底层二进制 SQLite WAL 存储健康巡检中心。支持 CRC32 完整性校验、页缓存状态分析、数据库 VACUUM 碎片清理，并通过双向 WebSocket 实时查看后台审计守护日志。
![系统与数据库哨兵](../../docs/images/system-sentinel.png)

---

## ⚡ 快速开始

### 1. 克隆与安装
```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt
```
*(Windows 用户可直接双击运行 `scripts\install.bat`)*

### 2. 启动后台守护进程与 Web 控制台
一键启动 Python 核心 API 与 Node.js Web UI：
- **Windows（一键后台启动）：**
  ```bash
  scripts\start-all.bat
  ```
- **或通过 CLI 守护进程：**
  ```bash
  python -m prime_gate.cli daemon start
  ```
- **或前台终端模式：**
  ```bash
  python -m prime_gate.cli start --port 52111
  python -m prime_gate.cli ui --port 52110
  ```

### 3. 打开 Web 控制台与连接账号
1. 在浏览器中访问 **`http://127.0.0.1:52110`**。
2. 若尚未配置账号，系统将自动弹出 Anthropic 风格的 **引导配置窗口**：
   - 点击 **"Sign in with Google"** 进行 OAuth 2.0 PKCE 认证。
   - 或点击 **"⚡ Quick Import from OpenCode Config"** 快速导入现有凭据。
3. 授权成功后，页面将自动解锁并进入 **主仪表盘**，实时展示配额雷达、可用模型与 OpenAI 端点 (`http://127.0.0.1:52111/v1`)。

> 💡 **终端命令行替代方案：** 偏好纯命令行操作？您也可以直接在终端中运行：
> ```bash
> python -m prime_gate.cli auth login   # 浏览器 OAuth 登录
> python -m prime_gate.cli auth import  # 导入 OpenCode 配置
> python -m prime_gate.cli quota        # 查看配额雷达表格
> ```

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
