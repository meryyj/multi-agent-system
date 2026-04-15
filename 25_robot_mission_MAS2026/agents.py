# Group: XX | Date: 2026-03-16 | Members: <your names here>

import random
from mesa import Agent
from objects import WasteAgent, RadioactivityAgent, WasteDisposalZone

# ---------------------------------------------------------------------------
# Action constants
# ---------------------------------------------------------------------------
MOVE   = "move"
PICK   = "pick"
TRANS  = "transform"
DROP   = "drop"
WAIT   = "wait"


class RobotAgent(Agent):
    """
    Abstract base class for all robot agents.
    Implements the percept → deliberate → do loop.
    """

    def __init__(self, model, robot_type: str):
        super().__init__(model)
        self.robot_type = robot_type   # "green" | "yellow" | "red"
        # ---- knowledge base ------------------------------------------------
        self.knowledge = {
            "pos": None,               # updated each step
            "inventory": [],           # list of WasteAgent currently carried
            "percepts": {},            # last percept dict
            "known_waste": {},         # pos -> waste_type  (memory map)
            "known_disposal": None,    # position of disposal zone (if seen)
            "zone": None,              # current zone (1/2/3)
            "last_action": None,
            "steps": 0,
        }

    # ------------------------------------------------------------------
    # Mesa hook
    # ------------------------------------------------------------------
    def step(self):
        percepts = self.model.do(self, WAIT)          # get initial percepts
        self._update_knowledge(percepts)
        action = self._deliberate(self.knowledge)
        self.knowledge["last_action"] = action
        percepts = self.model.do(self, action)
        self._update_knowledge(percepts)
        self.knowledge["steps"] += 1

    # ------------------------------------------------------------------
    # Percept update
    # ------------------------------------------------------------------
    def _update_knowledge(self, percepts: dict):
        self.knowledge["percepts"] = percepts
        self.knowledge["pos"] = self.pos

        for pos, contents in percepts.items():
            # Remember waste locations
            waste_here = [c for c in contents if isinstance(c, WasteAgent)]
            if waste_here:
                self.knowledge["known_waste"][pos] = waste_here[0].waste_type
            else:
                # Clear cell from memory if we previously knew waste was there
                self.knowledge["known_waste"].pop(pos, None)

            # Remember disposal zone
            if any(isinstance(c, WasteDisposalZone) for c in contents):
                self.knowledge["known_disposal"] = pos

            # Determine current zone from radioactivity
            for c in contents:
                if isinstance(c, RadioactivityAgent) and pos == self.pos:
                    self.knowledge["zone"] = c.zone

    # ------------------------------------------------------------------
    # Deliberate  (NO external variable access allowed)
    # ------------------------------------------------------------------
    def _deliberate(self, knowledge: dict):
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Helpers shared across subclasses
    # ------------------------------------------------------------------
    @staticmethod
    def _target_move(current_pos, target_pos, grid_w, grid_h):
        """Return a neighbouring position one step closer to target."""
        cx, cy = current_pos
        tx, ty = target_pos
        dx = 0 if tx == cx else (1 if tx > cx else -1)
        dy = 0 if ty == cy else (1 if ty > cy else -1)
        # Prefer x-movement first (east/west), then y
        if dx != 0:
            return (cx + dx, cy)
        return (cx, cy + dy)

    @staticmethod
    def _random_neighbour(pos, grid_w, grid_h):
        x, y = pos
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < grid_w and 0 <= ny < grid_h:
                    candidates.append((nx, ny))
        return random.choice(candidates) if candidates else pos


# ===========================================================================
# Green Robot
# ===========================================================================
class GreenRobotAgent(RobotAgent):
    """
    - Stays in z1
    - Picks up green waste (up to 2)
    - Transforms 2 green → 1 yellow, then drops it
    """

    def __init__(self, model):
        super().__init__(model, "green")

    def _deliberate(self, knowledge: dict):
        pos       = knowledge["pos"]
        inventory = knowledge["inventory"]
        percepts  = knowledge["percepts"]
        grid_w    = knowledge.get("grid_w", self.model.grid.width)
        grid_h    = knowledge.get("grid_h", self.model.grid.height)
        zone_bound = knowledge.get("z1_bound", self.model.z1_bound)  # x < z1_bound

        green_count  = sum(1 for w in inventory if w.waste_type == "green")
        yellow_count = sum(1 for w in inventory if w.waste_type == "yellow")

        # 1. If we hold a yellow waste → move east to the z1/z2 border and drop
        if yellow_count > 0:
            # Drop at the eastern edge of z1
            east_z1 = zone_bound - 1
            if pos[0] == east_z1:
                return {"type": DROP, "waste_type": "yellow"}
            target = (east_z1, pos[1])
            return {"type": MOVE, "pos": self._target_move(pos, target, grid_w, grid_h)}

        # 2. If we hold 2 green wastes → transform
        if green_count >= 2:
            return {"type": TRANS}

        # 3. Look for green waste in current percepts
        for npos, contents in percepts.items():
            if npos[0] < zone_bound:   # stay in z1
                for c in contents:
                    if isinstance(c, WasteAgent) and c.waste_type == "green":
                        if npos == pos:
                            return {"type": PICK, "waste_type": "green"}
                        return {"type": MOVE, "pos": npos}

        # 4. Use memory map
        green_memories = [(p, t) for p, t in knowledge["known_waste"].items()
                          if t == "green" and p[0] < zone_bound]
        if green_memories:
            target = min(green_memories, key=lambda pt: abs(pt[0][0]-pos[0])+abs(pt[0][1]-pos[1]))[0]
            return {"type": MOVE, "pos": self._target_move(pos, target, grid_w, grid_h)}

        # 5. Explore randomly within z1
        candidates = [(nx, ny) for (nx, ny) in [
            (pos[0]+dx, pos[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1)
            if not (dx==0 and dy==0)
        ] if 0 <= nx < zone_bound and 0 <= ny < grid_h]
        if candidates:
            return {"type": MOVE, "pos": random.choice(candidates)}
        return {"type": WAIT}


# ===========================================================================
# Yellow Robot
# ===========================================================================
class YellowRobotAgent(RobotAgent):
    """
    - Moves in z1 and z2
    - Picks up yellow waste (up to 2)
    - Transforms 2 yellow → 1 red, then drops at z2/z3 border
    """

    def __init__(self, model):
        super().__init__(model, "yellow")

    def _deliberate(self, knowledge: dict):
        pos        = knowledge["pos"]
        inventory  = knowledge["inventory"]
        percepts   = knowledge["percepts"]
        grid_w     = knowledge.get("grid_w", self.model.grid.width)
        grid_h     = knowledge.get("grid_h", self.model.grid.height)
        z1_bound   = knowledge.get("z1_bound", self.model.z1_bound)
        z2_bound   = knowledge.get("z2_bound", self.model.z2_bound)

        yellow_count = sum(1 for w in inventory if w.waste_type == "yellow")
        red_count    = sum(1 for w in inventory if w.waste_type == "red")

        # 1. Holding red waste → drop at eastern edge of z2
        if red_count > 0:
            east_z2 = z2_bound - 1
            if pos[0] == east_z2:
                return {"type": DROP, "waste_type": "red"}
            target = (east_z2, pos[1])
            return {"type": MOVE, "pos": self._target_move(pos, target, grid_w, grid_h)}

        # 2. Transform 2 yellow → red
        if yellow_count >= 2:
            return {"type": TRANS}

        # 3. Scan percepts for yellow waste (in z1 or z2)
        for npos, contents in percepts.items():
            if npos[0] < z2_bound:
                for c in contents:
                    if isinstance(c, WasteAgent) and c.waste_type == "yellow":
                        if npos == pos:
                            return {"type": PICK, "waste_type": "yellow"}
                        return {"type": MOVE, "pos": npos}

        # 4. Memory
        yellow_mem = [(p, t) for p, t in knowledge["known_waste"].items()
                      if t == "yellow" and p[0] < z2_bound]
        if yellow_mem:
            target = min(yellow_mem, key=lambda pt: abs(pt[0][0]-pos[0])+abs(pt[0][1]-pos[1]))[0]
            return {"type": MOVE, "pos": self._target_move(pos, target, grid_w, grid_h)}

        # 5. Explore randomly in z1 ∪ z2
        candidates = [(nx, ny) for (nx, ny) in [
            (pos[0]+dx, pos[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1)
            if not (dx==0 and dy==0)
        ] if 0 <= nx < z2_bound and 0 <= ny < grid_h]
        if candidates:
            return {"type": MOVE, "pos": random.choice(candidates)}
        return {"type": WAIT}


# ===========================================================================
# Red Robot
# ===========================================================================
class RedRobotAgent(RobotAgent):
    """
    - Moves in z1, z2, z3
    - Picks up 1 red waste
    - Transports it to the waste disposal zone (easternmost column)
    """

    def __init__(self, model):
        super().__init__(model, "red")

    def _deliberate(self, knowledge: dict):
        pos       = knowledge["pos"]
        inventory = knowledge["inventory"]
        percepts  = knowledge["percepts"]
        grid_w    = knowledge.get("grid_w", self.model.grid.width)
        grid_h    = knowledge.get("grid_h", self.model.grid.height)
        disposal  = knowledge["known_disposal"]

        red_count = sum(1 for w in inventory if w.waste_type == "red")

        # 1. Holding red → go to disposal zone and drop
        if red_count > 0:
            if disposal:
                if pos == disposal:
                    return {"type": DROP, "waste_type": "red"}
                return {"type": MOVE, "pos": self._target_move(pos, disposal, grid_w, grid_h)}
            # Don't know disposal yet → move east
            target = (grid_w - 1, pos[1])
            return {"type": MOVE, "pos": self._target_move(pos, target, grid_w, grid_h)}

        # 2. Scan percepts for red waste
        for npos, contents in percepts.items():
            for c in contents:
                if isinstance(c, WasteAgent) and c.waste_type == "red":
                    if npos == pos:
                        return {"type": PICK, "waste_type": "red"}
                    return {"type": MOVE, "pos": npos}

        # 3. Memory
        red_mem = [(p, t) for p, t in knowledge["known_waste"].items() if t == "red"]
        if red_mem:
            target = min(red_mem, key=lambda pt: abs(pt[0][0]-pos[0])+abs(pt[0][1]-pos[1]))[0]
            return {"type": MOVE, "pos": self._target_move(pos, target, grid_w, grid_h)}

        # 4. Explore entire grid randomly
        return {"type": MOVE, "pos": self._random_neighbour(pos, grid_w, grid_h)}
