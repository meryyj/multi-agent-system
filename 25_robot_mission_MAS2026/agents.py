# Group XX
# Date: 2026-03-16
# Members: Member 1, Member 2, Member 3

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any

from mesa import Agent


Position = Tuple[int, int]
Action = Dict[str, Any]
Percepts = Dict[Position, Dict[str, Any]]


class RobotAgent(Agent):
    robot_type = "base_robot"
    allowed_zone_names = set()
    pickup_type = None
    transform_from = None
    transform_to = None
    max_inventory = 2
    knowledge_ttl = 20

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

        self.carrying: List[str] = []

        self.knowledge: Dict[str, Any] = {
            "last_percepts": {},
            "known_map": {},          # pos -> {"zone": ..., "has_disposal": ..., "radioactivity": ...}
            "known_wastes": {},       # pos -> {"types": [...], "last_seen": step}
            "visited": {},            # pos -> number of visits
            "disposal_pos": None,
            "disposal_last_seen": None,
            "history": [],
        }

        self.inbox: List[Dict[str, Any]] = []

    # ------------------------------------------------------------
    # Perception and knowledge
    # ------------------------------------------------------------

    def percepts(self) -> Percepts:
        return self.model.get_percepts(self)

    def update_knowledge(self, percepts: Percepts) -> None:
        self.knowledge["last_percepts"] = percepts
        self.knowledge["visited"][self.pos] = self.knowledge["visited"].get(self.pos, 0) + 1

        self.knowledge["history"].append({
            "step": self.model.step_count,
            "pos": self.pos,
            "inventory": list(self.carrying),
        })

        for pos, info in percepts.items():
            self.knowledge["known_map"][pos] = {
                "zone": info.get("zone"),
                "has_disposal": info.get("has_disposal", False),
                "radioactivity": info.get("radioactivity_level"),
            }

            if info.get("has_disposal", False):
                self.knowledge["disposal_pos"] = pos
                self.knowledge["disposal_last_seen"] = self.model.step_count

            wastes = info.get("wastes", [])
            if wastes:
                self.knowledge["known_wastes"][pos] = {
                    "types": list(wastes),
                    "last_seen": self.model.step_count,
                }
            else:
                self.knowledge["known_wastes"].pop(pos, None)

        self.forget_old_information()

    def forget_old_information(self) -> None:
        current_step = self.model.step_count

        old_positions = []
        for pos, info in self.knowledge["known_wastes"].items():
            if current_step - info["last_seen"] > self.knowledge_ttl:
                old_positions.append(pos)

        for pos in old_positions:
            self.knowledge["known_wastes"].pop(pos, None)

        disposal_last_seen = self.knowledge.get("disposal_last_seen")
        if disposal_last_seen is not None:
            if current_step - disposal_last_seen > self.knowledge_ttl:
                self.knowledge["disposal_pos"] = None
                self.knowledge["disposal_last_seen"] = None

    def receive_messages(self) -> None:
        while self.inbox:
            msg = self.inbox.pop(0)

            if msg["type"] == "waste_info":
                pos = msg["pos"]
                waste_type = msg["waste_type"]

                current = self.knowledge["known_wastes"].get(
                    pos,
                    {"types": [], "last_seen": self.model.step_count}
                )

                if waste_type not in current["types"]:
                    current["types"].append(waste_type)
                current["last_seen"] = self.model.step_count
                self.knowledge["known_wastes"][pos] = current

            elif msg["type"] == "disposal_info":
                self.knowledge["disposal_pos"] = msg["pos"]
                self.knowledge["disposal_last_seen"] = self.model.step_count

        self.forget_old_information()

    # ------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------

    def nearby_robot_agents(self) -> List["RobotAgent"]:
        positions = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=True)
        robots = []

        for pos in positions:
            for obj in self.model.grid.get_cell_list_contents([pos]):
                if isinstance(obj, RobotAgent) and obj is not self:
                    robots.append(obj)

        return robots

    def send_message(self, receiver: "RobotAgent", message: Dict[str, Any]) -> None:
        receiver.inbox.append(message)

    def broadcast_useful_information(self) -> None:
        if not self.model.enable_communication:
            return

        neighbors = self.nearby_robot_agents()

        if self.knowledge["disposal_pos"] is not None:
            for robot in neighbors:
                self.send_message(robot, {
                    "type": "disposal_info",
                    "pos": self.knowledge["disposal_pos"],
                })

        for pos, info in self.knowledge["known_wastes"].items():
            if self.model.step_count - info["last_seen"] <= self.knowledge_ttl:
                for waste_type in info["types"]:
                    for robot in neighbors:
                        self.send_message(robot, {
                            "type": "waste_info",
                            "pos": pos,
                            "waste_type": waste_type,
                        })

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def current_cell_info(self) -> Dict[str, Any]:
        return self.knowledge["last_percepts"].get(self.pos, {})

    def waste_here(self, waste_type: str) -> bool:
        return waste_type in self.current_cell_info().get("wastes", [])

    def on_disposal_zone(self) -> bool:
        return self.current_cell_info().get("has_disposal", False)

    def inventory_count(self, waste_type: str) -> int:
        return self.carrying.count(waste_type)

    def can_pickup_more(self) -> bool:
        return len(self.carrying) < self.max_inventory

    def has_transform_material(self) -> bool:
        return (
            self.transform_from is not None
            and self.inventory_count(self.transform_from) >= 2
        )

    def feasible_neighbors(self) -> List[Position]:
        neighbors = self.model.grid.get_neighborhood(self.pos, moore=False, include_center=False)
        return [p for p in neighbors if self.model.is_move_feasible(self, p)]

    def move_toward(self, target: Position) -> Action:
        candidates = self.feasible_neighbors()
        if not candidates:
            return {"type": "wait"}

        tx, ty = target

        def dist(p):
            return abs(p[0] - tx) + abs(p[1] - ty)

        best = min(candidates, key=dist)
        return {"type": "move", "to": best}

    def explore_action(self) -> Action:
        candidates = self.feasible_neighbors()
        if not candidates:
            return {"type": "wait"}

        def score(p):
            visits = self.knowledge["visited"].get(p, 0)
            east_bonus = p[0] * 0.05
            return visits - east_bonus

        best = min(candidates, key=score)
        return {"type": "move", "to": best}

    def find_known_waste(self, waste_type: str) -> Optional[Position]:
        valid_targets = []

        for pos, info in self.knowledge["known_wastes"].items():
            is_fresh = self.model.step_count - info["last_seen"] <= self.knowledge_ttl
            if is_fresh and waste_type in info["types"] and self.model.position_in_allowed_zone(self, pos):
                valid_targets.append(pos)

        if not valid_targets:
            return None

        x, y = self.pos
        return min(valid_targets, key=lambda p: abs(p[0] - x) + abs(p[1] - y))

    # ------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------

    def deliberate(self, knowledge: Dict[str, Any]) -> Action:
        return {"type": "wait"}

    def step(self) -> None:
        percepts = self.percepts()
        self.update_knowledge(percepts)
        self.receive_messages()

        action = self.deliberate(self.knowledge)
        new_percepts = self.model.do(self, action)
        self.update_knowledge(new_percepts)

        self.broadcast_useful_information()


class GreenAgent(RobotAgent):
    robot_type = "green_robot"
    allowed_zone_names = {"z1"}
    pickup_type = "green"
    transform_from = "green"
    transform_to = "yellow"
    max_inventory = 2

    def deliberate(self, knowledge: Dict[str, Any]) -> Action:
        if self.has_transform_material():
            return {"type": "transform", "from": "green", "to": "yellow"}

        if self.can_pickup_more() and self.waste_here("green"):
            return {"type": "pickup", "waste_type": "green"}

        target = self.find_known_waste("green")
        if target is not None and target != self.pos:
            return self.move_toward(target)

        return self.explore_action()


class YellowAgent(RobotAgent):
    robot_type = "yellow_robot"
    allowed_zone_names = {"z1", "z2"}
    pickup_type = "yellow"
    transform_from = "yellow"
    transform_to = "red"
    max_inventory = 2

    def deliberate(self, knowledge: Dict[str, Any]) -> Action:
        if self.has_transform_material():
            return {"type": "transform", "from": "yellow", "to": "red"}

        if self.can_pickup_more() and self.waste_here("yellow"):
            return {"type": "pickup", "waste_type": "yellow"}

        target = self.find_known_waste("yellow")
        if target is not None and target != self.pos:
            return self.move_toward(target)

        return self.explore_action()


class RedAgent(RobotAgent):
    robot_type = "red_robot"
    allowed_zone_names = {"z1", "z2", "z3"}
    pickup_type = "red"
    transform_from = None
    transform_to = None
    max_inventory = 1

    def deliberate(self, knowledge: Dict[str, Any]) -> Action:
        if "red" in self.carrying and self.on_disposal_zone():
            return {"type": "drop", "waste_type": "red"}

        if self.can_pickup_more() and self.waste_here("red"):
            return {"type": "pickup", "waste_type": "red"}

        if "red" in self.carrying:
            disposal_pos = knowledge.get("disposal_pos")
            if disposal_pos is not None:
                return self.move_toward(disposal_pos)

        target = self.find_known_waste("red")
        if target is not None and target != self.pos:
            return self.move_toward(target)

        return self.explore_action()