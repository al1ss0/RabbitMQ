import json
import sys
import urllib.error
import urllib.request
from base64 import b64encode
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

BASE_URL = "http://localhost:15672/api"
_AUTH_HEADER = {"Authorization": "Basic " + b64encode(b"guest:guest").decode()}

console = Console()


def fetch(path: str) -> Any:
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=_AUTH_HEADER)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def build_queues_table(queues: list[dict[str, Any]]) -> Table:
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Fila", style="bold")
    table.add_column("Ready", justify="right")
    table.add_column("Unacked", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Cons.", justify="right")
    table.add_column("Pub.", justify="right")
    table.add_column("Entregues", justify="right")
    table.add_column("ACK", justify="right")
    table.add_column("NACK", justify="right")
    table.add_column("Estado")

    for q in queues:
        stats: dict[str, Any] = q.get("message_stats", {})
        state = q.get("state", "-")
        state_display = f"[green]{state}[/green]" if state == "running" else f"[red]{state}[/red]"
        table.add_row(
            q["name"],
            str(q.get("messages_ready", 0)),
            str(q.get("messages_unacknowledged", 0)),
            str(q.get("messages", 0)),
            str(q.get("consumers", 0)),
            str(stats.get("publish", 0)),
            str(stats.get("deliver", 0)),
            str(stats.get("ack", 0)),
            str(stats.get("redeliver", 0)),
            state_display,
        )
    return table


def build_exchanges_table(exchanges: list[dict[str, Any]]) -> Table:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Exchange", style="bold")
    table.add_column("Tipo")
    table.add_column("Durável", justify="center")

    for e in exchanges:
        if e["name"]:
            table.add_row(
                e["name"],
                e["type"],
                "[green]✓[/green]" if e["durable"] else "[red]✗[/red]",
            )
    return table


def build_bindings_table(bindings: list[dict[str, Any]]) -> Table:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Source")
    table.add_column("Routing Key", style="yellow")
    table.add_column("Destination")

    for b in bindings:
        table.add_row(b["source"], b["routing_key"], b["destination"])
    return table


def main() -> None:
    try:
        queues: list[dict[str, Any]] = fetch("/queues")
        exchanges: list[dict[str, Any]] = fetch("/exchanges")
        bindings: list[dict[str, Any]] = fetch(
            "/bindings/%2F/e/pedidos_exchange/q/pedidos_queue"
        )
    except urllib.error.URLError as exc:
        console.print(f"[red]Erro ao conectar ao RabbitMQ Management:[/red] {exc.reason}")
        console.print("Verifique se os containers estão rodando: [bold]docker compose ps[/bold]")
        sys.exit(1)

    console.print(Panel(build_queues_table(queues), title="[bold]Filas[/bold]"))
    console.print(Panel(build_exchanges_table(exchanges), title="[bold]Exchanges[/bold]"))
    console.print(
        Panel(
            build_bindings_table(bindings) if bindings else "[yellow]Nenhum binding encontrado[/yellow]",
            title="[bold]Bindings — pedidos_exchange → pedidos_queue[/bold]",
        )
    )


if __name__ == "__main__":
    main()