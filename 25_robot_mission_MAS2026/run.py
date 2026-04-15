# Group: XX | Date: 2026-03-16 | Members: <your names here>
"""
run.py – headless simulation runner.

Usage:
    python run.py                     # default parameters
    python run.py --steps 200 --seed 0
"""

import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from model import RobotMission


def run_simulation(
    steps: int = 300,
    width: int = 15,
    height: int = 10,
    n_green_robots: int = 2,
    n_yellow_robots: int = 2,
    n_red_robots: int = 2,
    n_green_waste: int = 10,
    seed: int = 42,
    output_chart: str = "waste_over_time.png",
):
    print(f"[RobotMission] Starting simulation | seed={seed} | steps={steps}")
    model = RobotMission(
        width=width,
        height=height,
        n_green_robots=n_green_robots,
        n_yellow_robots=n_yellow_robots,
        n_red_robots=n_red_robots,
        n_green_waste=n_green_waste,
        seed=seed,
    )

    for i in range(steps):
        if not model.running:
            print(f"  → Mission complete at step {i}!")
            break
        model.step()
        if (i + 1) % 50 == 0:
            df = model.datacollector.get_model_vars_dataframe()
            last = df.iloc[-1]
            print(f"  Step {i+1:4d} | green={int(last['Green waste'])} "
                  f"yellow={int(last['Yellow waste'])} red={int(last['Red waste'])}")

    # ---- Plot results ----
    df = model.datacollector.get_model_vars_dataframe()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df["Green waste"],  color="green",  label="Green waste")
    ax.plot(df.index, df["Yellow waste"], color="goldenrod", label="Yellow waste")
    ax.plot(df.index, df["Red waste"],    color="red",    label="Red waste")
    ax.plot(df.index, df["Total waste"],  color="black",  label="Total waste", linewidth=2, linestyle="--")
    ax.set_xlabel("Step")
    ax.set_ylabel("Number of waste objects in the grid")
    ax.set_title("Robot Waste Mission – waste count over time")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_chart, dpi=120)
    print(f"[RobotMission] Chart saved → {output_chart}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps",          type=int, default=300)
    parser.add_argument("--width",          type=int, default=15)
    parser.add_argument("--height",         type=int, default=10)
    parser.add_argument("--green-robots",   type=int, default=2)
    parser.add_argument("--yellow-robots",  type=int, default=2)
    parser.add_argument("--red-robots",     type=int, default=2)
    parser.add_argument("--green-waste",    type=int, default=10)
    parser.add_argument("--seed",           type=int, default=42)
    parser.add_argument("--output",         type=str, default="waste_over_time.png")
    args = parser.parse_args()

    run_simulation(
        steps=args.steps,
        width=args.width,
        height=args.height,
        n_green_robots=args.green_robots,
        n_yellow_robots=args.yellow_robots,
        n_red_robots=args.red_robots,
        n_green_waste=args.green_waste,
        seed=args.seed,
        output_chart=args.output,
    )
