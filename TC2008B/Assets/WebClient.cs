using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

public class WebClient : MonoBehaviour
{
    [Header("Configuración del Servidor")]
    public string serverURL = "http://localhost:5000";
    
    [Header("Configuración del Grid")]
    [Tooltip("Posición de la esquina (0,0) del mapa en Unity")]
    public Vector3 gridOrigin = new Vector3(0, 0, 0);
    
    [Tooltip("Tamaño de cada celda en X")]
    public float cellSizeX = 1.45f;  // 32/22 ≈ 1.45
    
    [Tooltip("Tamaño de cada celda en Z")]
    public float cellSizeZ = 2.75f;  // 44/16 ≈ 2.75
    
    [Tooltip("Altura Y para los objetos")]
    public float objectHeight = 0.5f;
    
    [Header("Prefabs")]
    public GameObject firefighterPrefab;
    public GameObject firePrefab;
    public GameObject smokePrefab;
    public GameObject victimPrefab;  // POI
    
    [Header("Simulación")]
    public float stepInterval = 1.0f;  // Segundos entre cada step
    public bool autoStep = false;     
    
    [Header("Debug")]
    public bool showDebugLogs = true;
    
    // Referencias a objetos instanciados
    private Dictionary<int, GameObject> firefighters = new Dictionary<int, GameObject>();
    private List<GameObject> fireObjects = new List<GameObject>();
    private List<GameObject> smokeObjects = new List<GameObject>();
    private List<GameObject> victimObjects = new List<GameObject>();
    
    // Estado actual
    private SimulationState currentState;
    private bool isSimulationRunning = false;
    private float stepTimer = 0f;
    
    void Start()
    {
        StartCoroutine(InitializeSimulation());
    }
    
    void Update()
    {
        // Auto-step si está habilitado
        if (autoStep && isSimulationRunning)
        {
            stepTimer += Time.deltaTime;
            if (stepTimer >= stepInterval)
            {
                stepTimer = 0f;
                StartCoroutine(StepSimulation());
            }
        }
        
        // Controles manuales
        if (Input.GetKeyDown(KeyCode.Space))
        {
            StartCoroutine(StepSimulation());
        }
        
        if (Input.GetKeyDown(KeyCode.R))
        {
            StartCoroutine(ResetSimulation());
        }
        
        if (Input.GetKeyDown(KeyCode.A))
        {
            autoStep = !autoStep;
            Debug.Log("Auto-step: " + (autoStep ? "ON" : "OFF"));
        }
    }
    
    /// <summary>
    /// Convierte coordenadas del grid (Mesa) a posición en Unity
    /// </summary>
    Vector3 GridToWorldPosition(int x, int y)
    {
        return new Vector3(
            gridOrigin.x + (x * cellSizeX),
            objectHeight,
            gridOrigin.z - (y * cellSizeZ)  
        );
    }
    
    /// <summary>
    /// Inicializa la simulación llamando a /init
    /// </summary>
    IEnumerator InitializeSimulation()
    {
        string url = serverURL + "/init";
        
        using (UnityWebRequest www = new UnityWebRequest(url, "POST"))
        {
            www.downloadHandler = new DownloadHandlerBuffer();
            www.SetRequestHeader("Content-Type", "application/json");
            
            // Body vacío o con configuración
            string body = "{\"num_agents\": 6, \"max_pois\": 3}";
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(body);
            www.uploadHandler = new UploadHandlerRaw(bodyRaw);
            
            yield return www.SendWebRequest();
            
            if (www.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError("Error al inicializar: " + www.error);
                Debug.LogError("¿Está corriendo el servidor en " + serverURL + "?");
            }
            else
            {
                string json = www.downloadHandler.text;
                if (showDebugLogs) Debug.Log("Simulación inicializada: " + json);
                
                currentState = JsonUtility.FromJson<SimulationState>(json);
                isSimulationRunning = currentState.running;
                
                UpdateVisualization();
                
                Debug.Log($"=== FLASHPOINT INICIADO ===");
                Debug.Log($"Grid: {currentState.width}x{currentState.height}");
                Debug.Log($"Agentes: {currentState.agents.Count}");
                Debug.Log($"Controles: SPACE=Step, R=Reset, A=AutoStep");
            }
        }
    }
    
    /// <summary>
    /// Avanza un paso de la simulación
    /// </summary>
    IEnumerator StepSimulation()
    {
        if (!isSimulationRunning)
        {
            Debug.Log("Simulación terminada. Presiona R para reiniciar.");
            yield break;
        }
        
        string url = serverURL + "/step";
        
        using (UnityWebRequest www = new UnityWebRequest(url, "POST"))
        {
            www.downloadHandler = new DownloadHandlerBuffer();
            www.SetRequestHeader("Content-Type", "application/json");
            
            yield return www.SendWebRequest();
            
            if (www.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError("Error en step: " + www.error);
            }
            else
            {
                string json = www.downloadHandler.text;
                if (showDebugLogs) Debug.Log("Step recibido: " + json);
                
                currentState = JsonUtility.FromJson<SimulationState>(json);
                isSimulationRunning = currentState.running;
                
                UpdateVisualization();
                
                // Mostrar estadísticas
                Debug.Log($"Step {currentState.step} | " +
                         $"Rescatados: {currentState.stats.victims_rescued}/7 | " +
                         $"Daño: {currentState.stats.building_damage}/24");
                
                // Verificar fin del juego
                if (!currentState.running)
                {
                    Debug.Log($"=== JUEGO TERMINADO: {currentState.game_result} ===");
                    autoStep = false;
                }
            }
        }
    }
    
    /// <summary>
    /// Reinicia la simulación
    /// </summary>
    IEnumerator ResetSimulation()
    {
        // Limpiar objetos existentes
        ClearAllObjects();
        
        string url = serverURL + "/reset";
        
        using (UnityWebRequest www = new UnityWebRequest(url, "POST"))
        {
            www.downloadHandler = new DownloadHandlerBuffer();
            www.SetRequestHeader("Content-Type", "application/json");
            
            string body = "{\"num_agents\": 6, \"max_pois\": 3}";
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(body);
            www.uploadHandler = new UploadHandlerRaw(bodyRaw);
            
            yield return www.SendWebRequest();
            
            if (www.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError("Error al reiniciar: " + www.error);
            }
            else
            {
                string json = www.downloadHandler.text;
                currentState = JsonUtility.FromJson<SimulationState>(json);
                isSimulationRunning = currentState.running;
                
                UpdateVisualization();
                Debug.Log("=== SIMULACIÓN REINICIADA ===");
            }
        }
    }
    
    /// <summary>
    /// Actualiza todos los objetos visuales basado en el estado actual
    /// </summary>
    void UpdateVisualization()
    {
        if (currentState == null) return;
        
        UpdateFirefighters();
        UpdateCellEffects();  // Fuego y humo
        UpdateVictims();
    }
    
    /// <summary>
    /// Actualiza posición de los bomberos
    /// </summary>
    void UpdateFirefighters()
    {
        foreach (var agent in currentState.agents)
        {
            Vector3 pos = GridToWorldPosition(agent.x, agent.y);

            Debug.Log($"Agente {agent.id}: Mesa({agent.x}, {agent.y}) -> Unity{pos}");

            
            if (firefighters.ContainsKey(agent.id))
            {
                // Mover bombero existente
                GameObject ff = firefighters[agent.id];
                ff.transform.position = pos;
                
                // Cambiar color si lleva víctima (opcional)
                if (agent.carrying_victim)
                {
                    // Puedes cambiar el material o agregar un indicador visual
                    ff.transform.localScale = new Vector3(1.2f, 1.2f, 1.2f);
                }
                else
                {
                    ff.transform.localScale = Vector3.one;
                }
            }
            else
            {
                // Crear nuevo bombero
                if (firefighterPrefab != null)
                {
                    GameObject ff = Instantiate(firefighterPrefab, pos, Quaternion.identity);
                    ff.name = $"Firefighter_{agent.id}";
                    firefighters[agent.id] = ff;
                }
                else
                {
                    Debug.LogWarning("firefighterPrefab no asignado!");
                }
            }
        }
    }
    
    /// <summary>
    /// Actualiza fuego y humo basado en el estado de las celdas
    /// </summary>
    void UpdateCellEffects()
    {
        // Limpiar fuego y humo anteriores
        foreach (var obj in fireObjects) Destroy(obj);
        foreach (var obj in smokeObjects) Destroy(obj);
        fireObjects.Clear();
        smokeObjects.Clear();
        
        foreach (var cell in currentState.cells)
        {
            Vector3 pos = GridToWorldPosition(cell.x, cell.y);
            
            if (cell.state == CellState.FIRE)
            {
                if (firePrefab != null)
                {
                    GameObject fire = Instantiate(firePrefab, pos, Quaternion.identity);
                    fire.name = $"Fire_{cell.x}_{cell.y}";
                    fireObjects.Add(fire);
                }
            }
            else if (cell.state == CellState.SMOKE)
            {
                if (smokePrefab != null)
                {
                    GameObject smoke = Instantiate(smokePrefab, pos, Quaternion.identity);
                    smoke.name = $"Smoke_{cell.x}_{cell.y}";
                    smokeObjects.Add(smoke);
                }
            }
        }
    }
    
    /// <summary>
    /// Actualiza las víctimas (POIs)
    /// </summary>
    void UpdateVictims()
    {
        // Limpiar víctimas anteriores
        foreach (var obj in victimObjects) Destroy(obj);
        victimObjects.Clear();
        
        foreach (var poi in currentState.pois)
        {
            Vector3 pos = GridToWorldPosition(poi.x, poi.y);
            
            if (victimPrefab != null)
            {
                GameObject victim = Instantiate(victimPrefab, pos, Quaternion.identity);
                victim.name = $"Victim_{poi.x}_{poi.y}";
                victimObjects.Add(victim);
            }
        }
    }
    
    /// <summary>
    /// Limpia todos los objetos instanciados
    /// </summary>
    void ClearAllObjects()
    {
        foreach (var ff in firefighters.Values) Destroy(ff);
        foreach (var obj in fireObjects) Destroy(obj);
        foreach (var obj in smokeObjects) Destroy(obj);
        foreach (var obj in victimObjects) Destroy(obj);
        
        firefighters.Clear();
        fireObjects.Clear();
        smokeObjects.Clear();
        victimObjects.Clear();
    }
    
    /// <summary>
    /// UI de debug en pantalla
    /// </summary>
    void OnGUI()
    {
        if (currentState == null) return;
        
        GUIStyle style = new GUIStyle();
        style.fontSize = 20;
        style.normal.textColor = Color.white;
        
        int y = 10;
        int lineHeight = 25;
        
        GUI.Label(new Rect(10, y, 400, 30), $"Step: {currentState.step}", style);
        y += lineHeight;
        
        GUI.Label(new Rect(10, y, 400, 30), $"Rescatados: {currentState.stats.victims_rescued}/7", style);
        y += lineHeight;
        
        GUI.Label(new Rect(10, y, 400, 30), $"Victimas perdidas: {currentState.stats.victims_lost}/4", style);
        y += lineHeight;

        GUI.Label(new Rect(10, y, 400, 30), $"Daño edificio: {currentState.stats.building_damage}/24", style);
        y += lineHeight;
        
        GUI.Label(new Rect(10, y, 400, 30), $"Estado: {(isSimulationRunning ? "Running" : currentState.game_result)}", style);
        y += lineHeight;
                
        style.fontSize = 14;
    }
}