#!/usr/bin/env python3
"""
A more advanced single-user Python MUD with a Tkinter GUI,
featuring:
- Pomodoro timer (auto-movement & auto-attack during focus).
- Level system & classes (Warrior, Mage, Rogue).
- Automated mob respawning.
- Expanded map with more rooms.

For demonstration, the Pomodoro times remain short:
    POMODORO_FOCUS_TIME = 15
    POMODORO_BREAK_TIME = 5
Adjust as needed for real usage.
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import tkinter.font as tkFont
import tkinter.messagebox
import tkinter.simpledialog
import json
import os
import random
import time

SAVE_FILE = "mud_save.json"

# Pomodoro times (short for testing)
POMODORO_FOCUS_TIME = 60*25
POMODORO_BREAK_TIME = 60*5

# -- Game balancing constants --
# Base stats for each class:
CLASS_STATS = {
    "warrior": {"max_hp": 120, "base_attack": 8, "skill_name": "Power Strike"},
    "mage":    {"max_hp": 80,  "base_attack": 12,"skill_name": "Arcane Blast"},
    "rogue":   {"max_hp": 100, "base_attack": 10,"skill_name": "Backstab"}
}

# Amount HP / Attack grows per level
HP_PER_LEVEL     = 10
ATTACK_PER_LEVEL = 2

# Enemies can be chosen from a pool
ENEMY_POOL = [
    {"name": "Anti Claws",     "hp": 100, "attack_power": 12, "exp": 50},
    {"name": "Shadow Beast",   "hp": 80,  "attack_power": 8,  "exp": 30},
    {"name": "Angry Turkey",   "hp": 60,  "attack_power": 6,  "exp": 20},
    {"name": "Goblin Raider",  "hp": 70,  "attack_power": 7,  "exp": 25},
    {"name": "Mountain Troll", "hp": 120, "attack_power": 10, "exp": 60},
]

RESPAWN_TIME = 10  # seconds after a mob is defeated


# -------------------------
# Data Structures
# -------------------------
class Player:
    def __init__(
        self,
        name,
        player_class="warrior",
        level=1,
        exp=0,
        max_hp=120,
        hp=120,
        base_attack=8,
        inventory=None,
        location="temple_of_stillness",
        tasks=None,
        pomodoro_streak=0
    ):
        self.name = name
        self.player_class = player_class.lower()
        self.level = level
        self.exp = exp
        self.max_hp = max_hp
        self.hp = hp
        self.base_attack = base_attack

        self.inventory = inventory if inventory is not None else []
        self.location = location
        self.tasks = tasks if tasks else {
            "complete_daily_job": False,
            "drink_from_stream":  False,
            "stun_opponent":      False
        }
        self.pomodoro_streak = pomodoro_streak

    def stats_text(self):
        lines = []
        lines.append(f"Name: {self.name}")
        lines.append(f"Class: {self.player_class.title()}")
        lines.append(f"Level: {self.level} (EXP: {self.exp})")
        lines.append(f"HP: {self.hp}/{self.max_hp}")
        inv_str = ", ".join(self.inventory) if self.inventory else "Empty"
        lines.append(f"Attack: {self.calculate_attack()}")
        lines.append(f"Inventory: {inv_str}")
        lines.append("Tasks:")
        for t, done in self.tasks.items():
            lines.append(f"  - {t.replace('_', ' ').title()}: {'[Done]' if done else '[Not Done]'}")
        lines.append(f"Pomodoro Streak: {self.pomodoro_streak}")
        return "\n".join(lines)

    def calculate_attack(self):
        # Base attack could be scaled by something; for now we return base_attack
        return self.base_attack

    def add_experience(self, amount):
        self.exp += amount
        # Check for level up
        required_exp = self.level * 100
        while self.exp >= required_exp:
            self.level_up()
            self.exp -= required_exp
            required_exp = self.level * 100

    def level_up(self):
        self.level += 1
        self.max_hp += HP_PER_LEVEL
        self.hp = self.max_hp  # restore full HP on level up
        self.base_attack += ATTACK_PER_LEVEL

    def get_class_skill_name(self):
        return CLASS_STATS[self.player_class]["skill_name"]


class Enemy:
    def __init__(self, name, hp, attack_power, exp_reward):
        self.name = name
        self.hp = hp
        self.attack_power = attack_power
        self.exp_reward = exp_reward
        self.alive = True

    def is_alive(self):
        return self.alive and self.hp > 0


class Room:
    def __init__(self, name, description, exits=None, items=None, enemy=None):
        self.name = name
        self.description = description
        self.exits = exits if exits else {}
        self.items = items if items else []
        # "enemy" can be None or an Enemy object
        self.enemy = enemy
        self.respawn_timer = 0  # For tracking respawn

    def spawn_enemy(self):
        """Randomly choose an enemy from the pool if no enemy is alive."""
        if self.enemy and self.enemy.is_alive():
            return  # There's already a living enemy

        # Potentially wait for respawn (tracked via self.respawn_timer).
        # If time is up, we spawn a new mob.
        current_time = time.time()
        if current_time >= self.respawn_timer:
            chosen = random.choice(ENEMY_POOL)
            self.enemy = Enemy(
                name=chosen["name"],
                hp=chosen["hp"],
                attack_power=chosen["attack_power"],
                exp_reward=chosen["exp"]
            )


# ------------------------------------------------------
# Expanded MAP
# ------------------------------------------------------
rooms = {
    # --------------------------------------------------------------------------------
    # ORIGINAL 10 ROOMS
    # --------------------------------------------------------------------------------
    "temple_of_stillness": Room(
        name="Temple of Stillness in Gad's Landing",
        description=(
            "This chamber is filled with hypnotic, shifting colors of light.\n"
            "Walls, floor, and ceiling are crafted from timbers and wood.\n"
            "A simple, unadorned jet-black altar sits at the far end."
        ),
        exits={"northwest": "downtown_gads_landing", "east": "outer_courtyard"},
        items=["pair_of_red_fur_claws", "pair_of_red_fur_claws", "pair_of_red_fur_claws"],
    ),
    "outer_courtyard": Room(
        name="Outer Courtyard",
        description=(
            "An open courtyard surrounded by tall stone walls. The ground is dusty\n"
            "and scattered with training dummies. A path leads back west or east.\n"
            "A massive gate to the north leads toward a looming castle."
        ),
        exits={
            "west": "temple_of_stillness",
            "east": "training_ground",
            "north": "castle_entrance"
        },
        items=["training_dummy"],
    ),
    "training_ground": Room(
        name="Training Ground",
        description=(
            "A broad training yard with weapon racks and straw targets. Trainees\n"
            "practice their skills here. Exits lie to the west and southeast."
        ),
        exits={"west": "outer_courtyard", "southeast": "downtown_gads_landing"},
        items=["wooden_sword"]
    ),
    "downtown_gads_landing": Room(
        name="Downtown Gad's Landing",
        description=(
            "A large circular section of town with paths heading off in all directions.\n"
            "Shade trees and flowers line the sides of various buildings."
        ),
        exits={"north": "gads_way_road", "south": "back_alley", "east": "outer_courtyard"},
        items=["greeting_ranger", "huge_portal", "stone_statue"],
    ),
    "gads_way_road": Room(
        name="Gad's Way Road",
        description=(
            "A dirt path lined with shade trees on both sides. Occasional wooden buildings\n"
            "can be spotted through the leafy canopy. The path continues east or south\n"
            "and branches north into farmland."
        ),
        exits={"east": "forest_path", "south": "downtown_gads_landing", "north": "farmland_1"},
        items=[]
    ),
    "forest_path": Room(
        name="A path through the forest",
        description=(
            "Leaves and wildflowers border this trail. Footprints of all shapes and sizes\n"
            "suggest many have passed here. Birds chirp all around."
        ),
        exits={"west": "gads_way_road", "east": "ridge_fork"},
        items=["blood_red_bird"]
    ),
    "ridge_fork": Room(
        name="A ridge splits the path (Level 22+ Recommended)",
        description=(
            "Towering oaks line the wide path to the east and west. A large sign warns of\n"
            "danger ahead. This is a fork in the road leading south and west."
        ),
        exits={"west": "forest_path", "south": "ridge_path"},
        items=["warning_sign"]
    ),
    "ridge_path": Room(
        name="Following the ridge",
        description=(
            "A semi-wide trail around the mountain ridge. Rocks lie scattered about. Stunted\n"
            "trees and patchy grass cling to either side."
        ),
        exits={"north": "ridge_fork", "south": "ridge_path_2", "east": "mountain_pass_1"}
    ),
    "ridge_path_2": Room(
        name="Following the ridge (continued)",
        description=(
            "The path grows rockier as it skirts the mountainside. The forest thins out,\n"
            "leaving heaps of jagged stones scattered all over."
        ),
        exits={"north": "ridge_path"},
        items=["blood_red_bear"]
    ),
    "back_alley": Room(
        name="A shady back alley",
        description=(
            "Dark and narrow, this alley reeks of garbage. You see flickers of movement\n"
            "in the shadows. A path leads back north to the downtown.\n"
            "An opening to the south leads into the city slums."
        ),
        exits={"north": "downtown_gads_landing", "south": "city_slums_1"},
        items=["discarded_bottle"]
    ),

    # --------------------------------------------------------------------------------
    # (NEW) 1) CASTLE AREA (5 new rooms)
    # --------------------------------------------------------------------------------
    "castle_entrance": Room(
        name="Castle Entrance",
        description=(
            "Massive iron gates mark the entrance to an imposing castle. Torches flicker\n"
            "on either side of the entrance. You can return south to the courtyard or\n"
            "venture deeper north into the castle halls."
        ),
        exits={"south": "outer_courtyard", "north": "castle_hall_1"},
        items=["rusted_shield"]
    ),
    "castle_hall_1": Room(
        name="Castle Hallway (Section 1)",
        description=(
            "A grand hallway adorned with faded tapestries. The air is chill,\n"
            "and your footsteps echo on the stone floor. Passage continues north."
        ),
        exits={"south": "castle_entrance", "north": "castle_hall_2"},
        items=["torn_tapestry"]
    ),
    "castle_hall_2": Room(
        name="Castle Hallway (Section 2)",
        description=(
            "More corridors branch off here, but most are barred or collapsed.\n"
            "A spiral staircase leads further north into darkness."
        ),
        exits={"south": "castle_hall_1", "north": "castle_hall_3"},
        items=["broken_lance"]
    ),
    "castle_hall_3": Room(
        name="Castle Hallway (Section 3)",
        description=(
            "Cobwebs cover the corners, and old suits of armor stand like sentinels.\n"
            "A faint draft from further north hints at a larger chamber ahead."
        ),
        exits={"south": "castle_hall_2", "north": "castle_hall_4"},
        items=["dusty_armor"]
    ),
    "castle_hall_4": Room(
        name="Castle Great Hall",
        description=(
            "An expansive hall opens up here, with a vaulted ceiling and a\n"
            "long-abandoned throne at the far side. A massive chandelier lies\n"
            "shattered on the floor. The only exit is back south."
        ),
        exits={"south": "castle_hall_3"},
        items=["ancient_throne", "shattered_chandelier"]
    ),

    # --------------------------------------------------------------------------------
    # (NEW) 2) MOUNTAIN PASS (5 new rooms)
    # --------------------------------------------------------------------------------
    "mountain_pass_1": Room(
        name="Mountain Pass (Entrance)",
        description=(
            "A narrow path leads east along the mountainside. Sharp winds chill the air.\n"
            "To the west, the ridge path can be seen disappearing behind rocky slopes."
        ),
        exits={"west": "ridge_path", "east": "mountain_pass_2"},
        items=["stone_marker"]
    ),
    "mountain_pass_2": Room(
        name="Mountain Pass (Cliffside)",
        description=(
            "The trail clings to the edge of a steep cliff. Pebbles occasionally\n"
            "tumble off the side, vanishing into mist below. The path continues east."
        ),
        exits={"west": "mountain_pass_1", "east": "mountain_pass_3"},
        items=["loose_rocks"]
    ),
    "mountain_pass_3": Room(
        name="Mountain Pass (Midway)",
        description=(
            "High-altitude air stings your lungs. A frigid breeze sweeps by.\n"
            "A narrow ledge stretches on to the east, while the safer route is west."
        ),
        exits={"west": "mountain_pass_2", "east": "mountain_pass_4"},
        items=["weathered_sign"]
    ),
    "mountain_pass_4": Room(
        name="Mountain Pass (Nearing Summit)",
        description=(
            "The path widens slightly here, offering a precarious view of the\n"
            "valley below. Clouds swirl around the peaks. An icy slope climbs\n"
            "further east toward the summit."
        ),
        exits={"west": "mountain_pass_3", "east": "mountain_pass_5"},
        items=["broken_spike"]
    ),
    "mountain_pass_5": Room(
        name="Mountain Summit",
        description=(
            "At last, the peak! A small plateau offers a panoramic view of the\n"
            "lands below. Fierce winds batter this exposed location. You can only\n"
            "go back west."
        ),
        exits={"west": "mountain_pass_4"},
        items=["eagle_feather"]
    ),

    # --------------------------------------------------------------------------------
    # (NEW) 3) CITY SLUMS (10 new rooms)
    # --------------------------------------------------------------------------------
    "city_slums_1": Room(
        name="City Slums (Entrance)",
        description=(
            "Narrow shacks and ragged tents crowd this area. The smell is foul,\n"
            "and wary eyes watch from every dark corner. You can go north\n"
            "back to the alley or further south deeper into the slums."
        ),
        exits={"north": "back_alley", "south": "city_slums_2"},
        items=["filthy_rag"]
    ),
    "city_slums_2": Room(
        name="City Slums (Row of Shacks)",
        description=(
            "Leaning shacks line the alleyways, their walls patched with scrap wood.\n"
            "Children dart around, curious yet cautious of strangers."
        ),
        exits={"north": "city_slums_1", "south": "city_slums_3"},
        items=["ripped_blanket"]
    ),
    "city_slums_3": Room(
        name="City Slums (Market Corner)",
        description=(
            "A makeshift market: old crates serving as stalls, selling dubious\n"
            "food and second-hand trinkets. It's possible to continue south."
        ),
        exits={"north": "city_slums_2", "south": "city_slums_4"},
        items=["moldy_bread", "rusty_coin"]
    ),
    "city_slums_4": Room(
        name="City Slums (Cramped Passage)",
        description=(
            "Barely wide enough for a single person, this crooked lane weaves\n"
            "through the makeshift homes. The passage continues south."
        ),
        exits={"north": "city_slums_3", "south": "city_slums_5"},
        items=[]
    ),
    "city_slums_5": Room(
        name="City Slums (Gathering Spot)",
        description=(
            "A slightly open clearing where a few slum dwellers gather to chat,\n"
            "cook, or trade. There's an air of desperation but also camaraderie."
        ),
        exits={"north": "city_slums_4", "south": "city_slums_6"},
        items=["charcoal_fire"]
    ),
    "city_slums_6": Room(
        name="City Slums (Abandoned Cart)",
        description=(
            "An old, broken cart sits here, half-looted. Pieces of cloth hang\n"
            "off the sides, and you can see more rickety homes to the south."
        ),
        exits={"north": "city_slums_5", "south": "city_slums_7"},
        items=["broken_wheel"]
    ),
    "city_slums_7": Room(
        name="City Slums (Deep Alley)",
        description=(
            "The alley gets darker and narrower, the smell of garbage intensifies.\n"
            "A few suspicious figures loiter here, keeping to the shadows."
        ),
        exits={"north": "city_slums_6", "south": "city_slums_8"},
        items=["makeshift_knife"]
    ),
    "city_slums_8": Room(
        name="City Slums (Worn Stairway)",
        description=(
            "A crumbling stairway descends slightly, leading to an even lower\n"
            "section of the slums. The air is humid and stale."
        ),
        exits={"north": "city_slums_7", "south": "city_slums_9"},
        items=["broken_stair"]
    ),
    "city_slums_9": Room(
        name="City Slums (Sunken Square)",
        description=(
            "Here, the ground is below street level, forming a sunken courtyard.\n"
            "Shack rooftops rise around you, blocking most light. Further south\n"
            "there might be a way out."
        ),
        exits={"north": "city_slums_8", "south": "city_slums_10"},
        items=["scrap_rope"]
    ),
    "city_slums_10": Room(
        name="City Slums (Dead End)",
        description=(
            "The makeshift path ends abruptly at a collapsed building. There's\n"
            "no way forward, so the only path is back north."
        ),
        exits={"north": "city_slums_9"},
        items=["charred_debris"]
    ),

    # --------------------------------------------------------------------------------
    # (NEW) 4) FARMLAND (10 new rooms)
    # --------------------------------------------------------------------------------
    "farmland_1": Room(
        name="Farmland (Near Road)",
        description=(
            "Low wooden fences and tilled soil mark the start of open farmland.\n"
            "The road is back south, and you can move further north to more fields."
        ),
        exits={"south": "gads_way_road", "north": "farmland_2"},
        items=["scarecrow"]
    ),
    "farmland_2": Room(
        name="Farmland (Cornfield)",
        description=(
            "Tall corn stalks rustle in the breeze, forming a rust-gold sea.\n"
            "A narrow path continues north between the rows."
        ),
        exits={"south": "farmland_1", "north": "farmland_3"},
        items=["bundle_of_corn"]
    ),
    "farmland_3": Room(
        name="Farmland (Barn)",
        description=(
            "A weathered barn stands here, paint peeling from the siding. The\n"
            "scent of hay drifts from inside. You can continue north or go back south."
        ),
        exits={"south": "farmland_2", "north": "farmland_4"},
        items=["hay_bale"]
    ),
    "farmland_4": Room(
        name="Farmland (Wheat Fields)",
        description=(
            "Rows of ripe wheat shimmer under the sun. You hear the chirp of crickets\n"
            "and see a path heading north again."
        ),
        exits={"south": "farmland_3", "north": "farmland_5"},
        items=["wheat_bundle"]
    ),
    "farmland_5": Room(
        name="Farmland (Orchard Edge)",
        description=(
            "A small orchard of apple trees lines the fence. Fallen fruit litters\n"
            "the ground. You can move further north."
        ),
        exits={"south": "farmland_4", "north": "farmland_6"},
        items=["apple"]
    ),
    "farmland_6": Room(
        name="Farmland (Orchard Center)",
        description=(
            "Deeper in the orchard, branches intertwine overhead. Baskets filled\n"
            "with apples and pears lie about, some half-rotten."
        ),
        exits={"south": "farmland_5", "north": "farmland_7"},
        items=["fruit_basket"]
    ),
    "farmland_7": Room(
        name="Farmland (Cattle Field)",
        description=(
            "Wide grassy fields dotted with cows grazing lazily. A wooden gate to the\n"
            "north leads to another part of the farm."
        ),
        exits={"south": "farmland_6", "north": "farmland_8"},
        items=["cow_bell"]
    ),
    "farmland_8": Room(
        name="Farmland (Pond)",
        description=(
            "A small pond reflects the sky. Ducks float on the surface, quacking occasionally.\n"
            "You can head north or back south."
        ),
        exits={"south": "farmland_7", "north": "farmland_9"},
        items=["duck_feather"]
    ),
    "farmland_9": Room(
        name="Farmland (Storeroom Shed)",
        description=(
            "A wooden shed used to store tools and seeds. Its door creaks loudly.\n"
            "You see a path north that leads to a grassy trail."
        ),
        exits={"south": "farmland_8", "north": "farmland_10"},
        items=["bag_of_seeds", "rusty_shovel"]
    ),
    "farmland_10": Room(
        name="Farmland (Grassy Trail)",
        description=(
            "The farmland begins to merge with rolling hills. The wind is stronger\n"
            "here, rustling the grass. You can only return south."
        ),
        exits={"south": "farmland_9"},
        items=["tall_grass"]
    ),

    # --------------------------------------------------------------------------------
    # (NEW) 5) DEEP CAVERN NETWORK (10 new rooms)
    # --------------------------------------------------------------------------------
    # We'll attach the cavern to farmland_10 for variety
    "cavern_1": Room(
        name="Cavern Entrance",
        description=(
            "A small cave entrance yawns at the base of a hill. Cool air wafts\n"
            "out from within. You can step inside north or go back south."
        ),
        exits={"south": "farmland_10", "north": "cavern_2"},
        items=["damp_rocks"]
    ),
    "cavern_2": Room(
        name="Cavern (Twilight Zone)",
        description=(
            "Dim light filters in from the entrance behind you. Stalactites hang\n"
            "from above, and you hear dripping water. Passage continues north."
        ),
        exits={"south": "cavern_1", "north": "cavern_3"},
        items=["small_stalactite"]
    ),
    "cavern_3": Room(
        name="Cavern (Shallow Pool)",
        description=(
            "A shallow pool blocks part of the path, reflecting the ceiling.\n"
            "You might wade through it, continuing north, or retreat south."
        ),
        exits={"south": "cavern_2", "north": "cavern_4"},
        items=["glowing_moss"]
    ),
    "cavern_4": Room(
        name="Cavern (Crystal Vein)",
        description=(
            "Sparkling crystals emerge from the cavern walls, refracting any\n"
            "light into dazzling patterns. You can move further north."
        ),
        exits={"south": "cavern_3", "north": "cavern_5"},
        items=["crystal_shard"]
    ),
    "cavern_5": Room(
        name="Cavern (Crossroad)",
        description=(
            "Here the cave branches in multiple directions. A sign scratched\n"
            "onto stone warns of danger ahead. Forward is north, or go back."
        ),
        exits={"south": "cavern_4", "north": "cavern_6"},
        items=["worn_warning"]
    ),
    "cavern_6": Room(
        name="Cavern (Narrow Passage)",
        description=(
            "The walls squeeze in, forcing you to sidestep around large boulders.\n"
            "A faint echo suggests an opening further north."
        ),
        exits={"south": "cavern_5", "north": "cavern_7"},
        items=["cave_spider_web"]
    ),
    "cavern_7": Room(
        name="Cavern (Underground River)",
        description=(
            "A subterranean river flows here, rushing around smooth rocks.\n"
            "A fragile plank bridge crosses to the north side."
        ),
        exits={"south": "cavern_6", "north": "cavern_8"},
        items=["driftwood"]
    ),
    "cavern_8": Room(
        name="Cavern (Misty Hollow)",
        description=(
            "A low-hanging fog gathers here, swirling around your ankles.\n"
            "Stalagnates split the path, but a narrow route leads north."
        ),
        exits={"south": "cavern_7", "north": "cavern_9"},
        items=["foggy_stone"]
    ),
    "cavern_9": Room(
        name="Cavern (Glowshroom Grove)",
        description=(
            "Bioluminescent mushrooms cluster around a damp chamber, their soft\n"
            "light revealing a faint path heading north."
        ),
        exits={"south": "cavern_8", "north": "cavern_10"},
        items=["glow_shroom"]
    ),
    "cavern_10": Room(
        name="Cavern (Hidden Sanctuary)",
        description=(
            "The deepest chamber opens into a hidden sanctuary with an\n"
            "underground waterfall. It's serene, yet mysterious. Dead end here."
        ),
        exits={"south": "cavern_9"},
        items=["underground_waterfall"]
    ),
}

#
#

# ------------------------------------------------------
# Save & Load
# ------------------------------------------------------
def save_game(player: Player):
    data = {
        "name": player.name,
        "player_class": player.player_class,
        "level": player.level,
        "exp": player.exp,
        "max_hp": player.max_hp,
        "hp": player.hp,
        "base_attack": player.base_attack,
        "inventory": player.inventory,
        "location": player.location,
        "tasks": player.tasks,
        "pomodoro_streak": player.pomodoro_streak
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)


def load_game():
    if not os.path.isfile(SAVE_FILE):
        return None
    with open(SAVE_FILE, "r") as f:
        data = json.load(f)
    p = Player(
        name=data["name"],
        player_class=data["player_class"],
        level=data["level"],
        exp=data["exp"],
        max_hp=data["max_hp"],
        hp=data["hp"],
        base_attack=data["base_attack"],
        inventory=data["inventory"],
        location=data["location"],
        tasks=data["tasks"],
        pomodoro_streak=data["pomodoro_streak"]
    )
    return p


# ------------------------------------------------------
# Tkinter GUI
# ------------------------------------------------------
class MudGameGUI(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.player = None
        self.is_topmost = False
        self.in_pause = False
        self.temp_pomodoro_seconds_left = 0

        # Pomodoro / Movement variables
        self.pomodoro_running = False
        self.pomodoro_in_break = False
        self.pomodoro_seconds_left = 0

        # For auto-movement
        self.auto_move_directions = ["north", "west", "east", "south"]  # random directions
        self.auto_move_index = 0

        self.pack(fill=tk.BOTH, expand=True)
        self.create_widgets()
        self.init_mobs()  # spawn initial mobs

    def create_widgets(self):
        # Top frame
        self.top_frame = tk.Frame(self)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.btn_new = tk.Button(self.top_frame, text="New Game", command=self.new_game)
        self.btn_new.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_load = tk.Button(self.top_frame, text="Load Game", command=self.load_game_action)
        self.btn_load.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_save = tk.Button(self.top_frame, text="Save Game", command=self.save_game_action, state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_help = tk.Button(self.top_frame, text="Help", command=self.command_help, state=tk.NORMAL)
        self.btn_help.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_quit = tk.Button(self.top_frame, text="Quit", command=self.quit_game)
        self.btn_quit.pack(side=tk.LEFT, padx=(0, 5))

        self.toggle_btn = tk.Button(self.top_frame, text="Pin: OFF", bg="red", fg="white", command=self.toggle_topmost)
        self.toggle_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Pomodoro frame
        self.pomo_frame = tk.Frame(self)
        self.pomo_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.pomo_label = tk.Label(self.pomo_frame, text="Pomodoro: Not Running")
        self.pomo_label.pack(side=tk.LEFT)

        self.btn_pomo_start = tk.Button(self.pomo_frame, text="Start Pomodoro", command=self.start_pomodoro, state=tk.DISABLED)
        self.btn_pomo_start.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_pomo_pause = tk.Button(self.pomo_frame, text="Pause Pomodoro", command=self.pause_pomodoro, state=tk.DISABLED)
        self.btn_pomo_pause.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_pomo_stop = tk.Button(self.pomo_frame, text="Stop Pomodoro", command=self.stop_pomodoro, state=tk.DISABLED)
        self.btn_pomo_stop.pack(side=tk.LEFT, padx=(0, 5))

        # ScrolledText for output, change font size and fg bg of output area here:
        self.output_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=5, width=80, fg="green", bg="black", state=tk.DISABLED)
        custom_font = tkFont.Font(family="JetBrains Mono", size=16, weight="bold")  # Use any desired font family
        self.output_area.configure(font=custom_font)
        self.output_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bottom frame for commands
        self.entry_frame = tk.Frame(self)
        self.entry_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.entry_label = tk.Label(self.entry_frame, text="Command:")
        self.entry_label.pack(side=tk.LEFT)

        self.command_entry = tk.Entry(self.entry_frame)
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.command_entry.bind("<Return>", self.on_enter)

        self.btn_enter = tk.Button(self.entry_frame, text="Enter", command=self.execute_command)
        self.btn_enter.pack(side=tk.LEFT)


    # ------------------------------------------------------
    # Top most
    # ------------------------------------------------------
    def toggle_topmost(self):
        self.is_topmost = not self.is_topmost  # Toggle the state
        self.master.attributes("-topmost", self.is_topmost)  # Set topmost based on toggle state
        if self.is_topmost:
            self.toggle_btn.config(text="Pin: ON", bg="green")
        else:
            self.toggle_btn.config(text="Pin: OFF", bg="red")

    # ------------------------------------------------------
    # New / Load / Save / Quit
    # ------------------------------------------------------
    def new_game(self):
        name = tk.simpledialog.askstring("New Game", "What's your name?", parent=self)
        if not name:
            name = "idleHero"


        # Choose a class
        class_choice = tk.simpledialog.askstring("Choose Class", "Choose: warrior / mage / rogue", parent=self)
        if not class_choice or class_choice.lower() not in CLASS_STATS.keys():
            class_choice = "warrior"

        base_stats = CLASS_STATS[class_choice.lower()]
        player = Player(
            name=name,
            player_class=class_choice.lower(),
            max_hp=base_stats["max_hp"],
            hp=base_stats["max_hp"],
            base_attack=base_stats["base_attack"],
        )
        self.player = player

        self.clear_output()
        self.write_line(f"Welcome, {self.player.name} the {self.player.player_class.title()}!")
        self.write_line("You find yourself in a new world...")

        self.btn_save.config(state=tk.NORMAL)
        self.btn_pomo_start.config(state=tk.NORMAL)
        self.btn_pomo_pause.config(state=tk.NORMAL)
        self.btn_pomo_stop.config(state=tk.NORMAL)

        self.look_around()

    def load_game_action(self):
        loaded_player = load_game()
        if loaded_player:
            self.player = loaded_player
            self.clear_output()
            self.write_line(f"Welcome back, {self.player.name} the {self.player.player_class.title()}!")
            self.look_around()
            self.btn_save.config(state=tk.NORMAL)
            self.btn_pomo_start.config(state=tk.NORMAL)
            self.btn_pomo_pause.config(state=tk.NORMAL)
            self.btn_pomo_stop.config(state=tk.NORMAL)
        else:
            messagebox.showinfo("Load Game", "No saved game found, mate!")

    def save_game_action(self):
        if self.player:
            save_game(self.player)
            self.write_line("Game saved successfully.")
        else:
            self.write_line("No game in progress to save.")

    def quit_game(self):
        self.master.quit()

    # ------------------------------------------------------
    # Pomodoro
    # ------------------------------------------------------
    def start_pomodoro(self):
        if not self.player:
            self.write_line("Start a new game or load a game first!")
            return
        if self.pomodoro_running:
            self.write_line("Pomodoro is already running!")
            return
        self.pomodoro_running = True
        self.pomodoro_in_break = False
        if self.in_pause:
            self.pomodoro_seconds_left = self.temp_pomodoro_seconds_left
            self.in_pause = False
        else:
            self.pomodoro_seconds_left = POMODORO_FOCUS_TIME
        self.update_pomodoro_label()
        self.tick_pomodoro()

    def pause_pomodoro(self):
        if not self.pomodoro_running:
            self.write_line("No Pomodoro session is running right now.")
            return
        self.pomodoro_running = False
        self.pomodoro_in_break = False
        self.in_pause = True
        self.temp_pomodoro_seconds_left = self.pomodoro_seconds_left
        self.update_pomodoro_label()

    def stop_pomodoro(self):
        if not self.pomodoro_running:
            self.write_line("No Pomodoro session is running right now.")
            return
        self.pomodoro_running = False
        self.pomodoro_in_break = False
        self.update_pomodoro_label()

    def tick_pomodoro(self):
        """Called every second to update the Pomodoro timer."""
        if not self.pomodoro_running:
            return
        if self.pomodoro_seconds_left > 0:
            self.pomodoro_seconds_left -= 1
            self.update_pomodoro_label()

            # During focus, auto-move and auto-attack
            if not self.pomodoro_in_break:
                self.auto_move_and_attack()

            self.after(1000, self.tick_pomodoro)
        else:
            # Time's up - either switch to break or finish break
            if not self.pomodoro_in_break:
                # Completed focus
                self.player.pomodoro_streak += 1
                self.write_line(f"Focus session complete! Streak: {self.player.pomodoro_streak}")
                messagebox.showinfo("End", f"Focus session complete! Streak: {self.player.pomodoro_streak}")
                self.pomodoro_in_break = True
                self.pomodoro_seconds_left = POMODORO_BREAK_TIME
                self.update_pomodoro_label()
                self.after(1000, self.tick_pomodoro)
            else:
                # Completed break
                self.write_line("Break is over. Another Pomodoro starts!")
                self.pomodoro_in_break = False
                self.pomodoro_seconds_left = POMODORO_FOCUS_TIME
                self.update_pomodoro_label()
                self.after(1000, self.tick_pomodoro)

    def update_pomodoro_label(self):
        if not self.pomodoro_running and not self.in_pause:
            self.pomo_label.config(text="Pomodoro: Not Running")
        else:
            label = "Break" if self.pomodoro_in_break else "Focus"
            self.pomo_label.config(text=f"Pomodoro: {label} - {self.pomodoro_seconds_left // 60}min {self.pomodoro_seconds_left % 60}s left")

    def auto_move_and_attack(self):
        """
        During Focus, the player automatically moves
        and attacks any mob in the current room.
        Only moves to a new room if:
        - The player's HP is at maximum.
        - There is no living enemy in the current room.
        """

        # Check the current room
        current_room = rooms[self.player.location]

        # 1) If there's an enemy in the current room and it's alive, just attack it; do NOT move
        if current_room.enemy and current_room.enemy.is_alive():
            self.auto_attack_if_enemy()
            return

        # 2) If the player is not at full health, do not move
        if self.player.hp < self.player.max_hp:
            # Optionally, you could do some healing here automatically
            self.heal_player()
            return

        # 3) If we got here, it means HP is full and there's no enemy alive in this room.
        #    Let's proceed to move to another room.
        directions = current_room.exits
        if not directions:
            return  # no exits to move through

        # We'll do a naive cycle: pick from self.auto_move_directions
        # If that direction is valid, we move
        for _ in range(len(self.auto_move_directions)):
            dir_ = self.auto_move_directions[self.auto_move_index]
            self.auto_move_index = (self.auto_move_index + 1) % len(self.auto_move_directions)

            # If it's a valid exit with a non-None room
            if dir_ in directions and directions[dir_]:
                self.move_player(dir_)
                break

        # Optionally, after moving, if there's an enemy in the new room, attack it
        self.auto_attack_if_enemy()


    def auto_attack_if_enemy(self):
        room = rooms[self.player.location]
        if room.enemy and room.enemy.is_alive():
            self.attack_enemy()

    # ------------------------------------------------------
    # Mobs
    # ------------------------------------------------------
    def init_mobs(self):
        """Initial spawn attempt for each room."""
        for room in rooms.values():
            if random.random() < 0.4:  # 40% chance to spawn an enemy
                chosen = random.choice(ENEMY_POOL)
                room.enemy = Enemy(
                    name=chosen["name"],
                    hp=chosen["hp"],
                    attack_power=chosen["attack_power"],
                    exp_reward=chosen["exp"]
                )

    def handle_mob_death(self, room):
        """Mark the enemy as dead and set respawn time."""
        room.enemy.alive = False
        room.enemy = None  # remove reference
        room.respawn_timer = time.time() + RESPAWN_TIME
        # We'll spawn a new mob once respawn time is reached.

    def maybe_respawn_mob(self, room):
        """Check if it's time to respawn a mob."""
        room.spawn_enemy()

    # ------------------------------------------------------
    # Output
    # ------------------------------------------------------
    def clear_output(self):
        self.output_area.config(state=tk.NORMAL)
        self.output_area.delete("1.0", tk.END)
        self.output_area.config(state=tk.DISABLED)

    def write_line(self, text: str):
        self.output_area.config(state=tk.NORMAL)
        self.output_area.insert(tk.END, text + "\n")
        self.output_area.see(tk.END)
        self.output_area.config(state=tk.DISABLED)

    def on_enter(self, event):
        self.execute_command()

    # ------------------------------------------------------
    # Commands
    # ------------------------------------------------------
    def execute_command(self):
        cmd = self.command_entry.get().strip().lower()
        self.command_entry.delete(0, tk.END)
        if not self.player:
            self.write_line("You need to start or load a game first.")
            return

        if not cmd:
            return

        if cmd in ["quit", "exit"]:
            self.quit_game()
            return

        if cmd == "help":
            self.command_help()
            return

        if cmd in ["look", "l"]:
            self.look_around()
            return

        if cmd.startswith("move "):
            _, direction = cmd.split(" ", 1)
            self.move_player(direction)
            return

        if cmd in ["attack", "fight"]:
            self.attack_enemy()
            return

        if cmd == "heal":
            self.heal_player()
            return

        if cmd == "stats":
            self.write_line(self.player.stats_text())
            return

        if cmd.startswith("pickup "):
            _, item_name = cmd.split(" ", 1)
            self.pickup_item(item_name)
            return

        if cmd.startswith("drop "):
            _, item_name = cmd.split(" ", 1)
            self.drop_item(item_name)
            return

        if cmd.startswith("use "):
            _, item_name = cmd.split(" ", 1)
            self.use_item(item_name)
            return

        if cmd == "skill":
            self.use_class_skill()
            return

        if cmd == "task list":
            self.show_tasks()
            return

        self.write_line("Not sure what you're on about, mate. Type 'help' for valid commands.")

    def command_help(self):
        self.write_line("Possible commands:")
        self.write_line("  look / l                - Look around.")
        self.write_line("  stats                   - Show your status.")
        self.write_line("  move <direction>        - Move (north, east, south, west, etc.).")
        self.write_line("  attack                  - Attack an enemy here.")
        self.write_line("  heal                    - Self-heal if below max HP.")
        self.write_line("  skill                   - Use your class skill (Power Strike, Arcane Blast, etc.).")
        self.write_line("  pickup <item>           - Pick up an item in the room.")
        self.write_line("  drop <item>             - Drop an item from your inventory.")
        self.write_line("  use <item>              - Use an item (e.g., healing_potion).")
        self.write_line("  task list               - View your tasks.")
        self.write_line("  save                    - (Button at top) Save your current game.")
        self.write_line("  quit / exit             - Quit the game.")
        self.write_line("  help                    - This menu.")

    def look_around(self):
        room = rooms[self.player.location]
        # Attempt to respawn mob if needed
        self.maybe_respawn_mob(room)

        self.write_line(f"\nLocation: {room.name}")
        self.write_line(room.description)
        if room.items:
            self.write_line("\nItems in this area:")
            for i in room.items:
                self.write_line(f"  - {i}")

        if room.enemy and room.enemy.is_alive():
            self.write_line(f"\nThere's a hostile presence here: {room.enemy.name} (HP: {room.enemy.hp})")

        exits = [ex for ex, loc in room.exits.items() if loc]
        exit_str = ", ".join(exits) if exits else "None"
        self.write_line(f"Exits: {exit_str}")

    def move_player(self, direction: str):
        room = rooms[self.player.location]
        if direction not in room.exits or room.exits[direction] is None:
            self.write_line("You can’t go that way, mate!")
            return
        new_room_id = room.exits[direction]

        self.player.location = new_room_id
        self.look_around()

    def attack_enemy(self):
        room = rooms[self.player.location]
        if not room.enemy or not room.enemy.is_alive():
            self.write_line("There’s nothing here to attack.")
            return

        enemy = room.enemy
        # Player hits
        player_damage = random.randint(self.player.calculate_attack() - 2, self.player.calculate_attack() + 2)
        if player_damage < 0:
            player_damage = 0
        enemy.hp -= player_damage
        self.write_line(f"You lash out at {enemy.name}, dealing {player_damage} damage! (Enemy HP: {enemy.hp})")

        if enemy.hp <= 0:
            self.write_line(f"You have defeated {enemy.name}!")
            # Award exp
            self.write_line(f"You gain {enemy.exp_reward} EXP.")
            self.player.add_experience(enemy.exp_reward)

            # Task: stun an opponent (rough check here)
            if not self.player.tasks["stun_opponent"]:
                self.player.tasks["stun_opponent"] = True
                self.write_line("Task update: You have stunned an opponent!")

            self.handle_mob_death(room)
            return

        # Enemy hits back
        enemy_damage = random.randint(1, enemy.attack_power)
        self.player.hp -= enemy_damage
        self.write_line(f"{enemy.name} counters, dealing {enemy_damage} damage! (Your HP: {self.player.hp})")

        if self.player.hp <= 0:
            self.write_line("You succumb to your wounds...")
            self.heal_player()

    def heal_player(self):
        if self.player.hp >= self.player.max_hp:
            self.write_line("You're already at full health!")
            return
        heal_amount = random.randint(5, 15)
        self.player.hp = min(self.player.hp + heal_amount, self.player.max_hp)
        self.write_line(f"You patch yourself up, restoring {heal_amount} HP. (Your HP: {self.player.hp})")

    def pickup_item(self, item_name: str):
        room = rooms[self.player.location]
        if item_name not in room.items:
            self.write_line("That item isn’t here.")
            return
        room.items.remove(item_name)
        self.player.inventory.append(item_name)
        self.write_line(f"You pick up the {item_name}.")

    def drop_item(self, item_name: str):
        if item_name not in self.player.inventory:
            self.write_line("You don't have that item.")
            return
        self.player.inventory.remove(item_name)
        rooms[self.player.location].items.append(item_name)
        self.write_line(f"You dropped {item_name} on the ground.")

    def use_item(self, item_name: str):
        if item_name not in self.player.inventory:
            self.write_line("You don't have that in your bag.")
            return
        # For demo: if item is 'healing_potion', it heals
        if "healing_potion" in item_name:
            heal_amount = random.randint(20, 40)
            self.player.hp = min(self.player.hp + heal_amount, self.player.max_hp)
            self.write_line(f"You drink the healing potion, restoring {heal_amount} HP. (HP: {self.player.hp})")
            self.player.inventory.remove(item_name)
        else:
            self.write_line("You can't figure out how to use that right now.")

    def use_class_skill(self):
        """Example skill usage: deals extra damage or has special effect."""
        room = rooms[self.player.location]
        if not room.enemy or not room.enemy.is_alive():
            self.write_line("No enemy here to use your skill on.")
            return

        skill_name = self.player.get_class_skill_name()
        dmg_boost = random.randint(10, 15)

        enemy = room.enemy
        enemy.hp -= dmg_boost
        self.write_line(f"You use {skill_name}! It deals {dmg_boost} bonus damage. (Enemy HP: {enemy.hp})")

        if enemy.hp <= 0:
            self.write_line(f"You have defeated {enemy.name}!")
            self.write_line(f"You gain {enemy.exp_reward} EXP.")
            self.player.add_experience(enemy.exp_reward)
            if not self.player.tasks["stun_opponent"]:
                self.player.tasks["stun_opponent"] = True
                self.write_line("Task update: You have stunned an opponent!")
            self.handle_mob_death(room)
        else:
            # Enemy retaliates
            retal_damage = random.randint(1, enemy.attack_power)
            self.player.hp -= retal_damage
            self.write_line(f"{enemy.name} retaliates for {retal_damage} damage! (Your HP: {self.player.hp})")
            if self.player.hp <= 0:
                self.write_line("You succumb to your wounds... Game Over!")
                self.btn_save.config(state=tk.DISABLED)
                self.command_entry.config(state=tk.DISABLED)
                self.btn_pomo_start.config(state=tk.DISABLED)
                self.btn_pomo_stop.config(state=tk.DISABLED)
                self.pomodoro_running = False
                self.pomodoro_in_break = False

    def show_tasks(self):
        tasks_str = []
        tasks_str.append("Your tasks:")
        tasks_str.append(f"1) Complete a daily job:       [{'Done' if self.player.tasks['complete_daily_job'] else 'Not Done'}]")
        tasks_str.append(f"2) Drink from a stream/river:  [{'Done' if self.player.tasks['drink_from_stream'] else 'Not Done'}]")
        tasks_str.append(f"3) Stun an opponent:           [{'Done' if self.player.tasks['stun_opponent'] else 'Not Done'}]")
        self.write_line("\n".join(tasks_str))


def main():
    root = tk.Tk()
    root.title("Python MUD + Pomodoro (Advanced)")
    root.geometry("900x700")
    root.iconbitmap("C:\mudpy\g12-rpg_97293.ico")
    app = MudGameGUI(master=root)
    app.mainloop()


if __name__ == "__main__":
    main()
