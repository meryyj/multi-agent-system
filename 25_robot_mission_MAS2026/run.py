# Group XX
# Date: 2026-03-16
# Members: Member 1, Member 2, Member 3

import os
import pandas as pd
import matplotlib.pyplot as plt

from model import RobotMission


def ensure_dirs():
    os.makedirs("results/plots", exist_ok=True)
    os.makedirs("results/screenshots", exist_ok=True)


def run_experiment(communication=True, steps=250, seed=42):
    model = RobotMission(
        width=18,
        height=10,
        n_green_robots=4,
        n_yellow_robots=3,
        n_red_robots=2,
        initial_green_waste=30,
        enable_communication=communication,
        seed=seed,
    )

    for _ in range(steps):
        if not model.running:
            break
        model.step()

    df = model.datacollector.get_model_vars_dataframe()
    return model, df


def plot_main(df, filename):
    plt.figure(figsize=(10, 6))
    plt.plot(df["Green waste on grid"], label="Green waste")
    plt.plot(df["Yellow waste on grid"], label="Yellow waste")
    plt.plot(df["Red waste on grid"], label="Red waste")
    plt.plot(df["Disposed red"], label="Disposed red")
    plt.xlabel("Step")
    plt.ylabel("Count")
    plt.title("Waste evolution over time")
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()


def multi_seed_summary(seeds, communication=True, steps=250):
    rows = []

    for seed in seeds:
        model, df = run_experiment(
            communication=communication,
            steps=steps,
            seed=seed
        )

        rows.append({
            "seed": seed,
            "communication": communication,
            "steps_executed": len(df),
            "disposed_red": model.total_disposed_red,
            "mission_complete": model.is_mission_complete(),
            "remaining_units": model.total_remaining_units(),
        })

    return pd.DataFrame(rows)


def compare_comm_multi_seed(seeds, steps=250):
    df_no = multi_seed_summary(seeds, communication=False, steps=steps)
    df_yes = multi_seed_summary(seeds, communication=True, steps=steps)

    summary = pd.concat([df_no, df_yes], ignore_index=True)
    summary.to_csv("results/plots/multi_seed_summary.csv", index=False)

    avg_no = df_no["disposed_red"].mean()
    avg_yes = df_yes["disposed_red"].mean()

    plt.figure(figsize=(8, 5))
    plt.bar(["No communication", "With communication"], [avg_no, avg_yes])
    plt.ylabel("Average disposed red waste")
    plt.title("Average performance across seeds")
    plt.tight_layout()
    plt.savefig("results/plots/compare_communication_multi_seed.png")
    plt.close()

    return df_no, df_yes, summary


def main():
    ensure_dirs()

    model, df = run_experiment(communication=True, steps=500, seed=42)

    print("Simulation finished")
    print("Steps executed:", len(df))
    print("Disposed red:", model.total_disposed_red)
    print("Mission complete:", model.is_mission_complete())
    print("Remaining units:", model.total_remaining_units())

    df.to_csv("results/plots/run_data.csv", index=False)
    plot_main(df, "results/plots/main_plot.png")

    seeds = [1, 2, 3, 4, 5]
    df_no, df_yes, summary = compare_comm_multi_seed(seeds, steps=500)

    print("\nMulti-seed summary:")
    print(summary)

    print("\nAverage disposed red without communication:", df_no["disposed_red"].mean())
    print("Average disposed red with communication:", df_yes["disposed_red"].mean())

    print("\nSaved:")
    print("- results/plots/run_data.csv")
    print("- results/plots/main_plot.png")
    print("- results/plots/multi_seed_summary.csv")
    print("- results/plots/compare_communication_multi_seed.png")


if __name__ == "__main__":
    main()