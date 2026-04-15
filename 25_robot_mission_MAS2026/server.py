# Groupe : 25
# Date de creation : 2026-03-29
# Membres : [Prenoms Noms]

from mesa.visualization import SolaraViz, make_plot_component, make_space_component
from mesa.visualization.components import AgentPortrayalStyle, PropertyLayerStyle

from agents import GreenAgent, RedAgent, YellowAgent
from model import RobotMission
from objects import RadioactivityAgent, WasteAgent, WasteDisposalAgent, WasteType


def agent_portrayal(agent):
    if isinstance(agent, GreenAgent):
        return AgentPortrayalStyle(
            color="#1f9d55",
            marker="o",
            size=90 + 20 * len(agent.inventory),
            zorder=4,
            edgecolors="#0f5132",
            linewidths=1.8,
        )

    if isinstance(agent, YellowAgent):
        return AgentPortrayalStyle(
            color="#f0b429",
            marker="s",
            size=90 + 20 * len(agent.inventory),
            zorder=4,
            edgecolors="#8a6116",
            linewidths=1.8,
        )

    if isinstance(agent, RedAgent):
        return AgentPortrayalStyle(
            color="#d64545",
            marker="^",
            size=90 + 20 * len(agent.inventory),
            zorder=4,
            edgecolors="#7a1f1f",
            linewidths=1.8,
        )

    if isinstance(agent, WasteAgent):
        waste_styles = {
            WasteType.GREEN: ("#2ecc71", "h", "#1f7a4d"),
            WasteType.YELLOW: ("#f4c542", "D", "#9f7b11"),
            WasteType.RED: ("#e85d5d", "P", "#8a2323"),
        }
        color, marker, edge = waste_styles.get(
            agent.waste_type,
            ("#aaaaaa", "o", "#555555"),
        )
        return AgentPortrayalStyle(
            color=color,
            marker=marker,
            size=70,
            zorder=5,
            edgecolors=edge,
            linewidths=1.5,
        )

    if isinstance(agent, WasteDisposalAgent):
        return AgentPortrayalStyle(
            color="#111827",
            marker="X",
            size=120,
            zorder=6,
            edgecolors="#ef4444",
            linewidths=2.0,
        )

    if isinstance(agent, RadioactivityAgent):
        return AgentPortrayalStyle(
            color="#000000",
            marker="s",
            size=0,
            zorder=0,
            alpha=0.0,
        )

    return AgentPortrayalStyle(size=0, alpha=0.0)


def property_layer_portrayal(layer):
    if layer.name == "radiation_level":
        return PropertyLayerStyle(
            colormap="YlOrRd",
            alpha=0.35,
            colorbar=True,
            vmin=0.0,
            vmax=1.1,
        )
    return None


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
        "label": "Seed",
        "min": 0,
        "max": 999,
        "step": 1,
    },
}


SpaceComponent = make_space_component(
    agent_portrayal,
    propertylayer_portrayal=property_layer_portrayal,
)

WasteChart = make_plot_component(
    {
        "Green wastes": "#1f9d55",
        "Yellow wastes": "#f0b429",
        "Red wastes": "#d64545",
        "Total wastes": "#4b5563",
    }
)

MissionChart = make_plot_component(
    {
        "Wastes disposed": "#111827",
        "Known cells": "#2563eb",
    }
)

CoordinationChart = make_plot_component(
    {
        "Waste reports": "#0f766e",
        "Handoff reports": "#14b8a6",
        "Map shares": "#7c3aed",
        "Total messages": "#334155",
    }
)

ExplorationChart = make_plot_component({"Exploration ratio": "#2563eb"})

model_instance = RobotMission()

page = SolaraViz(
    model_instance,
    components=[
        SpaceComponent,
        WasteChart,
        MissionChart,
        CoordinationChart,
        ExplorationChart,
    ],
    model_params=model_params,
    name="Robot Mission MAS 2025-2026",
)
