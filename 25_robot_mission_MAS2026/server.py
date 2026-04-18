# Group : 25
# Created : 2026-03-29
# Members : 
# - Mathys Bagnah
# - Xavier Plantier
# - Meriem Jelassi

import warnings
import matplotlib.pyplot as plt

# Mesa 3.3 passes edgecolors to marker='None' agents, which matplotlib rejects.
# The rendering is unaffected, so we silence the warning.
warnings.filterwarnings("ignore", message="You passed a edgecolor")

from mesa.visualization import SolaraViz, make_plot_component, make_space_component
from mesa.visualization.components import AgentPortrayalStyle, PropertyLayerStyle

from agents import GreenAgent, RedAgent, YellowAgent
from model import RobotMission
from objects import RadioactivityAgent, WasteAgent, WasteDisposalAgent, WasteType


def property_layer_portrayal(layer):
    if layer.name == "radiation_level":
        return PropertyLayerStyle(
            colormap="RdYlGn_r",  # green (low) -> yellow -> red (high)
            alpha=0.45,
            colorbar=True,
            vmin=0.0,
            vmax=1.0,
        )
    return None


def _post_process(ax):
    # Recover grid dimensions from the axis limits set by Mesa.
    # x_min is clamped so a stray invisible agent can't skew the bounds.
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    x_min = max(-0.5, x_min)
    y_min = max(-0.5, y_min)

    w = int(round(x_max + 0.5))
    h = int(round(y_max + 0.5))
    if w <= 0:
        w = 30
    if h <= 0:
        h = 10

    # Dashed cell grid lines at zorder=0, behind agents (zorder=1).
    for xi in range(1, w):
        ax.axvline(xi - 0.5, color="#888888", linewidth=0.5, linestyle="--", zorder=0)
    for yi in range(1, h):
        ax.axhline(yi - 0.5, color="#888888", linewidth=0.5, linestyle="--", zorder=0)

    ax.add_patch(
        plt.Rectangle(
            (-0.5, -0.5), w, h,
            fill=False, edgecolor="#555555", linewidth=1.5, zorder=0,
        )
    )

    ax.set_aspect("equal", adjustable="box")
    ax.grid(False)

    # Show every ~10th column label to avoid crowding on wide grids.
    step_x = max(1, w // 10)
    ax.set_xticks(range(0, w, step_x))
    ax.set_yticks(range(0, h))
    ax.tick_params(colors="#444444", labelsize=7, length=3)

    ax.set_title("")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#aaaaaa")
    ax.spines["bottom"].set_color("#aaaaaa")


def agent_portrayal(agent):
    # RadioactivityAgents fill every cell and exist only to expose zone/radiation
    # data to robots via percepts. We use marker='None' so Mesa skips rendering
    # them — they must still return a style object (returning None crashes Mesa).
    if isinstance(agent, RadioactivityAgent):
        return AgentPortrayalStyle(
            marker="None",
            size=0.001,
            zorder=0,
        )

    # Robots — colored squares, size grows with inventory load.
    if isinstance(agent, GreenAgent):
        n = len(agent.inventory)
        return AgentPortrayalStyle(
            color="#0b3d20",
            marker="s",
            size=320 + 60 * n,
            zorder=1,
            edgecolors="#ffffff",
            linewidths=1.6,
        )

    if isinstance(agent, YellowAgent):
        n = len(agent.inventory)
        return AgentPortrayalStyle(
            color="#d68910",
            marker="s",
            size=320 + 60 * n,
            zorder=1,
            edgecolors="#ffffff",
            linewidths=1.6,
        )

    if isinstance(agent, RedAgent):
        n = len(agent.inventory)
        return AgentPortrayalStyle(
            color="#7b241c",
            marker="s",
            size=340 + 60 * n,
            zorder=1,
            edgecolors="#ffffff",
            linewidths=1.6,
        )

    # Wastes — small circles, color matches their danger level.
    if isinstance(agent, WasteAgent):
        styles = {
            WasteType.GREEN:  ("#2ecc71", "o", "#1e8449", 18),
            WasteType.YELLOW: ("#f1c40f", "o", "#b9770e", 18),
            WasteType.RED:    ("#e74c3c", "o", "#922b21", 18),
        }
        color, marker, edge, size = styles.get(
            agent.waste_type,
            ("#cccccc", "o", "#888888", 18),
        )
        return AgentPortrayalStyle(
            color=color,
            marker=marker,
            size=size,
            zorder=1,
            edgecolors=edge,
            linewidths=1.5,
        )

    # Disposal site — fixed position at the far right of the grid.
    if isinstance(agent, WasteDisposalAgent):
        return AgentPortrayalStyle(
            color="#111111",
            marker="X",
            size=260,
            zorder=1,
            edgecolors="#c0392b",
            linewidths=2.0,
        )

    return AgentPortrayalStyle(size=0.001, alpha=0.0)


SpaceComponent = make_space_component(
    agent_portrayal,
    propertylayer_portrayal=property_layer_portrayal,
    post_process=_post_process,
    draw_grid=False,
)


def _chart_style(ax):
    ax.set_facecolor("#ffffff")
    ax.grid(True, axis="y", color="#ebebeb", linewidth=0.8)
    ax.grid(False, axis="x")
    ax.tick_params(colors="#666666", labelsize=8)
    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#dddddd")
    ax.spines["bottom"].set_color("#dddddd")

    # At step 0 there is only one data point, so matplotlib auto-scales to a
    # tiny range around 0. Force sensible minimums to avoid negative x values.
    x_left, x_right = ax.get_xlim()
    ax.set_xlim(left=max(0, x_left), right=max(1, x_right))
    _, y_top = ax.get_ylim()
    if y_top < 1:
        ax.set_ylim(bottom=0, top=max(1, y_top))

    legend = ax.legend(fontsize=8, frameon=True)
    if legend:
        legend.get_frame().set_edgecolor("#e6e6e6")
        legend.get_frame().set_facecolor("#ffffff")
        legend.get_frame().set_alpha(0.95)


WasteChart = make_plot_component(
    {
        "Green wastes":  "#0b3d20",
        "Yellow wastes": "#d68910",
        "Red wastes":    "#7b241c",
        "Total wastes":  "#95a5a6",
    },
    post_process=_chart_style,
)

MissionChart = make_plot_component(
    {
        "Wastes disposed":   "#2c3e50",
        "Exploration ratio": "#2e86c1",
    },
    post_process=_chart_style,
)

CoordinationChart = make_plot_component(
    {
        "Waste reports":   "#17a589",
        "Handoff reports": "#3498db",
        "Map shares":      "#8e44ad",
        "Total messages":  "#7f8c8d",
    },
    post_process=_chart_style,
)


model_params = {
    "scenario": {
        "type": "Select",
        "value": "With communication",
        "label": "Scenario",
        "values": list(RobotMission.SCENARIOS),
    },
    "grid_width": {
        "type": "SliderInt",
        "value": 30,
        "label": "Grid width",
        "min": 9,
        "max": 60,
        "step": 3,
    },
    "grid_height": {
        "type": "SliderInt",
        "value": 10,
        "label": "Grid height",
        "min": 3,
        "max": 20,
        "step": 1,
    },
    "n_green_robots": {
        "type": "SliderInt",
        "value": 3,
        "label": "Green robots",
        "min": 1,
        "max": 10,
        "step": 1,
    },
    "n_yellow_robots": {
        "type": "SliderInt",
        "value": 3,
        "label": "Yellow robots",
        "min": 1,
        "max": 10,
        "step": 1,
    },
    "n_red_robots": {
        "type": "SliderInt",
        "value": 3,
        "label": "Red robots",
        "min": 1,
        "max": 10,
        "step": 1,
    },
    "n_green_wastes": {
        "type": "SliderInt",
        "value": 12,
        "label": "Initial green wastes",
        "min": 4,
        "max": 40,
        "step": 4,
    },
    "seed": {
        "type": "SliderInt",
        "value": 42,
        "label": "Random seed",
        "min": 0,
        "max": 999,
        "step": 1,
    },
}


model_instance = RobotMission()

page = SolaraViz(
    model_instance,
    components=[
        SpaceComponent,
        WasteChart,
        MissionChart,
        CoordinationChart,
    ],
    model_params=model_params,
    name="Robot Mission MAS 2025-2026",
)
