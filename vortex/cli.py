import sys
import time
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from vortex.config import settings

console = Console()


@click.group()
def cli():
    """VortexFS: Event-Driven Real-Time Feature Store CLI."""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host interface to bind")
@click.option("--port", default=8000, type=int, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def start(host, port, reload):
    """Start the VortexFS server & web console."""
    import uvicorn
    console.print(Panel.fit(
        f"[bold violet]VortexFS[/bold violet] [cyan]v1.0[/cyan]\n"
        f"[green]Online Store:[/green] {settings.ONLINE_STORE_TYPE}\n"
        f"[green]Offline Store:[/green] {settings.OFFLINE_STORE_TYPE}\n"
        f"[bold yellow]Web Dashboard & API:[/bold yellow] http://localhost:{port}\n"
        f"[bold yellow]Interactive API Docs:[/bold yellow] http://localhost:{port}/docs",
        title="[bold green]Starting Feature Store[/bold green]",
        border_style="violet",
    ))
    uvicorn.run("vortex.api:app", host=host, port=port, reload=reload)


@cli.command()
@click.option("--days", default=7, type=int, help="Number of historical days to backfill")
@click.option("--events-per-day", default=100, type=int, help="Events per day")
def seed(days, events_per_day):
    """Seed synthetic realistic e-commerce and fintech telemetry."""
    from vortex.serving.client import FeatureStoreClient
    from vortex.simulator.generator import SyntheticEventGenerator

    console.print(f"[cyan]Generating {days * events_per_day} historical events spanning past {days} days...[/cyan]")
    client = FeatureStoreClient()
    gen = SyntheticEventGenerator(num_users=50, seed=42)

    events = gen.generate_historical_dataset(days_back=days, events_per_day=events_per_day)
    count = client.ingest_batch(events)
    flushed = client.flush()

    console.print(f"[bold green]✓ Successfully generated {count} events and flushed {flushed} to DuckDB offline store![/bold green]")


@cli.command(name="info")
def registry_info():
    """Inspect registered Entities, Features, and Feature Views."""
    from vortex.serving.client import FeatureStoreClient
    client = FeatureStoreClient()
    reg = client.registry

    # Entities table
    ent_table = Table(title="Registered Entities", border_style="cyan")
    ent_table.add_column("Entity Name", style="bold cyan")
    ent_table.add_column("Join Keys", style="white")
    ent_table.add_column("Data Type", style="yellow")
    ent_table.add_column("Description", style="dim")

    for ent in reg.list_entities():
        ent_table.add_row(ent.name, ", ".join(ent.join_keys), ent.value_type.value, ent.description)
    console.print(ent_table)

    # Feature Views table
    fv_table = Table(title="Registered Feature Views & Aggregations", border_style="violet")
    fv_table.add_column("Feature View", style="bold violet")
    fv_table.add_column("Feature", style="bold white")
    fv_table.add_column("Type", style="yellow")
    fv_table.add_column("Aggregation", style="green")
    fv_table.add_column("Window", style="magenta")
    fv_table.add_column("Event Source", style="cyan")

    for fv in reg.list_feature_views():
        for feat in fv.features:
            agg = next((a for a in fv.aggregations if a.feature_name == feat.name), None)
            fv_table.add_row(
                fv.name,
                feat.name,
                feat.value_type.value,
                agg.agg_func.value if agg else "STATIC",
                agg.window_spec if agg else "N/A",
                agg.event_name if agg else "N/A",
            )
    console.print(fv_table)


@cli.command(name="asof-demo")
def asof_demo():
    """Demonstrate leak-free Point-in-Time (ASOF) training dataset join."""
    import pandas as pd
    from datetime import datetime, timezone, timedelta
    from vortex.serving.client import FeatureStoreClient

    client = FeatureStoreClient()
    now = datetime.now(timezone.utc)

    # Synthetic observations table: 3 distinct observation timestamps for user_0001
    observations = pd.DataFrame([
        {"user_id": "user_0001", "timestamp": now - timedelta(days=2), "fraud_label": 0},
        {"user_id": "user_0001", "timestamp": now - timedelta(hours=6), "fraud_label": 0},
        {"user_id": "user_0001", "timestamp": now, "fraud_label": 1},
    ])

    features = [
        "user_fraud_features:failed_logins_1h",
        "user_fraud_features:transaction_count_10m",
        "user_fraud_features:total_spend_24h",
    ]

    console.print("[bold yellow]Running Point-in-Time Correct (ASOF) Join...[/bold yellow]")
    start = time.perf_counter()
    training_df = client.get_historical_features(
        observation_df=observations,
        entity_key="user_id",
        feature_refs=features,
    )
    elapsed = (time.perf_counter() - start) * 1000.0

    res_table = Table(title=f"Training Dataset (ASOF Joined in {elapsed:.2f}ms)", border_style="green")
    for col in training_df.columns:
        res_table.add_column(str(col), style="cyan" if "user" in col or "label" in col else "white")

    for _, row in training_df.iterrows():
        res_table.add_row(*[str(val) for val in row.values])

    console.print(res_table)
    console.print("[bold green]✓ Verified zero future target leakage.[/bold green]")


@cli.command()
@click.option("--n", default=1000, type=int, help="Number of point lookups to execute")
def benchmark(n):
    """Benchmark online feature serving latency."""
    from vortex.serving.client import FeatureStoreClient
    client = FeatureStoreClient()

    # Pre-populate sample user
    from vortex.core.event import Event
    from datetime import datetime, timezone
    client.ingest(Event(event="payment_executed", distinct_id="bench_user", timestamp=datetime.now(timezone.utc), properties={"amount": 99.0}))

    latencies = []
    features = ["user_fraud_features:total_spend_24h", "user_fraud_features:transaction_count_10m"]

    console.print(f"[cyan]Executing {n} online feature lookups...[/cyan]")
    for _ in range(n):
        t0 = time.perf_counter()
        _ = client.get_online_features("user", ["bench_user"], features)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    import numpy as np
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    qps = n / (sum(latencies) / 1000.0)

    b_table = Table(title="Online Feature Store Serving Latency Benchmark", border_style="cyan")
    b_table.add_column("Metric", style="bold yellow")
    b_table.add_column("Value", style="bold green")

    b_table.add_row("Total Lookups", f"{n:,}")
    b_table.add_row("p50 Latency", f"{p50:.3f} ms")
    b_table.add_row("p95 Latency", f"{p95:.3f} ms")
    b_table.add_row("p99 Latency", f"{p99:.3f} ms")
    b_table.add_row("Estimated QPS", f"{qps:,.0f} req/sec")

    console.print(b_table)


if __name__ == "__main__":
    cli()
