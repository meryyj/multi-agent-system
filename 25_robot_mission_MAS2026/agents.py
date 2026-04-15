# Groupe : 25
# Date de creation : 2026-03-29
# Membres : [Prenoms Noms]

from collections import defaultdict, deque

import mesa

from model import Action
from objects import WasteType, ZoneType


class MsgType:
    WASTE_FOUND = "waste_found"
    WASTE_GONE = "waste_gone"
    DISPOSAL_FOUND = "disposal_found"
    MAP_SHARE = "map_share"


def direct_next_step(pos, target, knowledge):
    if pos == target:
        return (0, 0)

    allowed_zones = set(knowledge["allowed_zones"])
    queue = deque([(pos, [])])
    visited = {pos}

    while queue:
        (cx, cy), path = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            npos = (nx, ny)

            if npos in visited:
                continue
            if not (0 <= nx < knowledge["grid_width"] and 0 <= ny < knowledge["grid_height"]):
                continue
            if zone_from_knowledge(nx, knowledge) not in allowed_zones:
                continue

            new_path = path + [(dx, dy)]
            if npos == target:
                return new_path[0]

            visited.add(npos)
            queue.append((npos, new_path))

    return None


def zone_from_knowledge(x, knowledge):
    if x < knowledge["z1_end"]:
        return ZoneType.Z1
    if x < knowledge["z2_end"]:
        return ZoneType.Z2
    return ZoneType.Z3


class RobotAgent(mesa.Agent):
    ALLOWED_ZONES = set()
    TARGET_WASTE = None
    MAX_INVENTORY = 0
    ROLE = "robot"

    def __init__(self, model):
        super().__init__(model)
        self.inventory = []
        self.knowledge = {
            "pos": None,
            "zone": None,
            "inventory": self.inventory,
            "known_map": {},
            "target": None,
            "last_action": None,
            "step_count": 0,
            "wastes_seen": {},
            "messages_in": [],
            "disposal_pos": None,
            "visits": defaultdict(int),
            "recent_positions": deque(maxlen=6),
            "shared_targets": {},
            "shared_disposal_channels": set(),
            "last_announced_handoff": None,
            "robot_role": self.ROLE,
            "allowed_zones": tuple(sorted(self.ALLOWED_ZONES)),
            "grid_width": model.grid_width,
            "grid_height": model.grid_height,
            "z1_end": model.z1_end,
            "z2_end": model.z2_end,
            "target_waste": self.TARGET_WASTE,
            "max_inventory": self.MAX_INVENTORY,
        }

    def step_agent(self):
        percepts = self.model.do(self, {"type": Action.WAIT})
        if self.model.communication_enabled:
            self.knowledge["messages_in"] = self.model.mailbox.pop(self.unique_id, [])
        else:
            self.knowledge["messages_in"] = []
        self._update_knowledge(percepts)
        if self.model.communication_enabled:
            self._read_messages(self.knowledge)

        action = self.deliberate(self.knowledge)
        self.knowledge["last_action"] = action

        percepts = self.model.do(self, action)
        self._update_knowledge(percepts)
        if self.model.communication_enabled:
            self._announce_handoff(self.knowledge, action)
            self._broadcast(self.knowledge)
        self.knowledge["step_count"] += 1

    def _update_knowledge(self, knowledge_map):
        self.knowledge["pos"] = self.pos
        self.knowledge["visits"][self.pos] += 1
        self.knowledge["recent_positions"].append(self.pos)

        for cell_pos, cell_info in knowledge_map.items():
            if not cell_info.get("in_bounds", False):
                continue

            self.knowledge["known_map"][cell_pos] = cell_info

            if cell_pos == self.pos:
                self.knowledge["zone"] = cell_info.get("zone")

            if cell_info.get("has_disposal"):
                self.knowledge["disposal_pos"] = cell_pos

            matching = [
                waste
                for waste in cell_info.get("wastes", [])
                if waste["type"] == self.TARGET_WASTE
            ]
            if matching:
                self.knowledge["wastes_seen"][cell_pos] = matching[0]
            else:
                self.knowledge["wastes_seen"].pop(cell_pos, None)

    def _read_messages(self, knowledge):
        for msg in knowledge["messages_in"]:
            msg_type = msg.get("type")

            if msg_type == MsgType.WASTE_FOUND:
                if msg["waste"]["type"] == self.TARGET_WASTE:
                    knowledge["wastes_seen"][msg["pos"]] = msg["waste"]
            elif msg_type == MsgType.WASTE_GONE:
                knowledge["wastes_seen"].pop(msg["pos"], None)
            elif msg_type == MsgType.DISPOSAL_FOUND:
                knowledge["disposal_pos"] = msg["pos"]
            elif msg_type == MsgType.MAP_SHARE:
                for pos, cell_info in msg["map_fragment"].items():
                    knowledge["known_map"][pos] = cell_info

    def _broadcast(self, knowledge):
        same_team = self._recipient_ids(type(self))
        self._share_disposal(knowledge, same_team)
        self._share_waste_updates(knowledge, same_team)
        self._share_map_fragment(knowledge, same_team)

    def _share_disposal(self, knowledge, same_team):
        disposal_pos = knowledge["disposal_pos"]
        if disposal_pos is None:
            return

        if same_team and "team" not in knowledge["shared_disposal_channels"]:
            self._send_all(
                same_team,
                {"type": MsgType.DISPOSAL_FOUND, "pos": disposal_pos},
                "disposal_reports",
            )
            knowledge["shared_disposal_channels"].add("team")

        if isinstance(self, YellowAgent):
            red_team = self._recipient_ids(RedAgent)
            if red_team and "red_team" not in knowledge["shared_disposal_channels"]:
                self._send_all(
                    red_team,
                    {"type": MsgType.DISPOSAL_FOUND, "pos": disposal_pos},
                    "disposal_reports",
                )
                knowledge["shared_disposal_channels"].add("red_team")

    def _share_waste_updates(self, knowledge, recipients):
        current_targets = {
            pos: waste["id"] for pos, waste in knowledge["wastes_seen"].items()
        }
        shared_targets = knowledge["shared_targets"]

        for pos, waste in knowledge["wastes_seen"].items():
            if shared_targets.get(pos) != waste["id"]:
                self._send_all(
                    recipients,
                    {"type": MsgType.WASTE_FOUND, "pos": pos, "waste": waste},
                    "waste_reports",
                )

        for pos in set(shared_targets) - set(current_targets):
            self._send_all(
                recipients,
                {"type": MsgType.WASTE_GONE, "pos": pos},
                "waste_reports",
            )

        knowledge["shared_targets"] = current_targets

    def _share_map_fragment(self, knowledge, recipients):
        if not recipients or knowledge["step_count"] % 3 != 0:
            return

        known_items = list(knowledge["known_map"].items())
        priority = [
            (pos, cell_info)
            for pos, cell_info in known_items
            if cell_info.get("has_disposal") or cell_info.get("wastes")
        ]
        fallback = [
            (pos, cell_info)
            for pos, cell_info in known_items
            if pos not in {item[0] for item in priority}
        ]

        fragment_items = priority[:2]
        for item in fallback:
            fragment_items.append(item)
            if len(fragment_items) >= 5:
                break

        if fragment_items:
            self._send_all(
                recipients,
                {"type": MsgType.MAP_SHARE, "map_fragment": dict(fragment_items)},
                "map_shares",
            )

    def _announce_handoff(self, knowledge, action):
        expected_waste = None

        if isinstance(self, GreenAgent) and action["type"] == Action.TRANSFORM:
            expected_waste = WasteType.YELLOW
        elif isinstance(self, YellowAgent) and action["type"] == Action.PUT_DOWN:
            expected_waste = WasteType.RED

        if expected_waste is None:
            return

        current_cell = knowledge["known_map"].get(knowledge["pos"], {})
        handoff_waste = next(
            (
                waste
                for waste in current_cell.get("wastes", [])
                if waste["type"] == expected_waste
            ),
            None,
        )
        if handoff_waste is None:
            return

        signature = (knowledge["pos"], handoff_waste["id"])
        if signature == knowledge["last_announced_handoff"]:
            return

        recipients = self._recipient_ids_for_waste(expected_waste)
        self._send_all(
            recipients,
            {
                "type": MsgType.WASTE_FOUND,
                "pos": knowledge["pos"],
                "waste": handoff_waste,
            },
            "handoff_reports",
        )
        knowledge["last_announced_handoff"] = signature

    def _recipient_ids(self, agent_cls):
        return [
            agent.unique_id
            for agent in self.model.agents
            if isinstance(agent, agent_cls) and agent.unique_id != self.unique_id
        ]

    def _recipient_ids_for_waste(self, waste_type):
        mapping = {
            WasteType.YELLOW: YellowAgent,
            WasteType.RED: RedAgent,
        }
        agent_cls = mapping.get(waste_type)
        if agent_cls is None:
            return []
        return self._recipient_ids(agent_cls)

    def _send_all(self, recipients, msg, counter_key):
        if not recipients:
            return

        for recipient_id in recipients:
            self.model.mailbox.setdefault(recipient_id, []).append(msg)
        self.model.register_message(counter_key, len(recipients))

    def deliberate(self, knowledge):
        raise NotImplementedError

    def _navigate_to(self, knowledge, target):
        step = direct_next_step(knowledge["pos"], target, knowledge)
        if step and step != (0, 0):
            return {"type": Action.MOVE, "direction": step}
        return {"type": Action.WAIT}

    def _exploration_target_x(self, knowledge):
        if knowledge["robot_role"] == "green":
            return knowledge["z1_end"] - 1
        if knowledge["robot_role"] == "yellow":
            return knowledge["z2_end"] - 1
        if knowledge["disposal_pos"] is not None:
            return knowledge["disposal_pos"][0]
        return knowledge["grid_width"] - 1

    def _explore(self, knowledge):
        px, py = knowledge["pos"]
        target_x = self._exploration_target_x(knowledge)
        candidates = []

        for dx, dy in ((1, 0), (0, 1), (0, -1), (-1, 0)):
            nx, ny = px + dx, py + dy

            if not (0 <= nx < knowledge["grid_width"] and 0 <= ny < knowledge["grid_height"]):
                continue
            if zone_from_knowledge(nx, knowledge) not in set(knowledge["allowed_zones"]):
                continue

            cell = knowledge["known_map"].get((nx, ny), {})
            score = (
                0 if (nx, ny) not in knowledge["known_map"] else 1,
                1 if (nx, ny) in knowledge["recent_positions"] else 0,
                knowledge["visits"].get((nx, ny), 0),
                len(cell.get("robots", [])),
                abs(target_x - nx),
            )
            candidates.append((score, (dx, dy)))

        if not candidates:
            return {"type": Action.WAIT}

        best_score = min(score for score, _ in candidates)
        best_moves = [move for score, move in candidates if score == best_score]
        move = self.model.random.choice(best_moves)
        return {"type": Action.MOVE, "direction": move}

    def _pick_up_waste_here(self, knowledge):
        cell = knowledge["known_map"].get(knowledge["pos"], {})
        for waste in cell.get("wastes", []):
            if (
                waste["type"] == knowledge["target_waste"]
                and len(knowledge["inventory"]) < knowledge["max_inventory"]
            ):
                return {"type": Action.PICK_UP, "waste_id": waste["id"]}
        return None

    def _closest_target(self, knowledge):
        pos = knowledge["pos"]
        return min(
            knowledge["wastes_seen"],
            key=lambda target: abs(target[0] - pos[0]) + abs(target[1] - pos[1]),
        )

    def _inventory_count(self, knowledge, waste_type):
        return sum(1 for waste in knowledge["inventory"] if waste.waste_type == waste_type)


class GreenAgent(RobotAgent):
    ALLOWED_ZONES = {ZoneType.Z1}
    TARGET_WASTE = WasteType.GREEN
    MAX_INVENTORY = 2
    ROLE = "green"

    def deliberate(self, knowledge):
        if self._inventory_count(knowledge, WasteType.GREEN) == 2:
            return {"type": Action.TRANSFORM}

        pick_action = self._pick_up_waste_here(knowledge)
        if pick_action is not None:
            return pick_action

        if knowledge["wastes_seen"]:
            target = self._closest_target(knowledge)
            knowledge["target"] = target
            action = self._navigate_to(knowledge, target)
            if action["type"] != Action.WAIT:
                return action
            knowledge["wastes_seen"].pop(target, None)

        knowledge["target"] = None
        return self._explore(knowledge)


class YellowAgent(RobotAgent):
    ALLOWED_ZONES = {ZoneType.Z1, ZoneType.Z2}
    TARGET_WASTE = WasteType.YELLOW
    MAX_INVENTORY = 2
    ROLE = "yellow"

    def deliberate(self, knowledge):
        if self._inventory_count(knowledge, WasteType.RED) == 1:
            return {"type": Action.PUT_DOWN}

        if self._inventory_count(knowledge, WasteType.YELLOW) == 2:
            return {"type": Action.TRANSFORM}

        pick_action = self._pick_up_waste_here(knowledge)
        if pick_action is not None:
            return pick_action

        if knowledge["wastes_seen"]:
            target = self._closest_target(knowledge)
            knowledge["target"] = target
            action = self._navigate_to(knowledge, target)
            if action["type"] != Action.WAIT:
                return action
            knowledge["wastes_seen"].pop(target, None)

        knowledge["target"] = None
        return self._explore(knowledge)


class RedAgent(RobotAgent):
    ALLOWED_ZONES = {ZoneType.Z1, ZoneType.Z2, ZoneType.Z3}
    TARGET_WASTE = WasteType.RED
    MAX_INVENTORY = 1
    ROLE = "red"

    def deliberate(self, knowledge):
        has_red = self._inventory_count(knowledge, WasteType.RED) == 1
        disposal_pos = knowledge["disposal_pos"]

        if has_red and disposal_pos and knowledge["pos"] == disposal_pos:
            return {"type": Action.PUT_DOWN}

        if has_red and disposal_pos:
            knowledge["target"] = disposal_pos
            action = self._navigate_to(knowledge, disposal_pos)
            if action["type"] != Action.WAIT:
                return action

        if has_red:
            return self._explore(knowledge)

        pick_action = self._pick_up_waste_here(knowledge)
        if pick_action is not None:
            return pick_action

        if knowledge["wastes_seen"]:
            target = self._closest_target(knowledge)
            knowledge["target"] = target
            action = self._navigate_to(knowledge, target)
            if action["type"] != Action.WAIT:
                return action
            knowledge["wastes_seen"].pop(target, None)

        knowledge["target"] = None
        return self._explore(knowledge)
