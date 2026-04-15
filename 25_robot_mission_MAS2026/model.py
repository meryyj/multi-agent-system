# Group: XX | Date: 2026-03-16 | Members: <your names here>

import random
from mesa import Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector

from objects import RadioactivityAgent, WasteAgent, WasteDisposalZone
from agents import GreenRobotAgent, YellowRobotAgent, RedRobotAgent, MOVE, PICK, TRANS, DROP, WAIT


def count_waste(model, waste_type: str) -> int:
    return sum(
        1 for a in model.agents
        if isinstance(a, WasteAgent) and a.waste_type == waste_type
    )


class RobotMission(Model):
    """
    Main model for the robot waste-collection mission.

    Parameters
    ----------
    width, height   : grid dimensions
    n_green_robots  : number of GreenRobotAgent
    n_yellow_robots : number of YellowRobotAgent
    n_red_robots    : number of RedRobotAgent
    n_green_waste   : initial green waste in z1
    seed            : random seed
    """

    def __init__(
        self,
        width=15,
        height=10,
        n_green_robots=2,
        n_yellow_robots=2,
        n_red_robots=2,
        n_green_waste=10,
        seed=None,
    ):
        super().__init__(seed=seed)

        self.width  = width
        self.height = height
        self.grid   = MultiGrid(width, height, torus=False)

        # Zone boundaries (columns, exclusive upper bound)
        # z1: [0, z1_bound)  z2: [z1_bound, z2_bound)  z3: [z2_bound, width)
        self.z1_bound = width // 3
        self.z2_bound = 2 * (width // 3)

        self.running = True   # Mesa flag

        # ---- Place radioactivity agents on every cell ----
        for x in range(width):
            for y in range(height):
                if x < self.z1_bound:
                    zone = 1
                elif x < self.z2_bound:
                    zone = 2
                else:
                    zone = 3
                r = RadioactivityAgent(self, zone)
                self.grid.place_agent(r, (x, y))

        # ---- Place waste disposal zone in the easternmost column ----
        disposal_y = self.random.randint(0, height - 1)
        self.disposal_pos = (width - 1, disposal_y)
        dz = WasteDisposalZone(self)
        self.grid.place_agent(dz, self.disposal_pos)

        # ---- Place green waste randomly in z1 ----
        for _ in range(n_green_waste):
            x = self.random.randint(0, self.z1_bound - 1)
            y = self.random.randint(0, height - 1)
            w = WasteAgent(self, "green")
            self.grid.place_agent(w, (x, y))

        # ---- Place robot agents ----
        def place_robot(agent, x_range):
            x = self.random.randint(*x_range)
            y = self.random.randint(0, height - 1)
            self.grid.place_agent(agent, (x, y))

        for _ in range(n_green_robots):
            place_robot(GreenRobotAgent(self), (0, self.z1_bound - 1))

        for _ in range(n_yellow_robots):
            place_robot(YellowRobotAgent(self), (0, self.z2_bound - 1))

        for _ in range(n_red_robots):
            place_robot(RedRobotAgent(self), (0, width - 1))

        # ---- Data collector ----
        self.datacollector = DataCollector(
            model_reporters={
                "Green waste":  lambda m: count_waste(m, "green"),
                "Yellow waste": lambda m: count_waste(m, "yellow"),
                "Red waste":    lambda m: count_waste(m, "red"),
                "Total waste":  lambda m: count_waste(m, "green")
                                        + count_waste(m, "yellow")
                                        + count_waste(m, "red"),
            }
        )
        self.datacollector.collect(self)

    # ------------------------------------------------------------------
    # Mesa step
    # ------------------------------------------------------------------
    def step(self):
        # Activate only robot agents (random order)
        robots = [a for a in self.agents if isinstance(a, (GreenRobotAgent, YellowRobotAgent, RedRobotAgent))]
        self.random.shuffle(robots)
        for robot in robots:
            robot.step()
        self.datacollector.collect(self)

        # Stop when all waste is disposed
        if count_waste(self, "green") == 0 and count_waste(self, "yellow") == 0 and count_waste(self, "red") == 0:
            self.running = False

    # ------------------------------------------------------------------
    # do() – environment executes agent actions
    # ------------------------------------------------------------------
    def do(self, agent, action):
        """
        Execute an action for the given agent and return percepts.

        Percepts format:
            { (x, y): [list of agents at that cell], ... }
        covering the agent's current cell and all 8 neighbours.
        """
        if isinstance(action, dict):
            atype = action.get("type", WAIT)
        else:
            atype = action   # plain string e.g. WAIT

        # ---- MOVE --------------------------------------------------------
        if atype == MOVE:
            target = action["pos"]
            if self._can_move(agent, target):
                self.grid.move_agent(agent, target)

        # ---- PICK --------------------------------------------------------
        elif atype == PICK:
            waste_type = action["waste_type"]
            cell_agents = self.grid.get_cell_list_contents([agent.pos])
            wastes = [a for a in cell_agents
                      if isinstance(a, WasteAgent) and a.waste_type == waste_type]
            carried = [w for w in agent.knowledge["inventory"] if w.waste_type == waste_type]

            # Capacity: green/yellow robots max 2, red robots max 1
            capacity = 1 if agent.robot_type == "red" else 2
            if wastes and len(carried) < capacity:
                w = wastes[0]
                agent.knowledge["inventory"].append(w)
                self.grid.remove_agent(w)

        # ---- TRANSFORM ---------------------------------------------------
        elif atype == TRANS:
            inv = agent.knowledge["inventory"]
            if agent.robot_type == "green":
                greens = [w for w in inv if w.waste_type == "green"]
                if len(greens) >= 2:
                    inv.remove(greens[0])
                    inv.remove(greens[1])
                    yellow = WasteAgent(self, "yellow")
                    inv.append(yellow)

            elif agent.robot_type == "yellow":
                yellows = [w for w in inv if w.waste_type == "yellow"]
                if len(yellows) >= 2:
                    inv.remove(yellows[0])
                    inv.remove(yellows[1])
                    red = WasteAgent(self, "red")
                    inv.append(red)

        # ---- DROP --------------------------------------------------------
        elif atype == DROP:
            waste_type = action["waste_type"]
            inv = agent.knowledge["inventory"]
            to_drop = [w for w in inv if w.waste_type == waste_type]
            if to_drop:
                w = to_drop[0]
                inv.remove(w)
                # If dropping red waste at the disposal zone → "put away" (remove)
                disposal_agents = self.grid.get_cell_list_contents([agent.pos])
                if (any(isinstance(a, WasteDisposalZone) for a in disposal_agents)
                        and waste_type == "red"):
                    # Waste is put away; don't place it on the grid
                    pass
                else:
                    self.grid.place_agent(w, agent.pos)

        # ---- WAIT (or unknown) -------------------------------------------
        # Nothing to do

        return self._get_percepts(agent)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _can_move(self, agent, target) -> bool:
        tx, ty = target
        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return False
        # Zone constraints
        if agent.robot_type == "green" and tx >= self.z1_bound:
            return False
        if agent.robot_type == "yellow" and tx >= self.z2_bound:
            return False
        # Must be adjacent (Moore neighbourhood, distance 1)
        cx, cy = agent.pos
        if abs(tx - cx) > 1 or abs(ty - cy) > 1:
            return False
        return True

    def _get_percepts(self, agent) -> dict:
        """Return contents of the agent's cell and all 8 neighbours."""
        percepts = {}
        x, y = agent.pos
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    percepts[(nx, ny)] = self.grid.get_cell_list_contents([(nx, ny)])
        return percepts
