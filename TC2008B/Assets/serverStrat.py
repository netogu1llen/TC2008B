import heapq
from flask import Flask, jsonify, request
from flask_cors import CORS
import random
from typing import List, Tuple, Dict, Optional

from mesa import Agent, Model
from mesa.space import MultiGrid

app = Flask(__name__)
CORS(app)

MAP_LAYOUT = [
    "FFFFFFFFFFFFFFFFFFFF",
    "FMMMMMMMMMMMMDMMMMMF",
    "FMCCCCCDCCCMCCCCCCMF",
    "FMCCCCCMCCCDCCCCCCMF",
    "FMCCCMMMMMMMMMMMMDMF",
    "FDCCCMCCCCCCCCCDCCMF",
    "FMCCCMCCCCCCCCCMCCMF",
    "FMMMMMMMMDMMMMMMMMMF",
    "FMCCCCCCCCCDCCCDCCMF",
    "FMCCCCCCCCCMCCCMCCMF",
    "FMMMMDMMMMMMMMMMMMMF",
    "FFFFFFFFFFFFFFFFFFFF"
]

class Tile(Agent):
    def __init__(self, unique_id, model, pos, tile_type):
        super().__init__(unique_id, model)
        self.pos = pos
        self.type = tile_type  # M=Muro, D=Puerta, C=Celda, F=Fuera
        self.fire = 0
        self.smoke = 0
        self.damage = 0
        self.hasPOI = False
        self.walkable = tile_type in ("C", "D")


# Mensajes en consola Generados con IA
class FireFighter(Agent):
    def __init__(self, unique_id, model, pos, role):
        super().__init__(unique_id, model)
        self.role = role
        self.carrying = False
        self.action_points = 4

    def step(self):
        self.action_points = 4
        print(f"\nTURNO AGENTE {self.unique_id} ({self.role}) en {self.pos}")
        
        while self.action_points > 0 and self.model.running:
            # DEFINIR OBJETIVO
            target = None
            target_type = "Nada"
            
            if self.carrying:
                target = self.model.entryPoints[0]
                target_type = "SALIDA (Ambulancia)"
            else:
                if self.role == "APAGADOR":
                    target = self.model.get_nearest_hazard(self.pos)
                    target_type = "FUEGO/HUMO"
                    if target is None:
                        target = self.model.get_nearest_poi(self.pos)
                        target_type = "VICTIMA (Fallback)"

                elif self.role == "RESCATISTA":
                    target = self.model.get_nearest_poi(self.pos)
                    target_type = "VICTIMA"

                elif self.role == "COMODIN":
                    target = self.model.get_nearest_entity(self.pos)
                    target_type = "VICTIMA/FUEGO/HUMO"

            if target is None:
                return

            print(f"    Objetivo: {target} ({target_type})")

            # CALCULAR CAMINO
            path = self.model.get_path_astar(self.pos, target)
            
            if path is None or len(path) <= 1:
                return

            next_pos = path[1]
            next_tile = self.model.get_tile(next_pos)

            # EJECUTAR ACCIÓN
            
            # -- MOVIMIENTO Y OBSTÁCULOS --
            move_cost = 2 if self.carrying else 1

            if next_tile.type == "M":
                if self.action_points >= 2:
                    print(f"   ROMPIENDO en {next_pos} (Costo: 2 AP)")
                    next_tile.damage += 2
                    self.model.buildingDamage += 2
                    if next_tile.damage >= 2:
                        next_tile.type = "C"
                        next_tile.walkable = True
                        print("      🧱 ¡Pared destruida!")
                    self.action_points -= 2
                    continue 
                else:
                    print("   ❌ No hay AP para romper pared.")
                    return

            elif next_tile.type == "D":
                if self.action_points >= 1:
                    print(f"   🚪 ABRIENDO PUERTA en {next_pos} (Costo: 1 AP)")
                    next_tile.type = "C"
                    next_tile.walkable = True
                    self.action_points -= 1
                    continue
                else:
                    print("   ❌ No hay AP para abrir puerta.")
                    return

            # -- INTERACCIONES (Fuego/Humo) --
            if next_tile.fire == 1:
                if self.action_points >= 2:
                    print(f"   💦 EXTINGUIENDO FUEGO en {next_pos} (Costo: 2 AP)")
                    next_tile.fire = 0
                    next_tile.smoke = 1 
                    self.model.stats["fires_extinguished"] += 1
                    self.action_points -= 2
                    continue
                else:
                    print("   ❌ Fuego bloquea el paso y no hay AP suficiente.")
                    return
            
            elif next_tile.smoke == 1:
                if self.action_points >= 1:
                    print(f"   💨 DISIPANDO HUMO en {next_pos} (Costo: 1 AP)")
                    next_tile.smoke = 0
                    self.model.stats["smokes_removed"] += 1
                    self.action_points -= 1
                    continue
                else:
                    print("   ❌ Humo bloquea el paso y no hay AP suficiente.")
                    return

            # -- MOVERSE --
            if self.action_points >= move_cost:
                print(f"   🏃 MOVIENDO a {next_pos} (Costo: {move_cost} AP)")
                self.model.grid.move_agent(self, next_pos)
                self.action_points -= move_cost
            else:
                print("   ❌ No hay AP para moverse.")
                return

            # -- ACCIONES AUTOMÁTICAS POST-MOVIMIENTO --
            current_tile = self.model.get_tile(self.pos)
            
            # Recoger víctima
            if not self.carrying and current_tile.hasPOI:
                if self.action_points >= 1:
                    print(f"   🚑 RECOGIENDO VÍCTIMA en {self.pos} (Costo: 1 AP)")
                    self.carrying = True
                    current_tile.hasPOI = False
                    if self.pos in self.model.POIs:
                        self.model.POIs.remove(self.pos)
                    self.action_points -= 1
            
            # Entregar víctima
            if self.carrying and self.pos in self.model.entryPoints:
                print(f"   ✅ ¡VÍCTIMA SALVADA! en {self.pos}")
                self.carrying = False
                self.model.savedVictims += 1
                return

class FireModel(Model):
    def __init__(self):
        super().__init__()
        self.width = 20
        self.height = 12
        self.grid = MultiGrid(self.width, self.height, torus=False)
        self.tiles = {}
        self.POIs = []
        self.firefighters = []
        
        self.savedVictims = 0
        self.lostVictims = 0
        self.buildingDamage = 0
        self.entryPoints = [(1, 5)] # Ambulancia
        
        self.stats = {
            "victims_rescued": 0, "victims_lost": 0, "building_damage": 0,
            "fires_extinguished": 0, "smokes_removed": 0, "explosions": 0
        }
        
        self.running = True
        self.game_result = None
        self.steps = 0

        self._create_map()
        self._create_agents()
        self.spawn_pois()
        
        self.turn_order = self.get_turn_order()
        self.current_index = 0

    def _create_map(self):
        uid = 1000
        for y in range(self.height):
            for x in range(self.width):
                ch = MAP_LAYOUT[y][x]
                tile = Tile(uid, self, (x, y), ch)
                self.tiles[(x, y)] = tile
                self.grid.place_agent(tile, (x, y))
                uid += 1

    def _create_agents(self):
        # Roles definidos
        roles = ["APAGADOR", "RESCATISTA", "COMODIN",
                 "APAGADOR", "RESCATISTA", "COMODIN"]
        positions = [(0, 4), (0, 5), (0, 6), 
                     (13, 0), (14, 0), (15, 0)]
        
        for uid, (pos, role) in enumerate(zip(positions, roles)):
            ff = FireFighter(uid, self, pos, role)
            self.grid.place_agent(ff, pos)
            self.firefighters.append(ff)

    def get_tile(self, pos):
        return self.tiles.get(pos)

    # --- BÚSQUEDA DE OBJETIVOS ---

    # Se busca punto de interes (POI) basado en la distancia Manhattan
    def get_nearest_poi(self, pos):
        if not self.POIs: return None
        return min(self.POIs, key=lambda p: abs(p[0]-pos[0]) + abs(p[1]-pos[1]))

    # Busca fuego o humo basado en la distancia Manhattan
    def get_nearest_hazard(self, pos):
        """Busca fuego o humo"""
        hazards = [p for p, t in self.tiles.items() if t.fire > 0 or t.smoke > 0]
        if not hazards: return None
        return min(hazards, key=lambda p: abs(p[0]-pos[0]) + abs(p[1]-pos[1]))

    # Busqueda mixta de POI o peligro, Manhattan
    def get_nearest_entity(self, pos):
        targets = self.POIs + [p for p, t in self.tiles.items() if t.fire > 0 or t.smoke > 0]
        if not targets: return None
        return min(targets, key=lambda p: abs(p[0]-pos[0]) + abs(p[1]-pos[1]))

    #  PATHFINDING A* (Para preferir puertas sobre muros)
    def get_path_astar(self, start, end):
        if start == end: return [start]
        frontier = []
        heapq.heappush(frontier, (0, start))
        came_from = {start: None}
        cost_so_far = {start: 0}
        
        while frontier:
            _, current = heapq.heappop(frontier)
            
            if current == end:
                break
            
            x, y = current
            neighbors = []
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.tiles:
                    neighbors.append((nx, ny))
            
            for next_pos in neighbors:
                tile = self.tiles[next_pos]
                
                added_cost = 1 # Base move cost
                
                if tile.type == "M":
                    added_cost = 10 # Penalización altísima por muro
                elif tile.type == "D":
                    added_cost = 2  # Penalización leve por puerta (hay que abrirla)
                elif tile.fire > 0:
                    added_cost = 3  # Fuego es lento/peligroso
                
                new_cost = cost_so_far[current] + added_cost
                
                if next_pos not in cost_so_far or new_cost < cost_so_far[next_pos]:
                    cost_so_far[next_pos] = new_cost
                    priority = new_cost + (abs(end[0] - next_pos[0]) + abs(end[1] - next_pos[1])) # Heurística Manhattan
                    heapq.heappush(frontier, (priority, next_pos))
                    came_from[next_pos] = current
                    
        if end not in came_from:
            return None # No hay camino
            
        # Reconstruir camino
        path = []
        curr = end
        while curr is not None:
            path.append(curr)
            curr = came_from[curr]
        return path[::-1] # Invertir lista

    def count_total_pois(self):
        carrying = sum(1 for ff in self.firefighters if ff.carrying)
        return len(self.POIs) + carrying

    def spawn_pois(self, max_pois=3):
        while self.count_total_pois() < max_pois:
            candidates = [p for p, t in self.tiles.items() if t.type == "C" 
                          and not t.hasPOI and t.smoke == 0 and t.fire == 0]
            if not candidates: break
            pos = random.choice(candidates)
            self.tiles[pos].hasPOI = True
            self.POIs.append(pos)

    def spread_smoke(self):
        candidates = [p for p, t in self.tiles.items() if t.type == "C" and not t.hasPOI]
        if not candidates: return
        pos = random.choice(candidates)
        tile = self.tiles[pos]
        if tile.smoke == 0 and tile.fire == 0:
            tile.smoke = 1
        elif tile.smoke == 1:
            tile.smoke = 0; tile.fire = 1
        elif tile.fire == 1:
            self.explosion(pos)

    def explosion(self, pos):
        self.stats["explosions"] += 1
        print(f"💥 EXPLOSIÓN en {pos}!")
        # Daño en cruz
        self.check_explosion_damage(pos) # Centro
        x, y = pos
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            self.check_explosion_damage((x+dx, y+dy))

    def check_explosion_damage(self, pos):
        if pos not in self.tiles: return
        tile = self.tiles[pos]
        
        # Dañar Muro
        if tile.type == "M":
            tile.damage += 1
            self.buildingDamage += 1
            if tile.damage >= 2:
                tile.type = "C"; tile.walkable = True
        
        # Matar Víctima en suelo
        if tile.hasPOI:
            tile.hasPOI = False
            if pos in self.POIs: self.POIs.remove(pos)
            self.lostVictims += 1
            print(f" Víctima quemada en {pos}")

        # Herir Bombero (lo manda fuera, pierde víctima si carga)
        cell_contents = self.grid.get_cell_list_contents([pos])
        for obj in cell_contents:
            if isinstance(obj, FireFighter):
                self.send_to_outside(obj, victim_dies=True)

    def send_to_outside(self, ff, victim_dies=False):
        # Buscar la celda F más cercana
        start = ff.pos
        outside_cells = [p for p, t in self.tiles.items() if t.type == "F"]
        if not outside_cells: return
        target = min(outside_cells, key=lambda p: abs(p[0]-start[0]) + abs(p[1]-start[1]))
        
        self.grid.move_agent(ff, target)
        if ff.carrying:
            ff.carrying = False
            if victim_dies:
                self.lostVictims += 1
                print(f" Víctima perdida (bombero herido)")

    def get_turn_order(self):
        # Ordenar por rol para simular turnos organizados (opcional)
        return sorted(self.firefighters, key=lambda x: x.unique_id)

    def check_end_conditions(self):
        if self.savedVictims >= 7:
            self.running = False; self.game_result = "WIN"
        elif self.lostVictims >= 4:
            self.running = False; self.game_result = "LOSE VICTIMS"
        elif self.buildingDamage >= 24:
            self.running = False; self.game_result = "LOSE COLLAPSE"

    def get_state_json(self):
        # Serialización idéntica a la anterior
        cells = []
        for p, t in self.tiles.items():
            st = 0
            if t.type == "F": st=0
            elif t.type == "M": st=1
            elif t.type == "C": st=2
            elif t.type == "D": st=3
            if t.smoke: st=4
            if t.fire: st=5
            cells.append({"x":p[0], "y":p[1], "state":st, "damage":t.damage})
        
        agents = []
        for ff in self.firefighters:
            agents.append({
                "id": ff.unique_id, "x": ff.pos[0], "y": ff.pos[1],
                "role": ff.role, "carrying_victim": ff.carrying,
                "ap_remaining": ff.action_points
            })
            
        current = self.turn_order[self.current_index] if self.turn_order else None
        
        self.stats.update({
            "victims_rescued": self.savedVictims,
            "victims_lost": self.lostVictims,
            "building_damage": self.buildingDamage
        })

        return {
            "step": self.steps, "running": self.running, "game_result": self.game_result,
            "width": self.width, "height": self.height, 
            "current_agent": current.unique_id if current else -1,
            "cells": cells, "agents": agents, 
            "pois": [{"x":p[0], "y":p[1]} for p in self.POIs],
            "stats": self.stats
        }

    def step(self):
        if not self.running: return
        agent = self.turn_order[self.current_index]
        agent.step()
        self.spread_smoke()
        self.spawn_pois()
        self.check_end_conditions()
        self.current_index = (self.current_index + 1) % len(self.turn_order)
        self.steps += 1

# --- FLASK ---
model = None

@app.route('/init', methods=['POST'])
def init():
    global model; model = FireModel()
    return jsonify(model.get_state_json())

@app.route('/step', methods=['POST'])
def step_route():
    if not model: return jsonify({"error": "Init first"}), 400
    model.step()
    return jsonify(model.get_state_json())

@app.route('/reset', methods=['POST'])
def reset():
    global model; model = FireModel()
    return jsonify(model.get_state_json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)