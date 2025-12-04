# serverR.py - Estrategia 100% Aleatoria compatible con Unity
# CORREGIDO: Error de inicialización de Agente y Puerto 5005

from flask import Flask, jsonify, request
from flask_cors import CORS
import numpy as np
import random

from mesa import Agent, Model
from mesa.space import SingleGrid

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN ---
OUTSIDE = 0
WALL = 1
CELL = 2
DOOR = 3
SMOKE = 4
FIRE = 5
POI = 6
DOOR_OPEN = 8

AP_MOVE = 1
AP_MOVE_CARRYING = 2
AP_EXTINGUISH_SMOKE = 1
AP_EXTINGUISH_FIRE = 2
AP_BREAK_WALL = 2
AP_OPEN_DOOR = 1
AP_PICKUP_VICTIM = 1

GAME_MAP = """FFFFFFFFFFFFFFFFFFFF
FMMMMMMMMMMMMDMMMMMF
FMCCCCCDCCCMCCCCCCMF
FMCCCCCMCCCDCCCCCCMF
FMCCCMMMMMMMMMMMMDMF
FDCCCMCCCCCCCCCDCCMF
FMCCCMCCCCCCCCCMCCMF
FMMMMMMMMDMMMMMMMMMF
FMCCCCCCCCCDCCCDCCMF
FMCCCCCCCCCMCCCMCCMF
FMMMMDMMMMMMMMMMMMMF
FFFFFFFFFFFFFFFFFFFF"""

class FirefighterAgent(Agent):
    # --- CORRECCIÓN AQUÍ: Añadimos unique_id ---
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model) # Pasamos ID y Modelo a la clase base
        self.firefighter_id = unique_id
        self.ap = 0
        self.carrying_victim = False

    def get_valid_moves(self):
        x, y = self.pos
        moves = []
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                cell_type = self.model.cells[nx][ny]
                if cell_type in [CELL, DOOR_OPEN, SMOKE, OUTSIDE]:
                    if self.model.grid.is_cell_empty((nx, ny)):
                        moves.append((nx, ny))
        return moves

    # --- ACCIONES ALEATORIAS ---

    def move_random(self):
        moves = self.get_valid_moves()
        if not moves:
            return False
        
        cost = AP_MOVE_CARRYING if self.carrying_victim else AP_MOVE
        if self.ap >= cost:
            new_pos = random.choice(moves)
            print(f"   🎲 Moviendo a {new_pos} (Costo: {cost})")
            self.model.grid.move_agent(self, new_pos)
            self.ap -= cost
            return True
        return False

    def extinguish_smoke(self):
        if self.ap < AP_EXTINGUISH_SMOKE: return False
        x, y = self.pos
        candidates = [(x,y)] + [(x+dx, y+dy) for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]]
        random.shuffle(candidates)
        
        for cx, cy in candidates:
            if 0 <= cx < self.model.width and 0 <= cy < self.model.height:
                if self.model.cells[cx][cy] == SMOKE:
                    print(f"   💨 Extinguiendo Humo en {(cx, cy)}")
                    self.model.cells[cx][cy] = CELL
                    self.model.stats["smokes_removed"] += 1
                    self.ap -= AP_EXTINGUISH_SMOKE
                    return True
        return False

    def extinguish_fire(self):
        if self.ap < AP_EXTINGUISH_FIRE: return False
        x, y = self.pos
        candidates = [(x,y)] + [(x+dx, y+dy) for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]]
        random.shuffle(candidates)
        
        for cx, cy in candidates:
            if 0 <= cx < self.model.width and 0 <= cy < self.model.height:
                if self.model.cells[cx][cy] == FIRE:
                    print(f"   💦 Extinguiendo Fuego en {(cx, cy)}")
                    self.model.cells[cx][cy] = SMOKE
                    self.model.stats["fires_extinguished"] += 1
                    self.ap -= AP_EXTINGUISH_FIRE
                    return True
        return False

    def break_wall(self):
        if self.ap < AP_BREAK_WALL: return False
        x, y = self.pos
        candidates = []
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                if self.model.cells[nx][ny] == WALL:
                    candidates.append((nx, ny))
        
        if candidates:
            wx, wy = random.choice(candidates)
            print(f"   🔨 Golpeando pared en {(wx, wy)}")
            self.model.wall_damage[(wx, wy)] = self.model.wall_damage.get((wx, wy), 0) + 2
            self.model.stats["building_damage"] += 2
            self.ap -= AP_BREAK_WALL
            if self.model.wall_damage[(wx, wy)] >= 2:
                print("      🧱 ¡Pared destruida!")
                self.model.cells[wx][wy] = CELL
                self.model.stats["walls_broken"] += 1
            return True
        return False

    def open_door(self):
        if self.ap < AP_OPEN_DOOR: return False
        x, y = self.pos
        candidates = []
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                if self.model.cells[nx][ny] == DOOR:
                    candidates.append((nx, ny))
        
        if candidates:
            dx, dy = random.choice(candidates)
            print(f"   🚪 Abriendo puerta en {(dx, dy)}")
            self.model.cells[dx][dy] = DOOR_OPEN
            self.model.stats["doors_opened"] += 1
            self.ap -= AP_OPEN_DOOR
            return True
        return False

    def pickup_victim(self):
        if self.ap < AP_PICKUP_VICTIM or self.carrying_victim: return False
        x, y = self.pos
        if (x, y) in self.model.pois:
            print(f"   🚑 Recogiendo víctima en {self.pos}")
            self.carrying_victim = True
            self.model.pois.remove((x, y))
            self.ap -= AP_PICKUP_VICTIM
            return True
        return False

    def drop_victim_outside(self):
        if not self.carrying_victim: return False
        x, y = self.pos
        if self.model.cells[x][y] == OUTSIDE:
            print(f"   ✅ ¡Víctima salvada en {self.pos}!")
            self.carrying_victim = False
            self.model.stats["victims_rescued"] += 1
            return True
        return False

    def get_available_actions(self):
        actions = []
        x, y = self.pos
        
        if self.get_valid_moves():
            cost = AP_MOVE_CARRYING if self.carrying_victim else AP_MOVE
            if self.ap >= cost: actions.append("MOVE")
        
        if self.ap >= AP_EXTINGUISH_SMOKE:
            for dx, dy in [(0,0), (0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                    if self.model.cells[nx][ny] == SMOKE:
                        actions.append("EXTINGUISH_SMOKE"); break
        
        if self.ap >= AP_EXTINGUISH_FIRE:
            for dx, dy in [(0,0), (0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                    if self.model.cells[nx][ny] == FIRE:
                        actions.append("EXTINGUISH_FIRE"); break
        
        if self.ap >= AP_BREAK_WALL:
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                    if self.model.cells[nx][ny] == WALL:
                        actions.append("BREAK_WALL"); break
        
        if self.ap >= AP_OPEN_DOOR:
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.model.width and 0 <= ny < self.model.height:
                    if self.model.cells[nx][ny] == DOOR:
                        actions.append("OPEN_DOOR"); break
        
        if self.ap >= AP_PICKUP_VICTIM and not self.carrying_victim:
            if (x, y) in self.model.pois: actions.append("PICKUP_VICTIM")
        
        if self.carrying_victim and self.model.cells[x][y] == OUTSIDE:
            actions.append("DROP_VICTIM")
            
        actions.append("WAIT")
        return actions

    def do_turn(self):
        if not self.model.running: return
        self.ap = 4
        print(f"\n--- 🎲 TURNO RANDOM Agente {self.firefighter_id} en {self.pos} ---")
        
        while self.ap > 0:
            if self.carrying_victim:
                x, y = self.pos
                if self.model.cells[x][y] == OUTSIDE:
                    self.drop_victim_outside()
                    continue
            
            actions = self.get_available_actions()
            
            if len(actions) == 1 and actions[0] == "WAIT":
                print("   💤 Sin acciones posibles.")
                break
            
            filtered_actions = [a for a in actions if a != "WAIT"]
            if not filtered_actions:
                action = "WAIT"
            else:
                action = random.choice(filtered_actions)
            
            success = False
            if action == "MOVE": success = self.move_random()
            elif action == "EXTINGUISH_SMOKE": success = self.extinguish_smoke()
            elif action == "EXTINGUISH_FIRE": success = self.extinguish_fire()
            elif action == "BREAK_WALL": success = self.break_wall()
            elif action == "OPEN_DOOR": success = self.open_door()
            elif action == "PICKUP_VICTIM": success = self.pickup_victim()
            elif action == "DROP_VICTIM": success = self.drop_victim_outside()
            elif action == "WAIT": break
            
            if not success and action != "WAIT":
                break

class FlashPointModel(Model):
    def __init__(self, num_agents=6, max_pois=3):
        super().__init__()
        lines = GAME_MAP.strip().split('\n')
        self.height = len(lines)
        self.width = len(lines[0])
        self.grid = SingleGrid(self.width, self.height, torus=False)
        self.firefighters = []
        self.cells = np.zeros((self.width, self.height), dtype=int)
        self.wall_damage = {}
        self.pois = set()
        self.max_active_pois = max_pois
        
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                if char == 'F': self.cells[x][y] = OUTSIDE
                elif char == 'M': 
                    self.cells[x][y] = WALL
                    self.wall_damage[(x,y)] = 0
                elif char == 'C': self.cells[x][y] = CELL
                elif char == 'D': self.cells[x][y] = DOOR

        self.stats = {
            "victims_rescued": 0, "victims_lost": 0, "fires_extinguished": 0,
            "smokes_removed": 0, "smokes_spawned": 0, "explosions": 0,
            "building_damage": 0, "doors_opened": 0, "walls_broken": 0
        }

        self.spawn_agents(num_agents)
        self.spawn_initial_fires(3)
        for _ in range(self.max_active_pois): self.spawn_poi()

        self.steps = 0
        self.running = True
        self.game_result = None
        self.current_agent_index = 0

    def get_all_cells(self):
        cells = []
        for x in range(self.width):
            for y in range(self.height):
                if self.cells[x][y] in [CELL, DOOR_OPEN, SMOKE]:
                    cells.append((x, y))
        return cells

    def spawn_agents(self, num_agents):
        positions = [(0, 4), (0, 5), (0, 6), (13, 0), (14, 0), (15, 0)]
        
        limit = min(num_agents, len(positions))
        
        for i in range(limit):
            pos = positions[i]
            
            # Crear el agente usando 'i' como ID
            agent = FirefighterAgent(i, self)
            
            self.grid.place_agent(agent, pos)
            self.firefighters.append(agent)

    def spawn_initial_fires(self, count):
        candidates = []
        for x in range(self.width):
            for y in range(self.height):
                if self.cells[x][y] == CELL:
                    candidates.append((x,y))
        
        for _ in range(count):
            if not candidates: break
            pos = random.choice(candidates)
            candidates.remove(pos)
            self.cells[pos[0]][pos[1]] = FIRE

    def spawn_poi(self):
        if len(self.pois) >= self.max_active_pois: return False
        candidates = []
        for x in range(self.width):
            for y in range(self.height):
                if self.cells[x][y] == CELL and (x, y) not in self.pois:
                    if self.grid.is_cell_empty((x,y)):
                        candidates.append((x, y))
        if candidates:
            pos = random.choice(candidates)
            self.pois.add(pos)
            return True
        return False

    def spawn_smoke_random(self):
        x = random.randint(1, self.width-2)
        y = random.randint(1, self.height-2)
        current = self.cells[x][y]
        
        if current == SMOKE:
            print(f"🔥 ¡El humo en {x},{y} se convirtió en FUEGO!")
            self.cells[x][y] = FIRE
            self.stats["smokes_spawned"] += 1
        elif current == FIRE:
            self.trigger_explosion(x, y)
        elif current == CELL:
            self.cells[x][y] = SMOKE
            self.stats["smokes_spawned"] += 1

    def trigger_explosion(self, x, y):
        print(f"💥 ¡EXPLOSIÓN en {x},{y}!")
        self.stats["explosions"] += 1
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if self.cells[nx][ny] == WALL:
                    self.wall_damage[(nx, ny)] = self.wall_damage.get((nx, ny), 0) + 1
                    self.stats["building_damage"] += 1
                    if self.wall_damage[(nx, ny)] >= 2:
                        print(f"   🧱 Pared destruida por explosión en {nx},{ny}")
                        self.cells[nx][ny] = CELL
                elif self.cells[nx][ny] != OUTSIDE:
                    self.cells[nx][ny] = FIRE

    def check_end_conditions(self):
        if self.stats["victims_rescued"] >= 7:
            print("🎉 ¡GANASTE! Se rescataron 7 víctimas.")
            self.running = False
            self.game_result = "WIN"
        elif self.stats["building_damage"] >= 24:
            print("🏚️ ¡PERDISTE! El edificio colapsó.")
            self.running = False
            self.game_result = "LOSE COLLAPSADOS"
        elif self.stats["victims_lost"] >= 4:
            print("💀 ¡PERDISTE! Demasiadas víctimas.")
            self.running = False
            self.game_result = "LOSE DEMASIADAS VICTIMAS"

    def step(self):
        if not self.running: return
        agent = self.firefighters[self.current_agent_index]
        agent.do_turn()
        self.spawn_smoke_random()
        
        while len(self.pois) < self.max_active_pois:
            self.spawn_poi()
            
        self.check_end_conditions()
        self.current_agent_index = (self.current_agent_index + 1) % len(self.firefighters)
        self.steps += 1

    def get_state_json(self):
        cells_list = []
        for x in range(self.width):
            for y in range(self.height):
                cells_list.append({
                    "x": int(x), "y": int(y),
                    "state": int(self.cells[x][y]),
                    "damage": int(self.wall_damage.get((x,y), 0))
                })
        agents_list = []
        for agent in self.firefighters:
            agents_list.append({
                "id": int(agent.firefighter_id),
                "x": int(agent.pos[0]), "y": int(agent.pos[1]),
                "carrying_victim": agent.carrying_victim,
                "ap_remaining": agent.ap
            })
        
        current_id = self.firefighters[self.current_agent_index].firefighter_id if self.firefighters else -1
        
        return {
            "step": self.steps,
            "running": self.running,
            "game_result": self.game_result,
            "width": self.width, "height": self.height,
            "current_agent": current_id,
            "cells": cells_list,
            "agents": agents_list,
            "pois": [{"x":p[0], "y":p[1]} for p in self.pois],
            "stats": self.stats
        }

# --- API FLASK ---
model = None

@app.route('/init', methods=['POST'])
def init():
    global model
    data = request.get_json() or {}
    model = FlashPointModel(
        num_agents=data.get('num_agents', 6),
        max_pois=data.get('max_pois', 3)
    )
    print("🤖 Simulación RANDOM iniciada")
    return jsonify(model.get_state_json())

@app.route('/step', methods=['POST'])
def step():
    if not model: return jsonify({"error": "Init first"}), 400
    model.step()
    return jsonify(model.get_state_json())

@app.route('/reset', methods=['POST'])
def reset():
    global model
    model = FlashPointModel()
    print("🔄 Simulación Reiniciada")
    return jsonify(model.get_state_json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)