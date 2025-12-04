using System;
using System.Collections.Generic;

[Serializable]
public class Cell
{
    public int x;
    public int y;
    public int state;
    public int damage;
}

[Serializable]
public class Agent
{
    public int id;
    public int x;
    public int y;
    public bool carrying_victim;
    public int ap_remaining;
}

[Serializable]
public class Poi
{
    public int x;
    public int y;
}

[Serializable]
public class Stats
{
    public int victims_rescued;
    public int victims_lost;
    public int fires_extinguished;
    public int smokes_removed;
    public int smokes_spawned;
    public int explosions;
    public int building_damage;
    public int doors_opened;
    public int walls_broken;
}

[Serializable]
public class SimulationState
{
    public int step;
    public bool running;
    public string game_result;
    public int width;
    public int height;
    public List<Cell> cells;
    public List<Agent> agents;
    public List<Poi> pois;
    public Stats stats;
}

// Constantes para los estados de celda (deben coincidir con Python)
public static class CellState
{
    public const int OUTSIDE = 0;
    public const int WALL = 1;
    public const int CELL = 2;
    public const int DOOR = 3;
    public const int SMOKE = 4;
    public const int FIRE = 5;
    public const int POI = 6;
    public const int DOOR_OPEN = 8;
}