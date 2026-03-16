# Group XX
# Date: 2026-03-16
# Members: Member 1, Member 2, Member 3

from mesa import Agent


class Waste(Agent):
    def __init__(self, unique_id, model, waste_type: str):
        super().__init__(unique_id, model)
        self.waste_type = waste_type  # "green", "yellow", "red"


class RadioactivityCell(Agent):
    """
    Passive object that stores:
    - the zone name (z1, z2, z3)
    - a radioactivity level
    """
    def __init__(self, unique_id, model, zone: str, radioactivity_level: float):
        super().__init__(unique_id, model)
        self.zone = zone
        self.radioactivity_level = radioactivity_level


class DisposalZone(Agent):
    """
    Passive object representing the final eastern waste disposal area.
    """
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)