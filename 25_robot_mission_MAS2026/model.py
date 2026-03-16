# Group XX
# Date: 2026-03-16
# Members: Member 1, Member 2, Member 3

from __future__ import annotations

import random
from typing import Dict, Tuple, Any

from mesa import Model
from mesa.space import MultiGrid
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector

from agents import RobotAgent, GreenAgent, YellowAgent, RedAgent
from objects import Waste, RadioactivityCell, DisposalZone

Position = Tuple[int, int]


class RobotMission(Model):
    def __init__(
        self,
        width=18,
        height=10,
        n_green_robots=4,
        n_yellow_robots=3,
        n_red_robots=2,
        initial_green_waste=30,
        enable_communication=True,
        seed=None,
    ):
        super().__init__(seed=seed)

        self.width = width
        self.height = height
        self.grid = MultiGrid(width, height, torus=False)
        self.schedule = RandomActivation(self)
        self.running = True

        self.enable_communication = enable_communication
        self.current_id = 0
        self.step_count = 0
        self.total_disposed_red = 0
        self.disposal_pos = None

        self.datacollector = DataCollector(
            model_reporters={
                "Green waste on grid": lambda m: m.count_waste_on_grid("green"),
                "Yellow waste on grid": lambda m: m.count_waste_on_grid("yellow"),
                "Red waste on grid": lambda m: m.count_waste_on_grid("red"),
                "Green in inventory": lambda m: m.count_inventory("green"),
                "Yellow in inventory": lambda m: m.count_inventory("yellow"),
                "Red in inventory": lambda m: m.count_inventory("red"),
                "Disposed red": lambda m: m.total_disposed_red,
                "Total remaining units": lambda m: m.total_remaining_units(),
                "Mission complete": lambda m: int(m.is_mission_complete()),
            }
        )

        self._create_radioactivity_map()
        self._create_disposal_zone()
        self._create_initial_green_waste(initial_green_waste)
        self._create_robots(n_green_robots, n_yellow_robots, n_red_robots)

        self.datacollector.collect(self)

    def next_id(self):
        self.current_id += 1
        return self.current_id

    # ------------------------------------------------------------
    # Zones
    # ------------------------------------------------------------

    def zone_from_x(self, x):
        third = self.width // 3
        if x < third:
            return "z1"
        elif x < 2 * third:
            return "z2"
        else:
            return "z3"

    def position_in_allowed_zone(self, agent: RobotAgent, pos: Position):
        x, _ = pos
        return self.zone_from_x(x) in agent.allowed_zone_names

    # ------------------------------------------------------------
    # World creation
    # ------------------------------------------------------------

    def _create_radioactivity_map(self):
        for x in range(self.width):
            for y in range(self.height):
                zone = self.zone_from_x(x)
                if zone == "z1":
                    level = random.uniform(0.0, 0.33)
                elif zone == "z2":
                    level = random.uniform(0.33, 0.66)
                else:
                    level = random.uniform(0.66, 1.0)

                cell = RadioactivityCell(self.next_id(), self, zone, level)
                self.grid.place_agent(cell, (x, y))

    def _create_disposal_zone(self):
        x = self.width - 1
        y = random.randint(0, self.height - 1)
        self.disposal_pos = (x, y)

        dz = DisposalZone(self.next_id(), self)
        self.grid.place_agent(dz, self.disposal_pos)

    def _create_initial_green_waste(self, n):
        max_x = max(0, self.width // 3 - 1)

        for _ in range(n):
            x = random.randint(0, max_x)
            y = random.randint(0, self.height - 1)
            waste = Waste(self.next_id(), self, "green")
            self.grid.place_agent(waste, (x, y))

    def _create_robots(self, n_green, n_yellow, n_red):
        for _ in range(n_green):
            x = random.randint(0, max(0, self.width // 3 - 1))
            y = random.randint(0, self.height - 1)
            a = GreenAgent(self.next_id(), self)
            self.grid.place_agent(a, (x, y))
            self.schedule.add(a)

        for _ in range(n_yellow):
            x = random.randint(0, max(0, 2 * self.width // 3 - 1))
            y = random.randint(0, self.height - 1)
            a = YellowAgent(self.next_id(), self)
            self.grid.place_agent(a, (x, y))
            self.schedule.add(a)

        for _ in range(n_red):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            a = RedAgent(self.next_id(), self)
            self.grid.place_agent(a, (x, y))
            self.schedule.add(a)

    # ------------------------------------------------------------
    # Percepts
    # ------------------------------------------------------------

    def summarize_cell(self, pos: Position) -> Dict[str, Any]:
        contents = self.grid.get_cell_list_contents([pos])

        zone = self.zone_from_x(pos[0])
        radioactivity_level = None
        has_disposal = False
        wastes = []
        robots = []

        for obj in contents:
            if isinstance(obj, RadioactivityCell):
                zone = obj.zone
                radioactivity_level = obj.radioactivity_level
            elif isinstance(obj, DisposalZone):
                has_disposal = True
            elif isinstance(obj, Waste):
                wastes.append(obj.waste_type)
            elif isinstance(obj, RobotAgent):
                robots.append(obj.robot_type)

        return {
            "zone": zone,
            "radioactivity_level": radioactivity_level,
            "has_disposal": has_disposal,
            "wastes": wastes,
            "robots": robots,
        }

    def get_percepts(self, agent: RobotAgent):
        neighborhood = self.grid.get_neighborhood(
            agent.pos,
            moore=False,
            include_center=True
        )
        return {pos: self.summarize_cell(pos) for pos in neighborhood}

    # ------------------------------------------------------------
    # Feasibility
    # ------------------------------------------------------------

    def is_move_feasible(self, agent: RobotAgent, new_pos: Position):
        x, y = new_pos
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return self.position_in_allowed_zone(agent, new_pos)

    # ------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------

    def _move(self, agent: RobotAgent, target: Position):
        if self.is_move_feasible(agent, target):
            self.grid.move_agent(agent, target)

    def _pickup(self, agent: RobotAgent, waste_type: str):
        if len(agent.carrying) >= agent.max_inventory:
            return

        contents = self.grid.get_cell_list_contents([agent.pos])
        for obj in contents:
            if isinstance(obj, Waste) and obj.waste_type == waste_type:
                agent.carrying.append(waste_type)
                self.grid.remove_agent(obj)
                return

    def _transform(self, agent: RobotAgent, source: str, target: str):
        if agent.carrying.count(source) < 2:
            return

        removed = 0
        new_inventory = []
        for item in agent.carrying:
            if item == source and removed < 2:
                removed += 1
            else:
                new_inventory.append(item)

        agent.carrying = new_inventory

        transformed_waste = Waste(self.next_id(), self, target)
        self.grid.place_agent(transformed_waste, agent.pos)

    def _drop(self, agent: RobotAgent, waste_type: str):
        if waste_type not in agent.carrying:
            return

        contents = self.grid.get_cell_list_contents([agent.pos])
        has_disposal = any(isinstance(obj, DisposalZone) for obj in contents)

        if not has_disposal:
            return

        agent.carrying.remove(waste_type)

        if waste_type == "red":
            self.total_disposed_red += 1

    def do(self, agent: RobotAgent, action: Dict[str, Any]):
        action_type = action.get("type", "wait")

        if action_type == "move":
            target = action.get("to")
            if target is not None:
                self._move(agent, target)

        elif action_type == "pickup":
            waste_type = action.get("waste_type")
            if waste_type in {"green", "yellow", "red"}:
                self._pickup(agent, waste_type)

        elif action_type == "transform":
            source = action.get("from")
            target = action.get("to")
            if (source, target) in {("green", "yellow"), ("yellow", "red")}:
                self._transform(agent, source, target)

        elif action_type == "drop":
            waste_type = action.get("waste_type")
            if waste_type in {"green", "yellow", "red"}:
                self._drop(agent, waste_type)

        return self.get_percepts(agent)

    # ------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------

    def count_waste_on_grid(self, waste_type):
        count = 0
        for cell_content, _, _ in self.grid.coord_iter():
            for obj in cell_content:
                if isinstance(obj, Waste) and obj.waste_type == waste_type:
                    count += 1
        return count

    def count_inventory(self, waste_type):
        total = 0
        for agent in self.schedule.agents:
            if isinstance(agent, RobotAgent):
                total += agent.carrying.count(waste_type)
        return total

    def total_remaining_units(self):
        return (
            self.count_waste_on_grid("green")
            + self.count_waste_on_grid("yellow")
            + self.count_waste_on_grid("red")
            + self.count_inventory("green")
            + self.count_inventory("yellow")
            + self.count_inventory("red")
        )

    def is_mission_complete(self):
        return self.total_remaining_units() == 0

    # ------------------------------------------------------------
    # Step
    # ------------------------------------------------------------

    def step(self):
        self.step_count += 1
        self.schedule.step()
        self.datacollector.collect(self)

        if self.is_mission_complete():
            self.running = False