#!/usr/bin/env python3
"""
Live dashboard to monitor ZeroPain simulation progress.
Reads the manifest.json file from the specified run directory.
"""

import sys
import time
import json
from pathlib import Path

try:
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("Rich is required. Run: pip install rich")
    sys.exit(1)

def main(run_id: str):
    run_dir = Path("runs") / run_id
    manifest_path = run_dir / "manifest.json"
    
    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}. Waiting for run to start...")

    console = Console()
    
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    )

    task_id = progress.add_task("[cyan]Simulation Progress...", total=100, completed=0)

    with Live(Panel(progress, title=f"ZeroPain Run: {run_id}", border_style="cyan"), refresh_per_second=2) as live:
        while True:
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r") as f:
                        manifest = json.load(f)
                    
                    completed = manifest.get("completed_batches", 0)
                    total = manifest.get("total_batches", 1)
                    status = manifest.get("status", "unknown")
                    
                    progress.update(task_id, completed=completed, total=total)
                    
                    if status == "complete":
                        progress.update(task_id, description="[green]Simulation Complete! 🎉")
                        break
                    elif status == "interrupted":
                        progress.update(task_id, description="[red]Simulation Interrupted 🛑")
                        break
                    else:
                        progress.update(task_id, description=f"[cyan]Simulating ({status})...")
                        
                except (json.JSONDecodeError, OSError):
                    pass
            
            time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python live_dashboard.py <run_id>")
        sys.exit(1)
    main(sys.argv[1])
