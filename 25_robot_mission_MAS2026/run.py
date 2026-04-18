# Group : 25
# Created : 2026-03-29
# Members : 
# - Mathys Bagnah
# - Xavier Plantier
# - Meriem Jelassi

import argparse
from pathlib import Path

import pandas as pd

from model import RobotMission


def build_model(args, scenario=None, seed=None):
    return RobotMission(
        grid_width=args.width,
        grid_height=args.height,
        n_green_robots=args.green_robots,
        n_yellow_robots=args.yellow_robots,
        n_red_robots=args.red_robots,
        n_green_wastes=args.wastes,
        scenario=scenario or args.scenario,
        seed=args.seed if seed is None else seed,
    )


def run_model(model, max_steps):
    for step in range(max_steps):
        model.step()
        if model.is_finished():
            return step + 1
    return max_steps


def run_batch(args):
    print("=" * 60)
    print("  Robot Mission MAS 2025-2026 - Batch mode")
    print("=" * 60)
    print(f"  Grid          : {args.width} x {args.height}")
    print(
        "  Robots        : "
        f"{args.green_robots}G / {args.yellow_robots}Y / {args.red_robots}R"
    )
    print(f"  Green wastes  : {args.wastes}")
    print(f"  Scenario      : {args.scenario}")
    print(f"  Max steps     : {args.steps}")
    print(f"  Seed          : {args.seed}")
    print("=" * 60)

    model = build_model(args)
    steps_executed = run_model(model, args.steps)
    data = model.datacollector.get_model_vars_dataframe()

    if model.is_finished():
        print(f"\n  Mission completed in {steps_executed} steps.")
    else:
        print(f"\n  Simulation stopped after {steps_executed} steps.")

    print("\n  Final metrics:")
    print(f"    Wastes disposed : {model.wastes_disposed}/{model.expected_disposed}")
    print(f"    Remaining waste : {data['Total wastes'].iloc[-1]}")
    print(f"    Carried waste   : {data['Carried wastes'].iloc[-1]}")
    print(f"    Known cells     : {data['Known cells'].iloc[-1]}")
    print(f"    Messages sent   : {data['Total messages'].iloc[-1]}")
    print(f"    Coverage ratio  : {data['Exploration ratio'].iloc[-1]:.1%}")
    print()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "run_data.csv"
    plot_path = output_dir / "main_plot.png"
    data.to_csv(csv_path, index=True)
    save_single_run_plot(data, plot_path)
    print(f"  Data saved to : {csv_path}")
    print(f"  Plot saved to : {plot_path}")

    _ascii_chart(data)


def run_comparison(args):
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for scenario in RobotMission.SCENARIOS:
        for seed in range(1, args.seeds + 1):
            model = build_model(args, scenario=scenario, seed=seed)
            steps_executed = run_model(model, args.steps)
            rows.append(
                {
                    "scenario": scenario,
                    "seed": seed,
                    "steps_executed": steps_executed,
                    "mission_complete": model.is_finished(),
                    "disposed_red": model.wastes_disposed,
                    "remaining_wastes": model.count_waste(),
                    "carried_wastes": model.count_carried_waste(),
                    "known_cells": model.known_cells(),
                    "exploration_ratio": model.exploration_ratio(),
                    "waste_reports": model.message_counters["waste_reports"],
                    "handoff_reports": model.message_counters["handoff_reports"],
                    "map_shares": model.message_counters["map_shares"],
                    "disposal_reports": model.message_counters["disposal_reports"],
                    "total_messages": model.total_messages(),
                }
            )
            status = "done" if model.is_finished() else "timeout"
            print(
                f"{scenario:18s} seed={seed:02d} {status:7s} "
                f"steps={steps_executed:4d} remaining={model.count_waste():2d} "
                f"messages={model.total_messages():4d}"
            )

    summary = pd.DataFrame(rows)
    csv_path = output_dir / "multi_seed_summary.csv"
    plot_path = output_dir / "compare_communication_multi_seed.png"
    summary.to_csv(csv_path, index=False)
    save_comparison_plot(summary, plot_path)

    print("\nComparison summary:")
    grouped = summary.groupby("scenario")
    for scenario, group in grouped:
        terminated = group[group["mission_complete"]]
        average_steps = (
            terminated["steps_executed"].mean()
            if not terminated.empty
            else float("nan")
        )
        print(
            f"  {scenario:18s} "
            f"termination={group['mission_complete'].mean():.0%} "
            f"avg_steps_done={average_steps:.1f} "
            f"avg_remaining={group['remaining_wastes'].mean():.2f} "
            f"avg_messages={group['total_messages'].mean():.1f}"
        )

    print(f"\n  Summary saved to : {csv_path}")
    print(f"  Plot saved to    : {plot_path}")


def save_single_run_plot(data, path):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    ax = axes[0, 0]
    data[["Green wastes", "Yellow wastes", "Red wastes", "Total wastes"]].plot(ax=ax)
    ax.set_title("Waste transformation pipeline")
    ax.set_xlabel("Step")
    ax.set_ylabel("Waste count")
    ax.grid(True, alpha=0.25)

    ax = axes[0, 1]
    data[["Green on grid", "Yellow on grid", "Red on grid", "Carried wastes"]].plot(ax=ax)
    ax.set_title("Grid vs carried waste")
    ax.set_xlabel("Step")
    ax.grid(True, alpha=0.25)

    ax = axes[1, 0]
    data[["Wastes disposed", "Known cells"]].plot(ax=ax)
    ax.set_title("Mission progress and exploration")
    ax.set_xlabel("Step")
    ax.grid(True, alpha=0.25)

    ax = axes[1, 1]
    data[["Waste reports", "Handoff reports", "Map shares", "Total messages"]].plot(ax=ax)
    ax.set_title("Communication counters")
    ax.set_xlabel("Step")
    ax.grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_comparison_plot(summary, path):
    import matplotlib.pyplot as plt

    grouped = summary.groupby("scenario")
    scenarios = list(grouped.groups)
    termination = [grouped.get_group(s)["mission_complete"].mean() for s in scenarios]
    avg_steps = []
    avg_messages = []
    avg_remaining = []

    for scenario in scenarios:
        group = grouped.get_group(scenario)
        terminated = group[group["mission_complete"]]
        avg_steps.append(
            terminated["steps_executed"].mean() if not terminated.empty else 0
        )
        avg_messages.append(group["total_messages"].mean())
        avg_remaining.append(group["remaining_wastes"].mean())

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))

    axes[0].bar(scenarios, termination, color=["#64748b", "#2563eb"])
    axes[0].set_ylim(0, 1.05)
    axes[0].set_title("Termination rate")
    axes[0].set_ylabel("Rate")

    axes[1].bar(scenarios, avg_steps, color=["#64748b", "#2563eb"])
    axes[1].set_title("Average steps (finished runs)")
    axes[1].set_ylabel("Steps")

    axes[2].bar(scenarios, avg_messages, color=["#64748b", "#2563eb"])
    axes[2].set_title("Average messages")
    axes[2].set_ylabel("Messages")

    for ax in axes:
        ax.tick_params(axis="x", labelrotation=20)
        ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _ascii_chart(data: pd.DataFrame):
    print("\n  Total-waste evolution:")
    total = data["Total wastes"]
    if total.empty or total.max() == 0:
        print("  (mission already clean)")
        return

    width = 50
    height = 8
    max_value = total.max()
    steps = len(total)

    print("  " + "-" * (width + 2))
    for row in range(height, 0, -1):
        threshold = max_value * row / height
        line = ""
        for col in range(width):
            idx = int(col * steps / width)
            value = total.iloc[min(idx, steps - 1)]
            line += "#" if value >= threshold else " "
        print(f"  |{line}|")
    print("  " + "-" * (width + 2))
    print(f"  Step 0{' ' * (width - 10)}Step {steps - 1}")


def run_visualization():
    import os
    import subprocess
    import sys

    try:
        import solara  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Solara is not installed. Run: py -3 -m pip install -r requirements.txt"
        ) from exc

    print("=" * 60)
    print("  Robot Mission MAS 2025-2026 - Visualization")
    print("  -> Opens http://localhost:8765 in your browser")
    print("=" * 60)

    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    subprocess.run(
        [sys.executable, "-m", "solara", "run", server_path, "--port", "8765"],
        check=True,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Robot Mission MAS 2025-2026")
    parser.add_argument("--batch", action="store_true", help="Run without interface")
    parser.add_argument("--compare", action="store_true", help="Compare both scenarios")
    parser.add_argument("--steps", type=int, default=500, help="Maximum number of steps")
    parser.add_argument("--seeds", type=int, default=10, help="Seeds used by --compare")
    parser.add_argument("--width", type=int, default=30, help="Grid width")
    parser.add_argument("--height", type=int, default=10, help="Grid height")
    parser.add_argument(
        "--scenario",
        type=str,
        default="With communication",
        choices=RobotMission.SCENARIOS,
        help="Simulation scenario",
    )
    parser.add_argument("--green-robots", type=int, default=3, help="Number of green robots")
    parser.add_argument("--yellow-robots", type=int, default=3, help="Number of yellow robots")
    parser.add_argument("--red-robots", type=int, default=3, help="Number of red robots")
    parser.add_argument(
        "--wastes",
        type=int,
        default=12,
        help="Initial green wastes; must be a multiple of 4",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results/plots",
        help="Directory for CSV files and plots",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.compare:
        run_comparison(arguments)
    elif arguments.batch:
        run_batch(arguments)
    else:
        run_visualization()
