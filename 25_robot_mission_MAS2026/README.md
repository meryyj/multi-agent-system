# Self-Organization of Robotic Agents in Hostile Environments

**Group 25** — Mathys Bagnah, Xavier Plantier, Meriem Jelassi

---

## 1. Introduction

This project simulates a team of heterogeneous robots tasked with collecting, transforming, and disposing of hazardous waste in a radioactive environment. Each robot type has a distinct role and zone restriction, and operates autonomously following the perceive–deliberate–act loop from agent-based modeling. Two scenarios are compared: one where robots act independently without any inter-agent communication, and one where they share information to coordinate their actions.

---

## 2. Repository Structure

```
25_robot_mission_MAS2026/
├── agents.py      — Robot classes (GreenAgent, YellowAgent, RedAgent) with deliberation and communication logic
├── model.py       — RobotMission model: environment setup, action execution, data collection
├── objects.py     — Passive agents: RadioactivityAgent, WasteAgent, WasteDisposalAgent
├── server.py      — Solara visualization server
└── run.py         — CLI entry point (batch run, scenario comparison, visualization launcher)
```

---

## 3. Running the Simulation

**Install dependencies**

```sh
pip install -r requirements.txt
```

**Interactive visualization** — opens `http://localhost:8765`:

```sh
python run.py
```

**Headless single run** — prints metrics and saves a CSV + plot to `results/plots/`:

```sh
python run.py --batch --scenario "With communication" --steps 500
```

**Compare both scenarios over multiple seeds**:

```sh
python run.py --compare --seeds 20 --steps 500
```

**Available CLI options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--width` | 30 | Grid width (multiple of 3) |
| `--height` | 10 | Grid height |
| `--green-robots` | 3 | Number of green robots |
| `--yellow-robots` | 3 | Number of yellow robots |
| `--red-robots` | 3 | Number of red robots |
| `--wastes` | 12 | Initial green wastes (multiple of 4) |
| `--scenario` | `"With communication"` | `"No communication"` or `"With communication"` |
| `--seed` | 42 | Random seed |
| `--steps` | 500 | Max steps before timeout |
| `--output-dir` | `results/plots` | Output directory for CSV and PNG |

---

## 4. Environment

The grid is divided into three equal vertical zones:

| Zone | Radioactivity | Robots allowed |
|------|--------------|----------------|
| Z1 (west) | 0.00 – 0.33 | Green, Yellow, Red |
| Z2 (middle) | 0.33 – 0.66 | Yellow, Red |
| Z3 (east) | 0.66 – 1.00 | Red only |

Each cell contains a `RadioactivityAgent` whose radioactivity value is drawn uniformly within the zone's range. Robots read this value from their percepts to determine which zone they occupy. The waste disposal site is a single cell on the easternmost column, identified by a special radioactivity value of 1.1.

**Waste transformation chain:**

```
2 × green  →  1 yellow   (GreenAgent transforms)
2 × yellow →  1 red      (YellowAgent transforms)
1 × red    →  disposed   (RedAgent deposits at disposal site)
```

Starting from `n` green wastes (must be a multiple of 4), the expected number of red wastes disposed is `n / 4`.

---

## 5. Agent Design

All robot types inherit from `RobotAgent`, which implements the perceive–deliberate–act loop:

```python
def step_agent(self):
    percepts = self.model.do(self, {"type": Action.WAIT})   # perceive current cell
    self._update_knowledge(percepts)
    action = self.deliberate(self.knowledge)                 # reason
    percepts = self.model.do(self, action)                   # act and observe result
    self._update_knowledge(percepts)
```

### 5.1 Knowledge Base

`deliberate()` receives a single `knowledge` dictionary and is not allowed to access any external state. The dictionary contains:

- `pos`, `zone` — current position and zone
- `inventory` — list of held `WasteAgent` objects
- `known_map` — all cells observed so far, keyed by `(x, y)`
- `wastes_seen` — positions of target-type wastes still believed present
- `visits` — per-cell visit counter, used by the exploration heuristic
- `disposal_pos` — disposal site position (filled on first observation)
- `drop_cooldowns` — cells where the robot recently dropped a waste; suppresses re-pickup for `DROP_COOLDOWN = 24` steps to avoid infinite loops
- `single_hold_steps` — number of consecutive steps holding exactly one target waste; triggers a forced drop after `SINGLE_HOLD_LIMIT = 8` steps to break deadlocks

### 5.2 Deliberation Priority

`deliberate(knowledge)` follows a fixed priority order, shared across all robot types:

1. **Deliver produced waste** — if carrying a transformed waste, navigate to the handoff column (or to the disposal site for red robots) and put it down.
2. **Transform** — if holding two target wastes, transform immediately.
3. **Pick up** — if standing on a target waste with available inventory capacity, pick it up.
4. **Go to known waste** — navigate toward the closest previously seen target waste.
5. **Deadlock release** — if `single_hold_steps` exceeds the limit, drop the single waste at the handoff column so a teammate can collect it.
6. **Explore** — move to the least-visited neighboring cell within the allowed zone, biased toward the expected waste source column.

The handoff column alternates between two x-positions every 35 steps to spread drops and reduce congestion.

### 5.3 Robot Types

| Class | Allowed zones | Collects | Transforms into | Max inventory |
|-------|--------------|---------|----------------|--------------|
| `GreenAgent` | Z1 | green waste | yellow (2→1) | 2 |
| `YellowAgent` | Z1, Z2 | yellow waste | red (2→1) | 2 |
| `RedAgent` | Z1, Z2, Z3 | red waste | — (disposes) | 1 |

---

## 6. Communication Protocol

When the scenario is `"With communication"`, robots broadcast messages through a central mailbox managed by the model. Each robot consumes its inbox at the start of its turn.

**Message types:**

| Type | Sender | Recipients | Purpose |
|------|--------|-----------|---------|
| `WASTE_FOUND` | Any robot spotting a target waste | Same-type teammates | Share waste position and ID |
| `WASTE_GONE` | Any robot whose previously shared waste disappeared | Same-type teammates | Invalidate stale target |
| `DISPOSAL_FOUND` | First robot to observe the disposal site | Same-type teammates | Propagate disposal position |
| `MAP_SHARE` | Every robot every 4 steps | Same-type teammates | Up to 6 observed cells (cells with wastes or the disposal site take priority) |

**Handoff notification:** after dropping a yellow or red waste at the zone boundary, the robot sends a `WASTE_FOUND` message directly to the next robot tier (green → yellow, yellow → red). This allows downstream robots to navigate straight to the drop location instead of finding it by exploration.

The model tracks message volumes in four counters (`waste_reports`, `handoff_reports`, `map_shares`, `disposal_reports`), all visible in the coordination chart.

---

## 7. Visualization

Run `python run.py` and open `http://localhost:8765`.

### Grid

The grid is rendered as a matplotlib figure with:

- **Radiation heatmap** — `RdYlGn_r` colormap at 45 % opacity (green = low radiation in Z1, red = high radiation in Z3), making the three zones immediately readable.
- **Robot markers** — colored squares; the marker size grows with inventory load (base 320 pt², +60 pt² per carried waste).
  - Dark green `#0b3d20` — GreenAgent
  - Amber `#d68910` — YellowAgent
  - Dark red `#7b241c` — RedAgent
- **Waste markers** — small circles (18 pt²) colored by type: green `#2ecc71`, yellow `#f1c40f`, red `#e74c3c`.
- **Disposal site** — black `✕` marker with red outline at the easternmost column.
- **Dashed grid lines** at every cell boundary.

### Real-time Charts

Three charts update on every simulation step:

| Chart | Metrics displayed |
|-------|------------------|
| **Waste distribution** | Green, yellow, red and total waste counts |
| **Mission progress** | Cumulative wastes disposed and exploration coverage ratio |
| **Coordination** | Waste reports, handoff reports, map shares, total messages |

---

## 8. Results

The table below comes from a default-parameter run (`30×10` grid, 3 robots per type, 12 initial green wastes, 500 max steps, 10 seeds):

| Scenario | Termination rate | Avg steps (finished runs) | Avg total messages |
|----------|-----------------|--------------------------|-------------------|
| No communication | 100 % | ~185 | 0 |
| With communication | 100 % | ~135 | ~980 |

> Run `python run.py --compare --seeds 10` to get proper multi-seed averages for both scenarios.

The communication scenario benefits primarily from the handoff notification: instead of downstream robots discovering a dropped waste through exploration, they receive a direct pointer and navigate there immediately.

The no-communication scenario relies on the deadlock-prevention mechanism: a robot holding a single waste for more than `SINGLE_HOLD_LIMIT` steps drops it at the handoff column, giving other robots a chance to collect and combine it.

---

## 9. Generated Outputs

`python run.py --batch` and `python run.py --compare` write to `results/plots/`:

| File | Contents |
|------|---------|
| `run_data.csv` | Per-step model metrics for a single run |
| `main_plot.png` | Four-panel chart: waste pipeline, grid vs. carried, mission progress, communication |
| `multi_seed_summary.csv` | Per-seed results for both scenarios |
| `compare_communication_multi_seed.png` | Bar charts comparing termination rate, average steps, and messages |
