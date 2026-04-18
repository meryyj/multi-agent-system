# Group : 25
# Created : 2026-03-29
# Members : 
# - Mathys Bagnah
# - Xavier Plantier
# - Meriem Jelassi

import mesa


class WasteType:
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ZoneType:
    Z1 = "z1"
    Z2 = "z2"
    Z3 = "z3"


WASTE_DISPOSAL_RADIOACTIVITY = 1.1

ZONE_RANGES = {
    ZoneType.Z1: (0.00, 0.33),
    ZoneType.Z2: (0.33, 0.66),
    ZoneType.Z3: (0.66, 1.00),
}


class RadioactivityAgent(mesa.Agent):
    """Passive marker used by robots to infer zone and danger level."""

    def __init__(self, model, zone):
        super().__init__(model)
        self.zone = zone
        low, high = ZONE_RANGES[zone]
        self.radioactivity = model.random.uniform(low, high)

    def step(self):
        pass

    def __repr__(self):
        return f"RadioactivityAgent(zone={self.zone}, radioactivity={self.radioactivity:.3f})"


class WasteDisposalAgent(mesa.Agent):
    """Passive agent that marks the final disposal cell."""

    def __init__(self, model):
        super().__init__(model)

    def step(self):
        pass

    def __repr__(self):
        return "WasteDisposalAgent()"


class WasteAgent(mesa.Agent):
    """Waste object carried, transformed, dropped, or finally destroyed."""

    def __init__(self, model, waste_type):
        super().__init__(model)
        self.waste_type = waste_type
        self.picked_up = False

    def step(self):
        pass

    def is_green(self):
        return self.waste_type == WasteType.GREEN

    def is_yellow(self):
        return self.waste_type == WasteType.YELLOW

    def is_red(self):
        return self.waste_type == WasteType.RED

    def __repr__(self):
        return f"WasteAgent(type={self.waste_type}, picked_up={self.picked_up})"
