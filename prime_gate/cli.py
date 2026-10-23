import sys
from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from . import __version__, __codename__
from .config import DEFAULT_API_PORT, DEFAULT_UI_PORT, DEFAULT_HOST
from .auth import AccountManager, start_interactive_login
from .quota import QuotaMonitor
from .daemon import start_daemon, stop_daemon, get_daemon_status

app = typer.Typer(
    name="prime-gate",
    help="Prime Gate Antigravity: Production-grade OpenAI-compatible proxy for Google Antigravity.",
    add_completion=False
)
auth_app = typer.Typer(name="auth", help="Manage Google Antigravity accounts and OAuth authentication.")
keys_app = typer.Typer(name="keys", help="Manage Client Gateway API Keys and access policies.")
daemon_app = typer.Typer(name="daemon", help="Manage background daemon service.")
db_app = typer.Typer(name="db", help="Manage compiled binary database, integrity checks, and corruption diagnostics.")

app.add_typer(auth_app)
app.add_typer(keys_app)
app.add_typer(daemon_app)
app.add_typer(db_app)

from .db import db, sentinel, REC_SYSTEM

console = Console()
account_mgr = AccountManager()

def _parse_semver(v: str) -> tuple:
    parts = []
    for x in v.lstrip("v").split("."):
        try:
            parts.append(int(x))
        except ValueError:
            parts.append(0)
    return tuple(parts)

def check_npm_update_notifier(silent_if_current: bool = True):
    """
    Non-blocking update checker against NPM registry (prime-gate-antigravity).
    Caches check results in the database for 1 hour to maintain zero CLI latency.
    """
    try:
        now = time.time()
        cached = db.get("system:npm_update_check") or {}
        last_checked = cached.get("last_checked", 0.0)
        latest_ver = cached.get("latest_version")

        # Refresh check every 1 hour (3600 seconds)
        if (now - last_checked > 3600.0) or not latest_ver:
            import urllib.request
            req = urllib.request.Request(
                "https://registry.npmjs.org/prime-gate-antigravity/latest",
                headers={"User-Agent": "PrimeGate-CLI", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latest_ver = data.get("version")
                if latest_ver:
                    db.set("system:npm_update_check", {"last_checked": now, "latest_version": latest_ver})

        if latest_ver and _parse_semver(latest_ver) > _parse_semver(__version__):
            console.print(Panel(
                Text.from_markup(
                    f"[bold yellow]🔔 Update Available on NPM:[/bold yellow] [bold red]{__version__}[/bold red] → [bold green]{latest_ver}[/bold green]\n\n"
                    f"• Update globally via npm:  [bold cyan]npm install -g prime-gate-antigravity@latest[/bold cyan]\n"
                    f"• Or run latest via npx:    [bold cyan]npx prime-gate-antigravity@latest[/bold cyan]\n"
                    f"• Or update Git clone:      [bold cyan]scripts\\update.bat[/bold cyan] (or [bold cyan]git pull[/bold cyan])"
                ),
                title="[bold yellow]Prime Gate NPM Update Available[/bold yellow]",
                border_style="yellow"
            ))
        elif not silent_if_current:
            console.print(f"[bold green]✓ Prime Gate is up to date (v{__version__}) on npmjs.org.[/bold green]")
    except Exception:
        if not silent_if_current:
            console.print("[yellow]Could not reach npmjs.org (package may not yet be published or network offline).[/yellow]")

def version_callback(value: bool):
    if value:
        console.print(Panel(
            Text.from_markup(
                f"[bold cyan]prime-gate-proxy-antigravity-lik[/bold cyan] version [bold green]{__version__}[/bold green] "
                f"([italic yellow]Codename: {__codename__}[/italic yellow])\n"
                f"[dim]Engine: Python 3.11+ / FastAPI / HTTPX | Frontend: Node.js Glassmorphic Dashboard\n"
                f"NPM Package: prime-gate-antigravity | GitHub: https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik[/dim]"
            ),
            title="[bold white]Prime Gate Antigravity[/bold white]",
            border_style="cyan"
        ))
        check_npm_update_notifier(silent_if_current=True)
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", help="Show version information and exit.", callback=version_callback, is_eager=True
    )
):
    """Prime Gate Antigravity CLI Suite."""
    check_npm_update_notifier(silent_if_current=True)

@app.command(name="check-update")
def check_update_cmd():
    """Check for latest updates from npmjs.org."""
    console.print("[cyan]Checking for Prime Gate updates on npmjs.org (prime-gate-antigravity)...[/cyan]")
    check_npm_update_notifier(silent_if_current=False)

@app.command()
def start(
    port: int = typer.Option(DEFAULT_API_PORT, "--port", "-p", help="Port to run the OpenAI API proxy on."),
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help="Host address to bind.")
):
    """Start the proxy server in the foreground."""
    import uvicorn
    from .server import app as fastapi_app

    # Non-loopback Host Bind Guard
    if host not in ("127.0.0.1", "localhost", "::1"):
        active_keys = db.get_active_api_keys()
        if not active_keys:
            console.print(
                f"[bold red]CRITICAL SECURITY ERROR: Cannot bind to non-loopback interface '{host}' without active API key authentication configured![/bold red]\n"
                "[yellow]Refusing to start. Run 'prime-gate auth create-key' first to generate an authorized API key.[/yellow]"
            )
            raise typer.Exit(code=1)
        else:
            console.print(
                f"[bold yellow]SECURITY WARNING: Prime Gate is listening on external interface '{host}'. Ensure TLS reverse proxy and firewall rules are active.[/bold yellow]"
            )

    console.print(f"[bold green]Starting Prime Gate Proxy on http://{host}:{port}...[/bold green]")
    uvicorn.run(fastapi_app, host=host, port=port)

@app.command()
def ui(
    port: int = typer.Option(DEFAULT_UI_PORT, "--port", "-p", help="Port to run the Web UI on."),
    api_port: int = typer.Option(DEFAULT_API_PORT, "--api-port", help="Port where Python API is running.")
):
    """Launch the Node.js Web UI Dashboard."""
    import subprocess
    import webbrowser
    from .config import PROJECT_ROOT

    ui_script = PROJECT_ROOT / "ui" / "server.js"
    url = f"http://127.0.0.1:{port}"
    console.print(f"[bold cyan]Launching Prime Gate Web UI at {url}...[/bold cyan]")
    try:
        webbrowser.open(url)
        subprocess.run(["node", str(ui_script), "--port", str(port), "--api-port", str(api_port)])
    except KeyboardInterrupt:
        console.print("\n[yellow]Web UI stopped.[/yellow]")

@app.command()
def quota(
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh live quota directly from Google Antigravity servers.")
):
    """Display real-time quota status and available model catalog."""
    import asyncio
    active_acc = account_mgr.get_active_account()
    if not active_acc:
        console.print("[bold red]No accounts configured! Run 'prime-gate auth import' or 'prime-gate auth login'.[/bold red]")
        return

    tier_label = QuotaMonitor.get_tier_label(active_acc)
    try:
        rows = asyncio.run(QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=refresh))
        models = asyncio.run(QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=refresh))
    except Exception:
        rows = QuotaMonitor.parse_quota_details(active_acc)
        models = QuotaMonitor.get_available_models(active_acc)

    table = Table(title=f"Quota Status - {active_acc.get('email')} ({tier_label})", border_style="cyan")
    table.add_column("Model Family", style="bold white")
    table.add_column("Remaining Quota", justify="right")
    table.add_column("Progress Bar", justify="left")
    table.add_column("Reset Time", style="dim")

    for r in rows:
        pct = r["percentage"]
        bars = int(pct / 10)
        bar_str = f"[{'#' * bars}{'.' * (10 - bars)}]"
        color = "green" if pct > 40 else ("yellow" if pct > 15 else "red")
        table.add_row(
            r["label"],
            f"[{color}]{pct}%[/{color}]",
            f"[{color}]{bar_str}[/{color}]",
            str(r["reset_time"])
        )

    console.print(table)
def _create_key_handler(
    name: str = "api-client",
    rpm: int = 0,
    tpd: int = 0,
    quota: float = 0.0,
    models: str = "",
    cache_scope: str = "shared"
):
    import json
    allowed_list = [m.strip() for m in models.split(",") if m.strip()] if models else []
    raw_key, record = db.create_api_key(
        name=name,
        rate_limit_rpm=rpm,
        rate_limit_tpd=tpd,
        quota_credits=quota,
        allowed_models=json.dumps(allowed_list),
        cache_scope=cache_scope
    )
    models_display = ", ".join(allowed_list) if allowed_list else "All models allowed (*)"
    console.print(Panel(
        f"[bold green]Client Gateway API Key Created Successfully![/bold green]\n\n"
        f"[bold white]Key Secret:[/bold white] [bold yellow]{raw_key}[/bold yellow]\n\n"
        f"[bold red]IMPORTANT:[/bold red] Copy this key now! This is the ONLY time it will ever be shown.\n"
        f"Stored securely in database as salted SHA-256 hash.\n\n"
        f"[bold cyan]Policies Configured:[/bold cyan]\n"
        f"  • Name: [white]{record['name']}[/white] | ID: {record['id']} | Prefix: {record['prefix']}...\n"
        f"  • Rate Limit (RPM): [white]{'Unlimited' if rpm == 0 else f'{rpm} req/min'}[/white]\n"
        f"  • Daily Token Limit (TPD): [white]{'Unlimited' if tpd == 0 else f'{tpd:,} tokens/day'}[/white]\n"
        f"  • Lifetime Quota Credits: [white]{'Unlimited' if quota == 0.0 else f'{quota:,.2f}'}[/white]\n"
        f"  • Allowed Models: [white]{models_display}[/white]\n"
        f"  • Cache Scope: [white]{cache_scope}[/white]",
        title="Prime Gate Client Gateway API Key",
        border_style="green"
    ))

@keys_app.command("create")
def keys_create(
    name: str = typer.Option("api-client", "--name", "-n", help="Name or label for this API key."),
    rpm: int = typer.Option(0, "--rpm", help="Rate limit requests per minute (0 = unlimited)."),
    tpd: int = typer.Option(0, "--tpd", help="Daily LLM token quota in tokens/day (0 = unlimited)."),
    quota: float = typer.Option(0.0, "--quota", help="Lifetime credits quota (0.0 = unlimited)."),
    models: str = typer.Option("", "--models", "-m", help="Comma-separated allowed models whitelist (empty = all)."),
    cache_scope: str = typer.Option("shared", "--cache-scope", help="Cache scope: shared, key, or disabled.")
):
    """Generate a new secure Client Gateway API key with granular policies."""
    _create_key_handler(name, rpm, tpd, quota, models, cache_scope)

@auth_app.command("create-key")
def auth_create_key(
    name: str = typer.Option("api-client", "--name", "-n", help="Name or label for this API key."),
    rpm: int = typer.Option(0, "--rpm", help="Rate limit requests per minute (0 = unlimited)."),
    tpd: int = typer.Option(0, "--tpd", help="Daily LLM token quota in tokens/day (0 = unlimited)."),
    quota: float = typer.Option(0.0, "--quota", help="Lifetime credits quota (0.0 = unlimited)."),
    models: str = typer.Option("", "--models", "-m", help="Comma-separated allowed models whitelist (empty = all)."),
    cache_scope: str = typer.Option("shared", "--cache-scope", help="Cache scope: shared, key, or disabled.")
):
    """Generate a new secure API key (legacy alias for `prime-gate keys create`)."""
    _create_key_handler(name, rpm, tpd, quota, models, cache_scope)

def _list_keys_handler():
    import json
    import datetime
    keys = db.list_api_keys()
    if not keys:
        console.print("[yellow]No API keys found. Run 'prime-gate keys create' to generate one.[/yellow]")
        return

    table = Table(title="Prime Gate Client Gateway API Keys", border_style="cyan")
    table.add_column("ID", justify="right")
    table.add_column("Name", style="bold white")
    table.add_column("Key Preview", style="dim")
    table.add_column("RPM", justify="right")
    table.add_column("TPD (Daily)", justify="right")
    table.add_column("Cache", style="magenta")
    table.add_column("Models", style="yellow")
    table.add_column("Created", style="cyan")
    table.add_column("Last Used", style="green")
    table.add_column("Status", style="bold")

    for k in keys:
        created_str = datetime.datetime.fromtimestamp(k["created_at"]).strftime("%Y-%m-%d %H:%M")
        used_str = datetime.datetime.fromtimestamp(k["last_used_at"]).strftime("%Y-%m-%d %H:%M") if k.get("last_used_at") else "Never"
        status = "[red]Revoked[/red]" if k.get("revoked_at") else "[green]Active[/green]"
        rpm_str = "unlimited" if not k.get("rate_limit_rpm") else str(k["rate_limit_rpm"])
        tpd_str = "unlimited" if not k.get("rate_limit_tpd") else f"{k['rate_limit_tpd']:,}"
        cache_str = k.get("cache_scope", "shared")
        
        allowed_raw = k.get("allowed_models", "[]")
        try:
            allowed = json.loads(allowed_raw) if isinstance(allowed_raw, str) else allowed_raw
        except Exception:
            allowed = []
        models_str = "*" if not allowed else f"{len(allowed)} models"

        table.add_row(
            str(k["id"]),
            k["name"],
            f"{k['prefix']}...",
            rpm_str,
            tpd_str,
            cache_str,
            models_str,
            created_str,
            used_str,
            status
        )

    console.print(table)

@keys_app.command("list")
def keys_list():
    """List all registered Client Gateway API keys with policy limits."""
    _list_keys_handler()

@auth_app.command("list-keys")
def auth_list_keys():
    """List all registered API keys (legacy alias for `prime-gate keys list`)."""
    _list_keys_handler()

def _revoke_key_handler(target: str):
    success = db.revoke_api_key(target)
    if success:
        console.print(f"[bold green]API Key '{target}' has been successfully revoked.[/bold green]")
    else:
        console.print(f"[bold red]Failed to revoke key '{target}'. Key not found or already revoked.[/bold red]")

@keys_app.command("revoke")
def keys_revoke(
    target: str = typer.Argument(..., help="Numeric ID or exact name of the API key to revoke.")
):
    """Revoke an active API key immediately."""
    _revoke_key_handler(target)

@auth_app.command("revoke-key")
def auth_revoke_key(
    target: str = typer.Argument(..., help="Numeric ID or exact name of the API key to revoke.")
):
    """Revoke an active API key immediately."""
    _revoke_key_handler(target)

@app.command("check-models")
@app.command("models")
def check_models(
    refresh: bool = typer.Option(True, "--refresh", "-r", help="Force refresh models directly from Google Antigravity account.")
):
    """Query live supported models directly from Google Antigravity account."""
    import asyncio
    active_acc = account_mgr.get_active_account()
    if not active_acc:
        console.print("[bold red]No accounts configured! Run 'prime-gate auth login' or 'prime-gate auth import'.[/bold red]")
        return

    console.print(f"[bold cyan]Connecting to Google Antigravity for account {active_acc.get('email')}...[/bold cyan]")
    try:
        models = asyncio.run(QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=refresh))
    except Exception as e:
        console.print(f"[bold red]Failed to fetch live models: {e}[/bold red]")
        models = QuotaMonitor.get_available_models(active_acc)

    table = Table(title=f"Live Models Catalog - Google Antigravity ({len(models)} Models)", border_style="green")
    table.add_column("Model ID (OpenAI Endpoint)", style="bold green")
    table.add_column("Display Name", style="white")
    table.add_column("Provider", style="dim")

    for m in models:
        table.add_row(m["id"], m.get("name", m["id"]), m.get("owned_by", "google-antigravity"))

    console.print(table)
    console.print("[dim][OK] Models are active and ready to use via base URL: http://127.0.0.1:52111/v1[/dim]")

@auth_app.command("list")
def auth_list():
    """List all configured Google Antigravity accounts."""
    accounts = account_mgr.load_accounts()
    if not accounts:
        console.print("[yellow]No accounts configured.[/yellow]")
        return

    table = Table(title=f"Registered Antigravity Accounts ({len(accounts)} accounts)", border_style="green")
    table.add_column("No", justify="right")
    table.add_column("Email", style="bold white")
    table.add_column("Project ID", style="dim")
    table.add_column("Detected Tier", style="cyan")

    for idx, acc in enumerate(accounts, 1):
        tier = QuotaMonitor.get_tier_label(acc)
        table.add_row(str(idx), acc.get("email", "-"), acc.get("projectId", "-"), tier)

    console.print(table)

@auth_app.command("import")
def auth_import():
    """Import existing accounts from OpenCode config into local config and auto-sync binary DB."""
    count = account_mgr.import_from_opencode()
    if count > 0:
        console.print(f"[bold green]Successfully imported {count} account(s) from OpenCode![/bold green]")
        active_acc = account_mgr.get_active_account()
        if active_acc:
            import asyncio
            console.print(f"[dim]Auto-syncing live models & quota into binary DB for {active_acc.get('email')}...[/dim]")
            try:
                models = asyncio.run(QuotaMonitor.fetch_live_models_from_antigravity(active_acc, force_refresh=True))
                quota = asyncio.run(QuotaMonitor.fetch_live_quota_from_antigravity(active_acc, force_refresh=True))
                console.print(f"[bold green][OK] Loaded {len(models)} live models and {len(quota)} quota buckets into compiled binary DB.[/bold green]")
            except Exception as e:
                console.print(f"[yellow]Initial sync deferred: {e}[/yellow]")
    else:
        console.print("[yellow]No OpenCode accounts found or import failed.[/yellow]")

@auth_app.command("login")
def auth_login(port: int = 53123):
    """Authenticate a new Google account via browser and auto-sync models/quota to binary DB."""
    try:
        new_account = start_interactive_login(port=port)
        accounts = account_mgr.load_accounts()
        # Deduplicate by email
        accounts = [a for a in accounts if a.get("email") != new_account["email"]]
        accounts.append(new_account)
        account_mgr.save_accounts(accounts)
        console.print(f"[bold green]Login successful for account: {new_account['email']}[/bold green]")

        import asyncio
        console.print(f"[dim]Syncing live models & quota into binary database for {new_account.get('email')}...[/dim]")
        try:
            models = asyncio.run(QuotaMonitor.fetch_live_models_from_antigravity(new_account, force_refresh=True))
            quota = asyncio.run(QuotaMonitor.fetch_live_quota_from_antigravity(new_account, force_refresh=True))
            console.print(f"[bold green][OK] Successfully saved {len(models)} active models & quota into compiled database.[/bold green]")
        except Exception as e:
            console.print(f"[yellow]Live database sync deferred: {e}[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Login failed: {e}[/bold red]")

@auth_app.command("remove")
@auth_app.command("delete")
def auth_remove(
    email: Optional[str] = typer.Argument(None, help="Email of the account to remove (positional)."),
    email_flag: Optional[str] = typer.Option(None, "--email", "-e", help="Email of the account to remove via flag."),
    delete_all: bool = typer.Option(False, "--all", "-a", help="Delete ALL configured accounts from Prime Gate."),
    force: bool = typer.Option(False, "--force", "-f", "--yes", "-y", help="Skip interactive confirmation prompt.")
):
    """Remove or delete Google Antigravity accounts from Prime Gate with flexible flags."""
    target_email = email_flag or email

    if delete_all:
        if not force:
            confirm = typer.confirm("Are you sure you want to remove ALL Antigravity accounts from Prime Gate?")
            if not confirm:
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
        if account_mgr.clear_accounts():
            console.print("[bold green][OK] All Antigravity accounts successfully removed from Prime Gate.[/bold green]")
            console.print("[dim]Prime Gate is now reset to initial onboarding state.[/dim]")
        else:
            console.print("[bold red]Failed to clear accounts.[/bold red]")
        return

    accounts = account_mgr.load_accounts()
    if not accounts:
        console.print("[yellow]No accounts configured in Prime Gate.[/yellow]")
        return

    if not target_email:
        console.print("[bold cyan]Select the account to remove:[/bold cyan]")
        for idx, acc in enumerate(accounts, 1):
            console.print(f"  [bold white]{idx}.[/bold white] {acc.get('email')} [dim]({acc.get('projectId', 'default')})[/dim]")
        choice = typer.prompt("Enter the account number to remove (or 'q' to cancel)")
        if choice.strip().lower() == 'q':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
        try:
            sel_idx = int(choice.strip()) - 1
            if 0 <= sel_idx < len(accounts):
                target_email = accounts[sel_idx].get("email")
            else:
                console.print("[bold red]Invalid number selected.[/bold red]")
                return
        except ValueError:
            console.print("[bold red]Input must be a valid number.[/bold red]")
            return

    if not force:
        confirm = typer.confirm(f"Are you sure you want to remove account '{target_email}' from Prime Gate?")
        if not confirm:
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    if account_mgr.remove_account(target_email):
        console.print(f"[bold green][OK] Successfully removed account {target_email} from Prime Gate.[/bold green]")
        remaining = account_mgr.load_accounts()
        console.print(f"[dim]Remaining registered accounts: {len(remaining)}.[/dim]")
    else:
        console.print(f"[bold yellow]Account {target_email} not found in Prime Gate.[/bold yellow]")

@auth_app.command("clear")
def auth_clear(
    yes: bool = typer.Option(False, "--yes", "-y", "--force", "-f", help="Skip confirmation prompt.")
):
    """Remove ALL configured Google Antigravity accounts from Prime Gate."""
    if not yes:
        confirm = typer.confirm("Are you sure you want to remove all Antigravity accounts from Prime Gate?")
        if not confirm:
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    if account_mgr.clear_accounts():
        console.print("[bold green][OK] All Antigravity accounts successfully removed from Prime Gate.[/bold green]")
        console.print("[dim]Prime Gate is now reset to initial onboarding state.[/dim]")
    else:
        console.print("[bold red]Failed to clear accounts.[/bold red]")

@auth_app.command("switch")
def auth_switch(
    email: Optional[str] = typer.Argument(None, help="Email of the account to activate (positional)."),
    email_flag: Optional[str] = typer.Option(None, "--email", "-e", help="Email of the account to activate via flag.")
):
    """Switch the active Google Antigravity account in Prime Gate."""
    accounts = account_mgr.load_accounts()
    if not accounts:
        console.print("[yellow]No accounts configured in Prime Gate.[/yellow]")
        return

    target_email = email_flag or email
    if not target_email:
        console.print("[bold cyan]Select an account to activate:[/bold cyan]")
        active_acc = account_mgr.get_active_account()
        active_email = active_acc.get("email") if active_acc else None
        for idx, acc in enumerate(accounts, 1):
            is_cur = " [bold green](Current Active)[/bold green]" if acc.get("email") == active_email else ""
            console.print(f"  [bold white]{idx}.[/bold white] {acc.get('email')} [dim]({acc.get('projectId', 'default')})[/dim]{is_cur}")
        choice = typer.prompt("Enter the account number to set active (or 'q' to cancel)")
        if choice.strip().lower() == 'q':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
        try:
            sel_idx = int(choice.strip()) - 1
            if 0 <= sel_idx < len(accounts):
                target_email = accounts[sel_idx].get("email")
            else:
                console.print("[bold red]Invalid number selected.[/bold red]")
                return
        except ValueError:
            console.print("[bold red]Input must be a valid number.[/bold red]")
            return

    switched = account_mgr.set_active_account(target_email)
    if switched:
        console.print(f"[bold green][OK] Switched active account to: {switched.get('email')}[/bold green]")
        import asyncio
        console.print("[dim]Syncing live models & quota into binary DB...[/dim]")
        try:
            models = asyncio.run(QuotaMonitor.fetch_live_models_from_antigravity(switched, force_refresh=True))
            quota = asyncio.run(QuotaMonitor.fetch_live_quota_from_antigravity(switched, force_refresh=True))
            console.print(f"[bold green][OK] Loaded {len(models)} live models and {len(quota)} quota buckets into compiled binary DB.[/bold green]")
        except Exception as e:
            console.print(f"[yellow]Live sync deferred: {e}[/yellow]")
    else:
        console.print(f"[bold red]Account '{target_email}' not found.[/bold red]")


@daemon_app.command("start")
def daemon_start(
    api_port: int = typer.Option(DEFAULT_API_PORT, "--port", "-p", help="API port"),
    ui_port: int = typer.Option(DEFAULT_UI_PORT, "--ui-port", help="Web UI port")
):
    """Start proxy & UI as detached background services."""
    res = start_daemon(api_port=api_port, ui_port=ui_port)
    if res.get("success"):
        st = res["state"]
        console.print(Panel(
            f"[bold green]Daemon Successfully Started in Background![/bold green]\n"
            f"API Port: [bold cyan]http://127.0.0.1:{st['api_port']}/v1[/bold cyan] (PID: {st['pid']})\n"
            f"Web UI Port: [bold cyan]http://127.0.0.1:{st['ui_port']}[/bold cyan] (PID: {st['ui_pid']})",
            title="Daemon Started",
            border_style="green"
        ))
    else:
        console.print(f"[yellow]{res.get('message')}[/yellow]")

@daemon_app.command("stop")
def daemon_stop():
    """Stop the running background daemon processes."""
    res = stop_daemon()
    if res.get("success"):
        console.print("[bold green]All background proxy daemons successfully stopped.[/bold green]")
    else:
        console.print(f"[bold red]Failed to stop daemon: {res}[/bold red]")

@daemon_app.command("status")
def daemon_status():
    """Check background daemon status."""
    st = get_daemon_status()
    if st.get("running"):
        console.print(Panel(
            f"[bold green]Status: RUNNING[/bold green]\n"
            f"Python API PID: {st['pid']} (Port: {st['api_port']})\n"
            f"Node.js UI PID: {st['ui_pid']} (Port: {st['ui_port']})\n"
            f"Started At: {st.get('started_at')}",
            title="Daemon Status",
            border_style="green"
        ))
    else:
        console.print("[bold yellow]Status: STOPPED (No active daemon)[/bold yellow]")

# -------------------------------------------------------------
# Compiled Binary Database Management & Sentinel Commands
# -------------------------------------------------------------

@db_app.command("status")
def db_status():
    """Display binary database storage size, record count, and WAL engine metrics."""
    st = db.get_status()
    table = Table(title="Prime Gate Compiled Binary Database Engine", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Engine Type", st["engine"])
    table.add_row("Binary Format", st["format"])
    table.add_row("File Location", st["db_path"])
    table.add_row("Storage Size", f"{round(st['size_bytes'] / 1024, 2)} KB ({st['size_bytes']} bytes)")
    table.add_row("Sealed Records", str(st["records_count"]))
    table.add_row("Recorded Incidents", str(st["incidents_count"]))
    table.add_row("Active WS Subscribers", str(st["active_ws_subscribers"]))

    console.print(table)

@db_app.command("check")
def db_check():
    """Execute full SQLite B-Tree and record-level CRC32 checksum integrity audit."""
    console.print("[dim]Scanning compiled binary blocks and checking CRC32 checksums...[/dim]")
    audit = db.run_integrity_check()

    if audit["healthy"]:
        console.print(Panel(
            f"[bold green][OK] Database Integrity 100% HEALTHY[/bold green]\n"
            f"SQLite B-Tree Status: {audit['sqlite_status']}\n"
            f"Binary Records Scanned: {audit['records_scanned']}\n"
            f"Corruptions Found: 0\n"
            f"Physical Size: {round(audit['size_bytes'] / 1024, 2)} KB",
            title="Database Audit Passed",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red][ALERT] DATABASE CORRUPTION DETECTED![/bold red]\n"
            f"Corrupted Blocks: {audit['corruptions_count']}\n"
            f"Details: {audit['corruptions']}",
            title="Integrity Audit Failed",
            border_style="red"
        ))

@db_app.command("test-corrupt")
def db_test_corrupt(
    key: str = typer.Option("system:demo_block", "--key", "-k", help="Target record key to tamper with.")
):
    """Simulate binary data corruption to verify CRC32 watchdog, critical logs, and alert handlers."""
    import time
    # Ensure key exists
    db.set(key, {"sample_data": "prime_gate_crc32_test", "created": time.time()}, record_type=REC_SYSTEM)
    console.print(f"[yellow]Injecting bit-level binary corruption into record '{key}'...[/yellow]")
    
    # Simulate corruption
    db.simulate_corruption(key)
    console.print(f"[bold green][OK] Corruption successfully simulated! Check the logs above for [DATABASE_CORRUPT] alerts.[/bold green]")

@db_app.command("rotate-key")
def db_rotate_key():
    """Rotate the AES-256-GCM master database encryption key and re-encrypt all records."""
    console.print("[yellow]Rotating database master encryption key...[/yellow]")
    try:
        db.rotate_database_key()
        console.print("[bold green][OK] Master encryption key successfully rotated and all records re-encrypted with AES-256-GCM![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Key rotation failed: {e}[/bold red]")

@db_app.command("rollback")
def db_rollback():
    """Roll back the database to the most recent backup."""
    success, detail = db.rollback_latest_backup()
    if success:
        console.print(f"[bold green][OK] Database successfully rolled back from backup: {detail}[/bold green]")
    else:
        console.print(f"[bold red]Rollback failed: {detail}[/bold red]")

db_app.command("daemon")
def db_daemon_run(
    interval: int = typer.Option(30, "--interval", "-i", help="Audit interval in seconds.")
):
    """Run standalone database sentinel daemon with continuous CRC32 integrity audit."""
    import asyncio
    console.print(f"[bold green]Starting Database Sentinel Daemon (Audit interval: {interval}s)...[/bold green]")
    sentinel.interval = interval
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(sentinel.start())
        loop.run_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping Database Sentinel Daemon...[/yellow]")
@app.command("remove-account")
@app.command("delete-account")
def top_level_remove_account(
    email: Optional[str] = typer.Argument(None, help="Email of the account to remove (positional)."),
    email_flag: Optional[str] = typer.Option(None, "--email", "-e", help="Email of the account to remove via flag."),
    delete_all: bool = typer.Option(False, "--all", "-a", help="Delete ALL configured accounts from Prime Gate."),
    force: bool = typer.Option(False, "--force", "-f", "--yes", "-y", help="Skip interactive confirmation prompt.")
):
    """Direct shortcut to delete an account or all accounts using flags."""
    auth_remove(email=email, email_flag=email_flag, delete_all=delete_all, force=force)

@app.command("clear-accounts")
def top_level_clear_accounts(
    force: bool = typer.Option(False, "--force", "-f", "--yes", "-y", help="Skip interactive confirmation prompt.")
):
    """Direct shortcut to clear all accounts from Prime Gate."""
    auth_clear(yes=force)

if __name__ == "__main__":
    app()