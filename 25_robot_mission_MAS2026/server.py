# Group: XX | Date: 2026-03-16 | Members: <your names here>
"""
Visualization server using Mesa 3.x SolaraViz.

Run with:
    solara run server.py
"""

import solara
from mesa.visualization import SolaraViz, make_space_component, make_plot_component

from model import RobotMission
from objects import WasteAgent, WasteDisposalZone, RadioactivityAgent
from agents import GreenRobotAgent, YellowRobotAgent, RedRobotAgent


# ---------------------------------------------------------------------------
# Portrayal function
# ---------------------------------------------------------------------------
def agent_portrayal(agent):
    if isinstance(agent, GreenRobotAgent):
        return {"color": "limegreen", "shape": "circle", "size": 20, "zorder": 3}
    if isinstance(agent, YellowRobotAgent):
        return {"color": "gold",      "shape": "circle", "size": 20, "zorder": 3}
    if isinstance(agent, RedRobotAgent):
        return {"color": "red",       "shape": "circle", "size": 20, "zorder": 3}

    if isinstance(agent, WasteAgent):
        color_map = {"green": "darkgreen", "yellow": "orange", "red": "darkred"}
        return {"color": color_map[agent.waste_type], "shape": "rect", "size": 10, "zorder": 2}

    if isinstance(agent, WasteDisposalZone):
        return {"color": "purple", "shape": "rect", "size": 18, "zorder": 1}

    if isinstance(agent, RadioactivityAgent):
        r = agent.radioactivity
        if r < 0.33:
            color = "#90EE90"
        elif r < 0.66:
            color = "#FFFF66"
        else:
            color = "#FFA07A"
        return {"color": color, "shape": "rect", "size": 30, "zorder": 0}

    return {}


# ---------------------------------------------------------------------------
# Default model parameters
# ---------------------------------------------------------------------------
model_params = {
    "width":           {"type": "SliderInt", "value": 15, "min": 9,  "max": 30, "step": 3, "label": "Grid width"},
    "height":          {"type": "SliderInt", "value": 10, "min": 5,  "max": 20, "step": 1, "label": "Grid height"},
    "n_green_robots":  {"type": "SliderInt", "value": 2,  "min": 1,  "max": 6,  "step": 1, "label": "# Green robots"},
    "n_yellow_robots": {"type": "SliderInt", "value": 2,  "min": 1,  "max": 6,  "step": 1, "label": "# Yellow robots"},
    "n_red_robots":    {"type": "SliderInt", "value": 2,  "min": 1,  "max": 6,  "step": 1, "label": "# Red robots"},
    "n_green_waste":   {"type": "SliderInt", "value": 10, "min": 2,  "max": 30, "step": 1, "label": "# Green waste"},
    "seed":            {"type": "SliderInt", "value": 42, "min": 0,  "max": 999,"step": 1, "label": "Random seed"},
}

# ---------------------------------------------------------------------------
# Instantiate model — SolaraViz in Mesa 3.x requires an instance, not a class
# ---------------------------------------------------------------------------
model = RobotMission(seed=42)

# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
SpaceComponent = make_space_component(agent_portrayal)

WastePlot = make_plot_component(
    {"Green waste": "green", "Yellow waste": "gold", "Red waste": "red", "Total waste": "black"}
)

# ---------------------------------------------------------------------------
# SolaraViz page
# ---------------------------------------------------------------------------
page = SolaraViz(
    model,
    components=[SpaceComponent, WastePlot],
    model_params=model_params,
    name="Robot Waste Mission – MAS 2026",
)

page  # required by solara
