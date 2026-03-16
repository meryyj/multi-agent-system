# Group XX
# Date: 2026-03-16
# Members: Member 1, Member 2, Member 3

from mesa.visualization.modules import CanvasGrid, ChartModule
from mesa.visualization.ModularVisualization import ModularServer

from model import RobotMission
from agents import GreenAgent, YellowAgent, RedAgent
from objects import Waste, DisposalZone, RadioactivityCell


def agent_portrayal(agent):
    portrayal = {
        "Shape": "circle",
        "Filled": "true",
        "Layer": 1,
        "r": 0.45,
    }

    if isinstance(agent, RadioactivityCell):
        portrayal["Shape"] = "rect"
        portrayal["Filled"] = "true"
        portrayal["Layer"] = 0
        portrayal["w"] = 1
        portrayal["h"] = 1

        if agent.zone == "z1":
            portrayal["Color"] = "#dff6dd"
        elif agent.zone == "z2":
            portrayal["Color"] = "#fff1b8"
        else:
            portrayal["Color"] = "#ffd6d6"
        return portrayal

    if isinstance(agent, DisposalZone):
        portrayal["Shape"] = "rect"
        portrayal["Filled"] = "true"
        portrayal["Layer"] = 1
        portrayal["w"] = 1
        portrayal["h"] = 1
        portrayal["Color"] = "#7db4ff"
        return portrayal

    if isinstance(agent, Waste):
        portrayal["Shape"] = "rect"
        portrayal["Filled"] = "true"
        portrayal["Layer"] = 2
        portrayal["w"] = 0.5
        portrayal["h"] = 0.5

        if agent.waste_type == "green":
            portrayal["Color"] = "green"
        elif agent.waste_type == "yellow":
            portrayal["Color"] = "gold"
        else:
            portrayal["Color"] = "red"
        return portrayal

    if isinstance(agent, GreenAgent):
        portrayal["Color"] = "#1b8f3a"
        portrayal["Layer"] = 3
        portrayal["text"] = "G"
        portrayal["text_color"] = "white"
        return portrayal

    if isinstance(agent, YellowAgent):
        portrayal["Color"] = "#d4a000"
        portrayal["Layer"] = 3
        portrayal["text"] = "Y"
        portrayal["text_color"] = "black"
        return portrayal

    if isinstance(agent, RedAgent):
        portrayal["Color"] = "#c21f1f"
        portrayal["Layer"] = 3
        portrayal["text"] = "R"
        portrayal["text_color"] = "white"
        return portrayal

    return portrayal


grid = CanvasGrid(agent_portrayal, 18, 10, 900, 500)

chart = ChartModule(
    [
        {"Label": "Green waste on grid", "Color": "green"},
        {"Label": "Yellow waste on grid", "Color": "gold"},
        {"Label": "Red waste on grid", "Color": "red"},
        {"Label": "Disposed red", "Color": "blue"},
    ],
    data_collector_name="datacollector",
)

server = ModularServer(
    RobotMission,
    [grid, chart],
    "Robot Mission MAS 2026",
    {
        "width": 18,
        "height": 10,
        "n_green_robots": 4,
        "n_yellow_robots": 3,
        "n_red_robots": 2,
        "initial_green_waste": 30,
        "enable_communication": True,
        "seed": 42,
    },
)

server.port = 8521

if __name__ == "__main__":
    print("Launching Mesa server on http://127.0.0.1:8521")
    server.launch()