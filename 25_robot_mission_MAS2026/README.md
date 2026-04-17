# Robot Mission MAS 2025-2026

This folder contains the final delivery for group 25 on the "Self-organization of robots in a hostile environment" project.

## Files

- `agents.py`: robot classes, knowledge base, deliberation, communication, anti-deadlock logic.
- `objects.py`: passive objects for radioactivity, wastes, and disposal zone.
- `model.py`: environment, action execution, feasibility checks, and metrics.
- `run.py`: batch mode, multi-seed comparison, CSV export, and plots.
- `server.py`: Mesa + Solara visualization.
- `requirements.txt`: Python dependencies.
- `results/plots/`: generated CSV files and figures.

## Implemented expectations

- Three zones with different radioactivity levels.
- Three robot types with movement constraints:
  - green robots stay in `z1`
  - yellow robots stay in `z1` and `z2`
  - red robots can cross all zones
- Transformation chain:
  - 2 green -> 1 yellow
  - 2 yellow -> 1 red
  - 1 red -> disposed in the final storage cell
- Agent loop split into:
  - percepts
  - deliberate
  - do
- Two scenarios:
  - `No communication`
  - `With communication`
- Data extraction and plots.
- Interactive visualization.

## Strategy

Robots maintain a local knowledge dictionary updated from adjacent-cell percepts. To keep the mission solvable even with several robots of the same type, the implementation uses:

- memorized waste locations,
- fixed handoff points on zone borders,
- cooldown after dropping a single waste,
- a release rule when a robot keeps one waste for too long,
- optional message sharing in the communication scenario.

The communication scenario shares:

- discovered target wastes,
- new handoff wastes created on border cells,
- the disposal position,
- compact map fragments.

## Install

```bash
py -3 -m pip install -r requirements.txt
```

## Run

Batch mode:

```bash
py -3 run.py --batch --steps 500 --scenario "With communication"
```

Comparison on multiple seeds:

```bash
py -3 run.py --compare --steps 500 --seeds 10
```

Visualization:

```bash
py -3 run.py
```

The visualization should open on `http://localhost:8765`.

## Generated outputs

The main generated files are written to `results/plots/`:

- `run_data.csv`
- `main_plot.png`
- `multi_seed_summary.csv`
- `compare_communication_multi_seed.png`

## Current benchmark on the default model

Command used:

```bash
py -3 run.py --compare --steps 500 --seeds 10
```

Observed summary:

- `No communication`: 100% termination, average 244.0 steps.
- `With communication`: 100% termination, average 161.2 steps, average 1070.2 messages.

So the communication-enabled model is faster while keeping full completion on the tested seeds.

## Submission note

The folder `reference_self_org_robots_in_host_env/` was cloned only as an inspection reference and is not part of the deliverable. Submit the `25_robot_mission_MAS2026` folder.
