# Group : 25
# Created : 2026-03-29
# Members : 
# - Mathys Bagnah
# - Xavier Plantier
# - Meriem Jelassi

import mesa

from objects import (
    RadioactivityAgent,
    WasteAgent,
    WasteDisposalAgent,
    WasteType,
    ZoneType,
    WASTE_DISPOSAL_RADIOACTIVITY,
)


class Action:
    MOVE = "move"
    PICK_UP = "pick_up"
    TRANSFORM = "transform"
    PUT_DOWN = "put_down"
    WAIT = "wait"


class RobotMission(mesa.Model):
    """Agent-based model for the hostile-environment robot mission."""

    SCENARIOS = ("No communication", "With communication")

    def __init__(
        self,
        *,
        grid_width=30,
        grid_height=10,
        n_green_robots=3,
        n_yellow_robots=3,
        n_red_robots=3,
        n_green_wastes=12,
        scenario="With communication",
        seed=None,
    ):
        if grid_width % 3 != 0:
            raise ValueError("grid_width must be a multiple of 3 to keep balanced zones.")
        if n_green_wastes % 4 != 0:
            raise ValueError(
                "n_green_wastes must be a multiple of 4: 4 green wastes become 1 disposed red waste."
            )
        if scenario not in self.SCENARIOS:
            raise ValueError(f"scenario must be one of {self.SCENARIOS}.")

        super().__init__(seed=seed)

        self.grid_width = grid_width
        self.grid_height = grid_height
        self.n_green_wastes = n_green_wastes
        self.scenario_name = scenario
        self.communication_enabled = scenario == "With communication"
        self.total_cells = grid_width * grid_height
        self.running = True
        self.step_count = 0

        self.z1_end = grid_width // 3
        self.z2_end = 2 * grid_width // 3

        self.wastes_disposed = 0
        self.expected_disposed = n_green_wastes // 4
        self.mailbox = {}
        self.message_counters = {
            "waste_reports": 0,
            "handoff_reports": 0,
            "map_shares": 0,
            "disposal_reports": 0,
        }

        self.radiation_layer = mesa.space.PropertyLayer(
            "radiation_level",
            grid_width,
            grid_height,
            0.0,
            dtype=float,
        )
        self.grid = mesa.space.MultiGrid(
            grid_width,
            grid_height,
            torus=False,
            property_layers=[self.radiation_layer],
        )

        self._place_radioactivity()
        self._place_waste_disposal()
        self._place_wastes(n_green_wastes)
        self._place_robots(n_green_robots, n_yellow_robots, n_red_robots)

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Step": lambda m: m.step_count,
                "Green wastes": lambda m: m.count_waste(WasteType.GREEN),
                "Yellow wastes": lambda m: m.count_waste(WasteType.YELLOW),
                "Red wastes": lambda m: m.count_waste(WasteType.RED),
                "Total wastes": lambda m: m.count_waste(),
                "Green on grid": lambda m: m.count_waste_on_grid(WasteType.GREEN),
                "Yellow on grid": lambda m: m.count_waste_on_grid(WasteType.YELLOW),
                "Red on grid": lambda m: m.count_waste_on_grid(WasteType.RED),
                "Carried wastes": lambda m: m.count_carried_waste(),
                "Wastes disposed": lambda m: m.wastes_disposed,
                "Mission complete": lambda m: int(m.is_finished()),
                "Known cells": lambda m: m.known_cells(),
                "Exploration ratio": lambda m: m.exploration_ratio(),
                "Waste reports": lambda m: m.message_counters["waste_reports"],
                "Handoff reports": lambda m: m.message_counters["handoff_reports"],
                "Map shares": lambda m: m.message_counters["map_shares"],
                "Disposal reports": lambda m: m.message_counters["disposal_reports"],
                "Total messages": lambda m: m.total_messages(),
            }
        )
        self.datacollector.collect(self)

    def _zone_of(self, x):
        if x < self.z1_end:
            return ZoneType.Z1
        if x < self.z2_end:
            return ZoneType.Z2
        return ZoneType.Z3

    def _place_radioactivity(self):
        for x in range(self.grid_width):
            for y in range(self.grid_height):
                zone = self._zone_of(x)
                agent = RadioactivityAgent(self, zone)
                self.grid.place_agent(agent, (x, y))
                self.radiation_layer.set_cell((x, y), agent.radioactivity)

    def _place_waste_disposal(self):
        x = self.grid_width - 1
        y = self.random.randint(0, self.grid_height - 1)
        self.disposal_pos = (x, y)

        for agent in self.grid.get_cell_list_contents([self.disposal_pos]):
            if isinstance(agent, RadioactivityAgent):
                agent.radioactivity = WASTE_DISPOSAL_RADIOACTIVITY
                self.radiation_layer.set_cell(self.disposal_pos, agent.radioactivity)
                break

        self.grid.place_agent(WasteDisposalAgent(self), self.disposal_pos)

    def _place_wastes(self, n_wastes):
        z1_cells = [
            (x, y)
            for x in range(self.z1_end)
            for y in range(self.grid_height)
        ]
        for pos in self.random.sample(z1_cells, min(n_wastes, len(z1_cells))):
            self.grid.place_agent(WasteAgent(self, WasteType.GREEN), pos)

    def _place_robots(self, n_green, n_yellow, n_red):
        from agents import GreenAgent, RedAgent, YellowAgent

        for _ in range(n_green):
            pos = (
                self.random.randint(0, self.z1_end - 1),
                self.random.randint(0, self.grid_height - 1),
            )
            self.grid.place_agent(GreenAgent(self), pos)

        for _ in range(n_yellow):
            pos = (
                self.random.randint(0, self.z2_end - 1),
                self.random.randint(0, self.grid_height - 1),
            )
            self.grid.place_agent(YellowAgent(self), pos)

        for _ in range(n_red):
            pos = (
                self.random.randint(self.z1_end, self.grid_width - 1),
                self.random.randint(0, self.grid_height - 1),
            )
            self.grid.place_agent(RedAgent(self), pos)

    def register_message(self, category, amount=1):
        if category in self.message_counters:
            self.message_counters[category] += amount

    def total_messages(self):
        return sum(self.message_counters.values())

    def do(self, agent, action):
        action_type = action.get("type")

        if action_type == Action.MOVE:
            self._do_move(agent, action)
        elif action_type == Action.PICK_UP:
            self._do_pick_up(agent, action)
        elif action_type == Action.TRANSFORM:
            self._do_transform(agent)
        elif action_type == Action.PUT_DOWN:
            self._do_put_down(agent, action)

        return self._build_percepts(agent)

    def _do_move(self, agent, action):
        dx, dy = action.get("direction", (0, 0))
        cx, cy = agent.pos
        nx, ny = cx + dx, cy + dy

        if abs(dx) + abs(dy) != 1:
            return
        if not (0 <= nx < self.grid_width and 0 <= ny < self.grid_height):
            return
        if not self._can_enter(agent, nx):
            return

        self.grid.move_agent(agent, (nx, ny))

    def _can_enter(self, agent, x):
        from agents import GreenAgent, RedAgent, YellowAgent

        zone = self._zone_of(x)
        if isinstance(agent, GreenAgent):
            return zone == ZoneType.Z1
        if isinstance(agent, YellowAgent):
            return zone in (ZoneType.Z1, ZoneType.Z2)
        if isinstance(agent, RedAgent):
            return True
        return False

    def _do_pick_up(self, agent, action):
        from agents import GreenAgent, RedAgent, YellowAgent

        waste_id = action.get("waste_id")
        waste = next(
            (
                other
                for other in self.grid.get_cell_list_contents([agent.pos])
                if isinstance(other, WasteAgent) and other.unique_id == waste_id
            ),
            None,
        )
        if waste is None or waste.picked_up:
            return

        if isinstance(agent, GreenAgent):
            feasible = (
                waste.waste_type == WasteType.GREEN
                and all(item.waste_type == WasteType.GREEN for item in agent.inventory)
                and len(agent.inventory) < 2
            )
        elif isinstance(agent, YellowAgent):
            feasible = (
                waste.waste_type == WasteType.YELLOW
                and all(item.waste_type == WasteType.YELLOW for item in agent.inventory)
                and len(agent.inventory) < 2
            )
        elif isinstance(agent, RedAgent):
            feasible = waste.waste_type == WasteType.RED and len(agent.inventory) == 0
        else:
            feasible = False

        if not feasible:
            return

        waste.picked_up = True
        self.grid.remove_agent(waste)
        agent.inventory.append(waste)

    def _do_transform(self, agent):
        from agents import GreenAgent, YellowAgent

        if isinstance(agent, GreenAgent):
            required_type = WasteType.GREEN
            produced_type = WasteType.YELLOW
        elif isinstance(agent, YellowAgent):
            required_type = WasteType.YELLOW
            produced_type = WasteType.RED
        else:
            return

        matching = [waste for waste in agent.inventory if waste.waste_type == required_type]
        if len(matching) < 2:
            return

        for waste in matching[:2]:
            agent.inventory.remove(waste)
            waste.remove()

        produced = WasteAgent(self, produced_type)
        produced.picked_up = True
        agent.inventory.append(produced)

    def _do_put_down(self, agent, action):
        from agents import RedAgent

        requested_type = action.get("waste_type")
        waste = next(
            (
                item
                for item in agent.inventory
                if requested_type is None or item.waste_type == requested_type
            ),
            None,
        )
        if waste is None:
            return

        agent.inventory.remove(waste)

        if (
            isinstance(agent, RedAgent)
            and agent.pos == self.disposal_pos
            and waste.waste_type == WasteType.RED
        ):
            self.wastes_disposed += 1
            waste.remove()
            return

        waste.picked_up = False
        self.grid.place_agent(waste, agent.pos)

    def _build_percepts(self, agent):
        cx, cy = agent.pos
        neighbors = [(cx, cy), (cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]
        percepts = {}

        for nx, ny in neighbors:
            if not (0 <= nx < self.grid_width and 0 <= ny < self.grid_height):
                percepts[(nx, ny)] = {"in_bounds": False}
                continue

            contents = self.grid.get_cell_list_contents([(nx, ny)])
            radio_agent = next(
                (other for other in contents if isinstance(other, RadioactivityAgent)),
                None,
            )
            wastes = [other for other in contents if isinstance(other, WasteAgent)]
            robots = [other for other in contents if hasattr(other, "inventory")]
            has_disposal = any(isinstance(other, WasteDisposalAgent) for other in contents)

            percepts[(nx, ny)] = {
                "in_bounds": True,
                "radioactivity": radio_agent.radioactivity if radio_agent else None,
                "zone": radio_agent.zone if radio_agent else None,
                "wastes": [
                    {"id": waste.unique_id, "type": waste.waste_type}
                    for waste in wastes
                ],
                "has_disposal": has_disposal,
                "robots": [
                    {"id": robot.unique_id, "type": type(robot).__name__}
                    for robot in robots
                ],
            }

        return percepts

    def step(self):
        if not self.running:
            return

        robots = [agent for agent in self.agents if hasattr(agent, "step_agent")]
        self.random.shuffle(robots)

        for robot in robots:
            robot.step_agent()

        self.step_count += 1
        self.running = not self.is_finished()
        self.datacollector.collect(self)

    def count_waste(self, waste_type=None):
        return sum(
            1
            for agent in self.agents
            if isinstance(agent, WasteAgent)
            and (waste_type is None or agent.waste_type == waste_type)
        )

    def count_waste_on_grid(self, waste_type=None):
        return sum(
            1
            for agent in self.agents
            if isinstance(agent, WasteAgent)
            and not agent.picked_up
            and (waste_type is None or agent.waste_type == waste_type)
        )

    def count_carried_waste(self):
        return sum(
            len(agent.inventory)
            for agent in self.agents
            if hasattr(agent, "inventory")
        )

    def known_cells(self):
        known = set()
        for agent in self.agents:
            if hasattr(agent, "knowledge"):
                known.update(agent.knowledge["known_map"].keys())
        return len(known)

    def exploration_ratio(self):
        if self.total_cells == 0:
            return 0.0
        return self.known_cells() / self.total_cells

    def is_finished(self):
        return not any(isinstance(agent, WasteAgent) for agent in self.agents)
