import sys
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
daemon_app = typer.Typer(name="daemon", help="Manage background daemon service.")

app.add_typer(auth_app)
app.add_typer(daemon_app)

console = Console()
account_mgr = AccountManager()

def version_callback(value: bool):
    if value:
        console.print(Panel(
            Text.from_markup(
                f"[bold cyan]prime-gate-proxy-antigravity-lik[/bold cyan] version [bold green]{__version__}[/bold green] "
                f"([italic yellow]Codename: {__codename__}[/italic yellow])\n"
                f"[dim]Engine: Python 3.11+ / FastAPI / HTTPX | Frontend: Node.js Glassmorphic Dashboard\n"
                f"Author: irhamkaraman | GitHub: https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik[/dim]"
            ),
            title="[bold white]Prime Gate Antigravity[/bold white]",
            border_style="cyan"
        ))
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", help="Show version information and exit.", callback=version_callback, is_eager=True
    )
):
    """Prime Gate Antigravity CLI Suite."""
    pass

@app.command()
def start(
    port: int = typer.Option(DEFAULT_API_PORT, "--port", "-p", help="Port to run the OpenAI API proxy on."),
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help="Host address to bind.")
):
    """Start the proxy server in the foreground."""
    import uvicorn
    from .server import app as fastapi_app

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
def quota():
    """Display real-time quota status and available model catalog."""
    active_acc = account_mgr.get_active_account()
    if not active_acc:
        console.print("[bold red]Belum ada akun terdaftar! Jalankan 'prime-gate auth import' atau 'prime-gate auth login'.[/bold red]")
        return

    tier_label = QuotaMonitor.get_tier_label(active_acc)
    rows = QuotaMonitor.parse_quota_details(active_acc)
    models = QuotaMonitor.get_available_models(active_acc)

    table = Table(title=f"Quota Status - {active_acc.get('email')} ({tier_label})", border_style="cyan")
    table.add_column("Model Family", style="bold white")
    table.add_column("Sisa Quota", justify="right")
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

    model_table = Table(title="Model Catalog yang Aktif untuk Paket Ini", border_style="magenta")
    model_table.add_column("Model ID", style="bold green")
    model_table.add_column("Display Name", style="white")
    model_table.add_column("Provider", style="dim")

    for m in models:
        model_table.add_row(m["id"], m["name"], m.get("owned_by", "google-antigravity"))

    console.print(model_table)

@auth_app.command("list")
def auth_list():
    """List all configured Google Antigravity accounts."""
    accounts = account_mgr.load_accounts()
    if not accounts:
        console.print("[yellow]Tidak ada akun yang tersimpan.[/yellow]")
        return

    table = Table(title=f"Akun Antigravity Terdaftar ({len(accounts)} akun)", border_style="green")
    table.add_column("No", justify="right")
    table.add_column("Email", style="bold white")
    table.add_column("Project ID", style="dim")
    table.add_column("Tier Terdeteksi", style="cyan")

    for idx, acc in enumerate(accounts, 1):
        tier = QuotaMonitor.get_tier_label(acc)
        table.add_row(str(idx), acc.get("email", "-"), acc.get("projectId", "-"), tier)

    console.print(table)

@auth_app.command("import")
def auth_import():
    """Import existing accounts from OpenCode config into local config."""
    count = account_mgr.import_from_opencode()
    if count > 0:
        console.print(f"[bold green]Berhasil mengimpor {count} akun dari OpenCode![/bold green]")
    else:
        console.print("[yellow]Tidak menemukan akun OpenCode atau impor gagal.[/yellow]")

@auth_app.command("login")
def auth_login(port: int = 53123):
    """Authenticate a new Google account via browser."""
    try:
        new_account = start_interactive_login(port=port)
        accounts = account_mgr.load_accounts()
        # Deduplicate by email
        accounts = [a for a in accounts if a.get("email") != new_account["email"]]
        accounts.append(new_account)
        account_mgr.save_accounts(accounts)
        console.print(f"[bold green]Login berhasil untuk akun: {new_account['email']}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Login gagal: {e}[/bold red]")

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
            f"[bold green]Daemon Berhasil Dijalankan di Background![/bold green]\n"
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
        console.print("[bold green]Semua background daemon proxy berhasil dihentikan.[/bold green]")
    else:
        console.print(f"[bold red]Gagal menghentikan daemon: {res}[/bold red]")

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
        console.print("[bold yellow]Status: STOPPED (Tidak ada daemon aktif)[/bold yellow]")

if __name__ == "__main__":
    app()
