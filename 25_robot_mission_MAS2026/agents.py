# Group : 25
# Created : 2026-03-29
# Members : 
# - Mathys Bagnah
# - Xavier Plantier
# - Meriem Jelassi

from collections import defaultdict, deque

import mesa

from model import Action
from objects import WasteType, ZoneType


class MsgType:
    WASTE_FOUND = "waste_found"
    WASTE_GONE = "waste_gone"
    DISPOSAL_FOUND = "disposal_found"
    MAP_SHARE = "map_share"


MOVE_ORDER = ((1, 0), (0, 1), (0, -1), (-1, 0))


def zone_from_knowledge(x, knowledge):
    if x < knowledge["z1_end"]:
        return ZoneType.Z1
    if x < knowledge["z2_end"]:
        return ZoneType.Z2
    return ZoneType.Z3


def direct_next_step(pos, target, knowledge):
    """Return the first step of a shortest path inside the robot allowed zones."""
    if pos == target:
        return (0, 0)

    allowed_zones = set(knowledge["allowed_zones"])
    queue = deque([(pos, [])])
    visited = {pos}

    while queue:
        (cx, cy), path = queue.popleft()
        for dx, dy in MOVE_ORDER:
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


class RobotAgent(mesa.Agent):
    """Base class shared by the three robot types.

    The public decision method is deliberate(knowledge). It only reads and mutates the
    explicit knowledge dictionary, so the reasoning step remains inspectable.
    """

    ALLOWED_ZONES = set()
    TARGET_WASTE = None
    PRODUCED_WASTE = None
    MAX_TARGET_INVENTORY = 0
    ROLE = "robot"
    SINGLE_HOLD_LIMIT = 8
    DROP_COOLDOWN = 24

    def __init__(self, model):
        super().__init__(model)
        self.inventory = []
        self.knowledge = {
            "pos": None,
            "zone": None,
            "inventory": self.inventory,
            "known_map": {},
            "target": None,
            "last_action": {"type": Action.WAIT},
            "step_count": 0,
            "wastes_seen": {},
            "messages_in": [],
            "disposal_pos": None,
            "visits": defaultdict(int),
            "recent_positions": deque(maxlen=8),
            "shared_targets": {},
            "shared_disposal": False,
            "last_announced_handoff": None,
            "single_hold_steps": 0,
            "drop_cooldowns": {},
            "robot_role": self.ROLE,
            "allowed_zones": tuple(sorted(self.ALLOWED_ZONES)),
            "grid_width": model.grid_width,
            "grid_height": model.grid_height,
            "z1_end": model.z1_end,
            "z2_end": model.z2_end,
            "target_waste": self.TARGET_WASTE,
            "produced_waste": self.PRODUCED_WASTE,
            "max_target_inventory": self.MAX_TARGET_INVENTORY,
        }

    def step_agent(self):
        percepts = self.model.do(self, {"type": Action.WAIT})
        self.knowledge["messages_in"] = (
            self.model.mailbox.pop(self.unique_id, [])
            if self.model.communication_enabled
            else []
        )
        self._update_knowledge(percepts)
        if self.model.communication_enabled:
            self._read_messages(self.knowledge)

        action = self.deliberate(self.knowledge)
        self.knowledge["last_action"] = action

        percepts = self.model.do(self, action)
        self._update_knowledge(percepts)
        self._after_action(action)
        if self.model.communication_enabled:
            self._announce_handoff(self.knowledge, action)
            self._broadcast(self.knowledge)
        self.knowledge["step_count"] += 1

    def _update_knowledge(self, percepts):
        self.knowledge["pos"] = self.pos
        self.knowledge["visits"][self.pos] += 1
        self.knowledge["recent_positions"].append(self.pos)
        self._decay_drop_cooldowns()

        for cell_pos, cell_info in percepts.items():
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
            if matching and cell_pos not in self.knowledge["drop_cooldowns"]:
                self.knowledge["wastes_seen"][cell_pos] = matching[0]
            elif cell_pos in self.knowledge["wastes_seen"]:
                self.knowledge["wastes_seen"].pop(cell_pos, None)

    def _after_action(self, action):
        target_count = self._inventory_count(self.knowledge, self.TARGET_WASTE)
        produced_count = (
            self._inventory_count(self.knowledge, self.PRODUCED_WASTE)
            if self.PRODUCED_WASTE is not None
            else 0
        )

        if target_count == 1 and produced_count == 0:
            self.knowledge["single_hold_steps"] += 1
        else:
            self.knowledge["single_hold_steps"] = 0

        if (
            action.get("type") == Action.PUT_DOWN
            and action.get("waste_type") == self.TARGET_WASTE
        ):
            self.knowledge["drop_cooldowns"][self.pos] = self.DROP_COOLDOWN
            self.knowledge["wastes_seen"].pop(self.pos, None)

    def _decay_drop_cooldowns(self):
        expired = []
        for pos, remaining in self.knowledge["drop_cooldowns"].items():
            if remaining <= 1:
                expired.append(pos)
            else:
                self.knowledge["drop_cooldowns"][pos] = remaining - 1
        for pos in expired:
            self.knowledge["drop_cooldowns"].pop(pos, None)

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
        if knowledge["disposal_pos"] is None or knowledge["shared_disposal"]:
            return
        self._send_all(
            same_team,
            {"type": MsgType.DISPOSAL_FOUND, "pos": knowledge["disposal_pos"]},
            "disposal_reports",
        )
        knowledge["shared_disposal"] = True

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
        if not recipients or knowledge["step_count"] % 4 != 0:
            return

        known_items = list(knowledge["known_map"].items())
        priority = [
            (pos, cell_info)
            for pos, cell_info in known_items
            if cell_info.get("has_disposal") or cell_info.get("wastes")
        ]
        priority_positions = {pos for pos, _ in priority}
        fallback = [
            (pos, cell_info)
            for pos, cell_info in known_items
            if pos not in priority_positions
        ]

        fragment_items = priority[:3]
        for item in fallback:
            fragment_items.append(item)
            if len(fragment_items) >= 6:
                break

        if fragment_items:
            self._send_all(
                recipients,
                {"type": MsgType.MAP_SHARE, "map_fragment": dict(fragment_items)},
                "map_shares",
            )

    def _announce_handoff(self, knowledge, action):
        if action.get("type") != Action.PUT_DOWN:
            return

        produced_waste = action.get("waste_type")
        if produced_waste not in (WasteType.YELLOW, WasteType.RED):
            return

        current_cell = knowledge["known_map"].get(knowledge["pos"], {})
        handoff_waste = next(
            (
                waste
                for waste in current_cell.get("wastes", [])
                if waste["type"] == produced_waste
            ),
            None,
        )
        if handoff_waste is None:
            return

        signature = (knowledge["pos"], handoff_waste["id"])
        if signature == knowledge["last_announced_handoff"]:
            return

        recipients = self._recipient_ids_for_waste(produced_waste)
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

    def _target_count(self, knowledge):
        return self._inventory_count(knowledge, knowledge["target_waste"])

    def _produced_count(self, knowledge):
        produced_waste = knowledge["produced_waste"]
        if produced_waste is None:
            return 0
        return self._inventory_count(knowledge, produced_waste)

    def _inventory_count(self, knowledge, waste_type):
        return sum(1 for waste in knowledge["inventory"] if waste.waste_type == waste_type)

    def _handoff_x(self, knowledge):
        if knowledge["robot_role"] == "green":
            return knowledge["z1_end"] - 1
        if knowledge["robot_role"] == "yellow":
            return knowledge["z2_end"] - 1
        return knowledge["grid_width"] - 1

    def _handoff_pos(self, knowledge):
        return (self._handoff_x(knowledge), knowledge["grid_height"] // 2)

    def _source_x(self, knowledge):
        if knowledge["robot_role"] == "green":
            if (knowledge["step_count"] // 35) % 2 == 0:
                return max(0, knowledge["z1_end"] // 2)
            return knowledge["z1_end"] - 1
        if knowledge["robot_role"] == "yellow":
            if (knowledge["step_count"] // 35) % 2 == 0:
                return knowledge["z1_end"] - 1
            return knowledge["z2_end"] - 1
        if (knowledge["step_count"] // 45) % 2 == 0:
            return knowledge["z2_end"] - 1
        return knowledge["grid_width"] - 2

    def _move_to_column(self, knowledge, x):
        px, py = knowledge["pos"]
        target = (x, py)
        return self._navigate_to(knowledge, target)

    def _move_to_pos(self, knowledge, target):
        return self._navigate_to(knowledge, target)

    def _deliver_produced_waste(self, knowledge):
        produced = knowledge["produced_waste"]
        if produced is None or self._inventory_count(knowledge, produced) == 0:
            return None

        if knowledge["robot_role"] == "red":
            disposal_pos = knowledge["disposal_pos"]
            if disposal_pos and knowledge["pos"] == disposal_pos:
                return {"type": Action.PUT_DOWN, "waste_type": WasteType.RED}
            if disposal_pos:
                return self._navigate_to(knowledge, disposal_pos)
            return self._explore(knowledge, preferred_x=knowledge["grid_width"] - 1)

        handoff_pos = self._handoff_pos(knowledge)
        if knowledge["pos"] == handoff_pos:
            return {"type": Action.PUT_DOWN, "waste_type": produced}
        return self._move_to_pos(knowledge, handoff_pos)

    def _should_release_single_target(self, knowledge):
        return (
            self._target_count(knowledge) == 1
            and self._produced_count(knowledge) == 0
            and knowledge["single_hold_steps"] >= self.SINGLE_HOLD_LIMIT
        )

    def _release_single_target(self, knowledge):
        drop_pos = self._handoff_pos(knowledge)
        if knowledge["pos"] == drop_pos:
            return {"type": Action.PUT_DOWN, "waste_type": knowledge["target_waste"]}
        return self._move_to_pos(knowledge, drop_pos)

    def _pick_up_waste_here(self, knowledge):
        if self._produced_count(knowledge) > 0:
            return None
        if self._target_count(knowledge) >= knowledge["max_target_inventory"]:
            return None

        cell = knowledge["known_map"].get(knowledge["pos"], {})
        if knowledge["pos"] in knowledge["drop_cooldowns"]:
            return None

        for waste in cell.get("wastes", []):
            if waste["type"] == knowledge["target_waste"]:
                return {"type": Action.PICK_UP, "waste_id": waste["id"]}
        return None

    def _closest_target(self, knowledge):
        pos = knowledge["pos"]
        candidates = [
            target
            for target in knowledge["wastes_seen"]
            if target not in knowledge["drop_cooldowns"]
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda target: abs(target[0] - pos[0]) + abs(target[1] - pos[1]),
        )

    def _go_to_known_waste(self, knowledge):
        target = self._closest_target(knowledge)
        if target is None:
            return None

        knowledge["target"] = target
        action = self._navigate_to(knowledge, target)
        if action["type"] != Action.WAIT:
            return action

        knowledge["wastes_seen"].pop(target, None)
        return None

    def _explore(self, knowledge, preferred_x=None):
        px, py = knowledge["pos"]
        if preferred_x is None:
            preferred_x = self._source_x(knowledge)

        candidates = []
        for dx, dy in MOVE_ORDER:
            nx, ny = px + dx, py + dy
            npos = (nx, ny)

            if not (0 <= nx < knowledge["grid_width"] and 0 <= ny < knowledge["grid_height"]):
                continue
            if zone_from_knowledge(nx, knowledge) not in set(knowledge["allowed_zones"]):
                continue

            cell = knowledge["known_map"].get(npos, {})
            score = (
                0 if npos not in knowledge["known_map"] else 1,
                knowledge["visits"].get(npos, 0),
                1 if npos in knowledge["recent_positions"] else 0,
                len(cell.get("robots", [])),
                abs(preferred_x - nx),
                self.model.random.random(),
            )
            candidates.append((score, (dx, dy)))

        if not candidates:
            return {"type": Action.WAIT}

        _, move = min(candidates, key=lambda item: item[0])
        return {"type": Action.MOVE, "direction": move}

    def _standard_deliberation(self, knowledge):
        delivery_action = self._deliver_produced_waste(knowledge)
        if delivery_action is not None:
            return delivery_action

        if self._target_count(knowledge) >= 2:
            return {"type": Action.TRANSFORM}

        pick_action = self._pick_up_waste_here(knowledge)
        if pick_action is not None:
            return pick_action

        known_target_action = self._go_to_known_waste(knowledge)
        if known_target_action is not None:
            return known_target_action

        if self._should_release_single_target(knowledge):
            return self._release_single_target(knowledge)

        knowledge["target"] = None
        return self._explore(knowledge)


class GreenAgent(RobotAgent):
    ALLOWED_ZONES = {ZoneType.Z1}
    TARGET_WASTE = WasteType.GREEN
    PRODUCED_WASTE = WasteType.YELLOW
    MAX_TARGET_INVENTORY = 2
    ROLE = "green"

    def deliberate(self, knowledge):
        return self._standard_deliberation(knowledge)


class YellowAgent(RobotAgent):
    ALLOWED_ZONES = {ZoneType.Z1, ZoneType.Z2}
    TARGET_WASTE = WasteType.YELLOW
    PRODUCED_WASTE = WasteType.RED
    MAX_TARGET_INVENTORY = 2
    ROLE = "yellow"

    def deliberate(self, knowledge):
        return self._standard_deliberation(knowledge)


class RedAgent(RobotAgent):
    ALLOWED_ZONES = {ZoneType.Z1, ZoneType.Z2, ZoneType.Z3}
    TARGET_WASTE = WasteType.RED
    PRODUCED_WASTE = WasteType.RED
    MAX_TARGET_INVENTORY = 1
    ROLE = "red"
    SINGLE_HOLD_LIMIT = 9999

    def deliberate(self, knowledge):
        if self._target_count(knowledge) == 1:
            return self._deliver_produced_waste(knowledge)

        pick_action = self._pick_up_waste_here(knowledge)
        if pick_action is not None:
            return pick_action

        known_target_action = self._go_to_known_waste(knowledge)
        if known_target_action is not None:
            return known_target_action

        return self._explore(knowledge, preferred_x=self._source_x(knowledge))
