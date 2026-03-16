from mesa import Agent
import random


class Waste(Agent):
    """
    Waste object (green, yellow, red)
    """

    def __init__(self, unique_id, model, waste_type):
        super().__init__(unique_id, model)
        self.type = waste_type   # "green", "yellow", "red"



class Radioactivity(Agent):
    """
    Radioactivity agent indicating the zone level
    """

    def __init__(self, unique_id, model, zone):
        super().__init__(unique_id, model)

        self.zone = zone

        if zone == "z1":
            self.level = random.uniform(0, 0.33)
        elif zone == "z2":
            self.level = random.uniform(0.33, 0.66)
        else:
            self.level = random.uniform(0.66, 1)



class DisposalZone(Agent):
    """
    Final storage zone for red waste
    """

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.is_disposal = True