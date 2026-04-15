# Group: XX | Date: 2026-03-16 | Members: <your names here>

import random
from mesa import Agent


class RadioactivityAgent(Agent):
    """
    Passive agent placed on every cell to encode zone membership
    and radioactivity level. Robots read this to know their zone.

    Radioactivity ranges:
        z1 (low)    -> [0.00, 0.33)
        z2 (medium) -> [0.33, 0.66)
        z3 (high)   -> [0.66, 1.00]
    """

    def __init__(self, model, zone: int):
        super().__init__(model)
        self.zone = zone  # 1, 2 or 3
        if zone == 1:
            self.radioactivity = random.uniform(0.0, 0.33)
        elif zone == 2:
            self.radioactivity = random.uniform(0.33, 0.66)
        else:
            self.radioactivity = random.uniform(0.66, 1.0)

    def step(self):
        pass  # No behaviour


class WasteDisposalZone(Agent):
    """
    Passive marker agent that identifies the easternmost column(s)
    as the waste disposal zone. Robots drop red waste here.
    """

    def __init__(self, model):
        super().__init__(model)

    def step(self):
        pass  # No behaviour


class WasteAgent(Agent):
    """
    Passive object representing a piece of waste.
    waste_type: "green" | "yellow" | "red"
    """

    COLORS = {"green": "green", "yellow": "yellow", "red": "red"}

    def __init__(self, model, waste_type: str):
        super().__init__(model)
        assert waste_type in ("green", "yellow", "red")
        self.waste_type = waste_type

    def step(self):
        pass  # No behaviour

    def __repr__(self):
        return f"Waste({self.waste_type})"
