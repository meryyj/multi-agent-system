from mesa import Model
from mesa.space import MultiGrid
import random

from objects import Waste, Radioactivity, DisposalZone
from agents import GreenAgent, YellowAgent, RedAgent


class RobotMission(Model):
    def __init__(
        self,
        width=15,
        height=10,
        n_green_robots=2,
        n_yellow_robots=2,
        n_red_robots=2,
        n_initial_green_waste=20,
        seed=None
    ):
        super().__init__(seed=seed)

        self.width = width
        self.height = height
        self.grid = MultiGrid(width, height, torus=False)

        # stockage simple des agents robots
        self.robot_agents = []

        # 1) placer la radioactivité sur toute la grille
        self._create_radioactivity_map()

        # 2) placer la disposal zone tout à l'est
        self.disposal_pos = self._create_disposal_zone()

        # 3) placer les déchets verts initiaux dans z1
        self._create_initial_green_waste(n_initial_green_waste)

        # 4) placer les robots
        self._create_robots(
            n_green_robots=n_green_robots,
            n_yellow_robots=n_yellow_robots,
            n_red_robots=n_red_robots
        )

    # ------------------------------------------------------------------
    # ZONES
    # ------------------------------------------------------------------
    def get_zone_from_x(self, x):
        """
        Découpe la grille en 3 zones verticales :
        z1 = gauche, z2 = milieu, z3 = droite
        """
        if x < self.width / 3:
            return "z1"
        elif x < 2 * self.width / 3:
            return "z2"
        return "z3"

    # ------------------------------------------------------------------
    # INITIALISATION
    # ------------------------------------------------------------------
    def _create_radioactivity_map(self):
        for x in range(self.width):
            for y in range(self.height):
                zone = self.get_zone_from_x(x)
                radio = Radioactivity(self.next_id(), self, zone)
                self.grid.place_agent(radio, (x, y))

    def _create_disposal_zone(self):
        """
        La zone de stockage final est placée sur une case à l'est.
        """
        x = self.width - 1
        y = random.randrange(self.height)

        disposal = DisposalZone(self.next_id(), self)
        self.grid.place_agent(disposal, (x, y))

        return (x, y)

    def _create_initial_green_waste(self, n_initial_green_waste):
        """
        Au début, on place uniquement des déchets verts en z1.
        """
        z1_max_x = max(0, int(self.width / 3) - 1)

        for _ in range(n_initial_green_waste):
            x = random.randint(0, z1_max_x)
            y = random.randint(0, self.height - 1)

            waste = Waste(self.next_id(), self, "green")
            self.grid.place_agent(waste, (x, y))

    def _create_robots(self, n_green_robots, n_yellow_robots, n_red_robots):
        """
        Placement initial simple :
        - green robots en z1
        - yellow robots en z1/z2
        - red robots partout
        """
        # Green robots
        z1_max_x = max(0, int(self.width / 3) - 1)
        for _ in range(n_green_robots):
            x = random.randint(0, z1_max_x)
            y = random.randint(0, self.height - 1)
            agent = GreenAgent(self.next_id(), self)
            self.grid.place_agent(agent, (x, y))
            self.robot_agents.append(agent)

        # Yellow robots
        z2_max_x = max(0, int(2 * self.width / 3) - 1)
        for _ in range(n_yellow_robots):
            x = random.randint(0, z2_max_x)
            y = random.randint(0, self.height - 1)
            agent = YellowAgent(self.next_id(), self)
            self.grid.place_agent(agent, (x, y))
            self.robot_agents.append(agent)

        # Red robots
        for _ in range(n_red_robots):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            agent = RedAgent(self.next_id(), self)
            self.grid.place_agent(agent, (x, y))
            self.robot_agents.append(agent)

    # ------------------------------------------------------------------
    # OUTILS
    # ------------------------------------------------------------------
    def get_cell_contents(self, pos):
        return self.grid.get_cell_list_contents([pos])

    def get_adjacent_percepts(self, pos):
        """
        Retourne un dictionnaire des cases voisines + contenu.
        Format demandé par le sujet : dictionnaire.
        """
        neighborhood = self.grid.get_neighborhood(
            pos,
            moore=True,
            include_center=True
        )

        percepts = {}
        for cell in neighborhood:
            percepts[cell] = self.get_cell_contents(cell)
        return percepts

    def move_agent_if_possible(self, agent, new_pos):
        """
        Vérifie juste que la position reste dans la grille.
        Les restrictions de zone seront gérées selon le type de robot.
        """
        x, y = new_pos
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid.move_agent(agent, new_pos)
            return True
        return False

    # ------------------------------------------------------------------
    # REGLES DE ZONE SELON ROBOT
    # ------------------------------------------------------------------
    def is_move_allowed(self, agent, new_pos):
        x, _ = new_pos
        zone = self.get_zone_from_x(x)

        if isinstance(agent, GreenAgent):
            return zone == "z1"

        if isinstance(agent, YellowAgent):
            return zone in ["z1", "z2"]

        if isinstance(agent, RedAgent):
            return zone in ["z1", "z2", "z3"]

        return False

    # ------------------------------------------------------------------
    # ACTION EXECUTION
    # ------------------------------------------------------------------
    def do(self, agent, action):
        """
        Exécute l'action choisie par l'agent.
        Retourne des percepts sous forme de dictionnaire.
        """
        if action is None:
            return self.get_adjacent_percepts(agent.pos)

        action_type = action.get("type")

        # --------------------------------------------------------------
        # MOVE
        # --------------------------------------------------------------
        if action_type == "move":
            new_pos = action.get("target")

            if new_pos is not None and self.is_move_allowed(agent, new_pos):
                self.move_agent_if_possible(agent, new_pos)

            return self.get_adjacent_percepts(agent.pos)

        # --------------------------------------------------------------
        # PICK
        # action = {"type": "pick", "waste_type": "green"}
        # --------------------------------------------------------------
        if action_type == "pick":
            wanted_type = action.get("waste_type")
            contents = self.get_cell_contents(agent.pos)

            for obj in contents:
                if isinstance(obj, Waste) and obj.type == wanted_type:
                    if hasattr(agent, "inventory"):
                        agent.inventory.append(obj.type)
                    self.grid.remove_agent(obj)
                    break

            return self.get_adjacent_percepts(agent.pos)

        # --------------------------------------------------------------
        # TRANSFORM GREEN -> YELLOW
        # action = {"type": "transform_green"}
        # --------------------------------------------------------------
        if action_type == "transform_green":
            if hasattr(agent, "inventory") and agent.inventory.count("green") >= 2:
                agent.inventory.remove("green")
                agent.inventory.remove("green")

                yellow = Waste(self.next_id(), self, "yellow")
                self.grid.place_agent(yellow, agent.pos)

            return self.get_adjacent_percepts(agent.pos)

        # --------------------------------------------------------------
        # TRANSFORM YELLOW -> RED
        # action = {"type": "transform_yellow"}
        # --------------------------------------------------------------
        if action_type == "transform_yellow":
            if hasattr(agent, "inventory") and agent.inventory.count("yellow") >= 2:
                agent.inventory.remove("yellow")
                agent.inventory.remove("yellow")

                red = Waste(self.next_id(), self, "red")
                self.grid.place_agent(red, agent.pos)

            return self.get_adjacent_percepts(agent.pos)

        # --------------------------------------------------------------
        # DROP
        # action = {"type": "drop", "waste_type": "yellow"}
        # --------------------------------------------------------------
        if action_type == "drop":
            waste_type = action.get("waste_type")
            if hasattr(agent, "inventory") and waste_type in agent.inventory:
                agent.inventory.remove(waste_type)
                waste = Waste(self.next_id(), self, waste_type)
                self.grid.place_agent(waste, agent.pos)

            return self.get_adjacent_percepts(agent.pos)

        # --------------------------------------------------------------
        # DISPOSE RED
        # action = {"type": "dispose_red"}
        # --------------------------------------------------------------
        if action_type == "dispose_red":
            contents = self.get_cell_contents(agent.pos)
            on_disposal = any(isinstance(obj, DisposalZone) for obj in contents)

            if on_disposal and hasattr(agent, "inventory") and "red" in agent.inventory:
                agent.inventory.remove("red")
                # le déchet rouge est considéré comme stocké définitivement

            return self.get_adjacent_percepts(agent.pos)

        return self.get_adjacent_percepts(agent.pos)

    # ------------------------------------------------------------------
    # STEP
    # ------------------------------------------------------------------
    def step(self):
        """
        Version simple : on fait agir chaque robot à tour de rôle.
        """
        for agent in self.robot_agents:
            agent.step_agent()

    # ------------------------------------------------------------------
    # METRICS UTILES
    # ------------------------------------------------------------------
    def count_waste(self):
        counts = {"green": 0, "yellow": 0, "red": 0}

        for cell_content, x, y in self.grid.coord_iter():
            for obj in cell_content:
                if isinstance(obj, Waste):
                    counts[obj.type] += 1

        return counts