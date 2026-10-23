<div align="center">

# ⚡ Prime Gate Antigravity 代理网关
### `prime-gate-proxy-antigravity-lik`

**专为 Google Antigravity 打造的企业级、自托管 OpenAI 与 Anthropic 双协议兼容代理网关。**

[![Version](https://img.shields.io/npm/v/prime-gate-antigravity.svg?style=for-the-badge&logo=npm&color=CB3837)](https://www.npmjs.com/package/prime-gate-antigravity)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependencies)
[![Dependents](https://img.shields.io/badge/dependents-0-blue.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 语言选择 / Language Selection
[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](../id/README.md) • [🇨🇳 简体中文](README.md) • [🇯🇵 日本語](../ja/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

📸 [**查看完整 Web 控制台高清界面图集**](../../docs/SCREENSHOTS.md) • 📚 [**完整用户集成手册**](../../docs/USER_GUIDE.md)

---

</div>

## 🚀 极速安装与启动

```bash
# 方式 1: 无需安装，直接即时运行 (推荐)
npx prime-gate-antigravity

# 方式 2: 全局安装到系统
npm install -g prime-gate-antigravity@latest

# 启动后台守护服务 (Proxy API :52111 + Web UI :52110)
prime-gate daemon start
```

### 🎛️ 常用命令行参数 (Flags)
| 参数 / 选项 | 作用说明 | 默认值 |
| :--- | :--- | :--- |
| `--host <address>` | 代理服务监听地址 | `127.0.0.1` |
| `--port <number>` | 代理 API 端口 (OpenAI & Anthropic) | `52111` |
| `--ui-port <number>` | Web 控制台界面端口 | `52110` |
| `--daemon` | 后台守护进程模式启动 | `false` |
| `--version`, `-v` | 显示当前安装版本 | `1.2.6` |
| `--help`, `-h` | 查看完整帮助与指令列表 | - |

---

## 📸 Web 控制台界面演示

Prime Gate 拥有专为大模型交互设计的 Anthropic 暗色毛玻璃控制台（访问地址 `http://127.0.0.1:52110`）：

👉 **[点击浏览高清界面图集 (完整 5 大核心模块演示)](../../docs/SCREENSHOTS.md)**

---

## ⚡ 快速开始

### 1. 通过 NPX 即时运行（无需克隆与手动配置）
```bash
# 启动后台守护进程 (Proxy API :52111 + Web UI :52110)
npx prime-gate-antigravity daemon start

# 查看配额雷达表格
npx prime-gate-antigravity quota
```

### 2. 通过 NPM 全局安装（推荐）
```bash
npm install -g prime-gate-antigravity
prime-gate daemon start
```

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
