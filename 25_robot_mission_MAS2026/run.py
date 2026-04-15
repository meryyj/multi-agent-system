# Groupe : 25
# Date de creation : 2026-03-29
# Membres : [Prenoms Noms]

import argparse
from pathlib import Path

import pandas as pd

from model import RobotMission


def run_batch(args):
    print("=" * 55)
    print("  Robot Mission MAS 2025-2026 - Batch mode")
    print("=" * 55)
    print(f"  Grid          : {args.width} x {args.height}")
    print(
        "  Robots        : "
        f"{args.green_robots}G / {args.yellow_robots}Y / {args.red_robots}R"
    )
    print(f"  Green wastes  : {args.wastes}")
    print(f"  Scenario      : {args.scenario}")
    print(f"  Max steps     : {args.steps}")
    print(f"  Seed          : {args.seed}")
    print("=" * 55)

    model = RobotMission(
        grid_width=args.width,
        grid_height=args.height,
        n_green_robots=args.green_robots,
        n_yellow_robots=args.yellow_robots,
        n_red_robots=args.red_robots,
        n_green_wastes=args.wastes,
        scenario=args.scenario,
        seed=args.seed,
    )

    for step in range(args.steps):
        model.step()
        if model.is_finished():
            print(f"\n  Mission completed in {step + 1} steps.")
            break
    else:
        print(f"\n  Simulation stopped after {args.steps} steps.")

    data = model.datacollector.get_model_vars_dataframe()

    print("\n  Final metrics:")
    print(f"    Wastes disposed : {model.wastes_disposed}")
    print(f"    Remaining waste : {data['Total wastes'].iloc[-1]}")
    print(f"    Known cells     : {data['Known cells'].iloc[-1]}")
    print(f"    Messages sent   : {data['Total messages'].iloc[-1]}")
    print(f"    Coverage ratio  : {data['Exploration ratio'].iloc[-1]:.1%}")
    print()

    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "run_data.csv"
    data.to_csv(csv_path, index=True)
    print(f"  Data saved to : {csv_path}")

    _ascii_chart(data)


def _ascii_chart(data: pd.DataFrame):
    print("\n  Total-waste evolution:")
    total = data["Total wastes"]
    if total.empty or total.max() == 0:
        print("  (no data)")
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

    print("=" * 55)
    print("  Robot Mission MAS 2025-2026 - Visualization")
    print("  -> Opens http://localhost:8765 in your browser")
    print("=" * 55)

    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    subprocess.run(
        [sys.executable, "-m", "solara", "run", server_path, "--port", "8765"],
        check=True,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Robot Mission MAS 2025-2026")
    parser.add_argument("--batch", action="store_true", help="Run without interface")
    parser.add_argument("--steps", type=int, default=300, help="Number of batch steps")
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
        help="Number of initial green wastes (must be a multiple of 4)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.batch:
        run_batch(arguments)
    else:
        run_visualization()
