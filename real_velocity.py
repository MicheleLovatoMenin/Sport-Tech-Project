import bpy
import mathutils

# ==================== CONFIGURAZIONE ====================

ARMATURE_NAME = "Armature"

# Nomi delle ossa dei piedi (Controlla nel tuo rig!)
# Per Mixamo standard spesso è "mixamorig:LeftFoot" o "LeftFoot"
BONE_LEFT = "mixamorig:LeftFoot"
BONE_RIGHT = "mixamorig:RightFoot"

# === LISTA AGGIORNATA DELLE ANIMAZIONI ===
# Assumo che siano tutte locomozioni in AVANTI (FORWARD)
ACTIONS_TO_ANALYZE = [
    {"name": "walk",            "direction": "FORWARD"},
    {"name": "slow-run",        "direction": "FORWARD"},
    {"name": "fast_run",        "direction": "FORWARD"},
    {"name": "dribble_walk_dx", "direction": "FORWARD"},
    {"name": "dribble_walk_sx", "direction": "FORWARD"},
    {"name": "dribble_run_dx",  "direction": "FORWARD"},
    {"name": "dribble_run_sx",  "direction": "FORWARD"},
    {"name": "run_catch_dx",    "direction": "FORWARD"},
    {"name": "run_catch_sx",    "direction": "FORWARD"},
    {"name": "celly_lebron",    "direction": "FORWARD"} 
]

FPS = 120 # Il framerate del tuo progetto

# ==================== LOGICA DI CALCOLO ====================

def get_bone_speed(obj, action_name, bone_names, direction_mode="FORWARD"):
    """
    Calcola la velocità media del piede durante la fase di appoggio (Stance).
    """
    if action_name not in bpy.data.actions:
        print(f"⚠️ ATTENZIONE: Azione '{action_name}' non trovata nel file .blend. Salto.")
        return 0.0
    
    action = bpy.data.actions[action_name]
    
    # Salviamo lo stato attuale per ripristinarlo dopo
    prev_action = obj.animation_data.action
    obj.animation_data.action = action
    
    speeds = []
    
    # Range di analisi
    start_frame = int(action.frame_range[0])
    end_frame = int(action.frame_range[1])
    
    # Se l'animazione è troppo breve, evitiamo errori
    if end_frame - start_frame < 2:
        return 0.0

    print(f"--- Analisi: {action_name} ({direction_mode}) ---")
    
    # Per ogni frame dell'azione
    for f in range(start_frame, end_frame):
        bpy.context.scene.frame_set(f)
        
        # Analizziamo entrambi i piedi
        current_speeds_frame = []
        
        for b_name in bone_names:
            if b_name not in obj.pose.bones:
                continue
                
            pbone = obj.pose.bones[b_name]
            
            # Prendiamo la posizione Y globale (World Space)
            pos_curr = obj.matrix_world @ pbone.matrix.translation
            y_curr = pos_curr.y
            
            # Calcoliamo rispetto al frame precedente
            bpy.context.scene.frame_set(f - 1)
            pos_prev = obj.matrix_world @ pbone.matrix.translation
            y_prev = pos_prev.y
            
            # Torniamo al frame corrente per il prossimo ciclo
            bpy.context.scene.frame_set(f)
            
            # Calcolo Delta (Spostamento)
            delta_y = y_curr - y_prev
            
            valid_sample = False
            speed_sample = 0.0
            
            # FILTRO: Consideriamo solo quando il piede "spinge indietro" il terreno
            if direction_mode == "FORWARD":
                if delta_y < -0.005: # Piede va indietro (-Y)
                    valid_sample = True
                    speed_sample = abs(delta_y) * FPS
            
            elif direction_mode == "BACKWARD":
                if delta_y > 0.005: # Piede va avanti (+Y)
                    valid_sample = True
                    speed_sample = abs(delta_y) * FPS
            
            if valid_sample:
                current_speeds_frame.append(speed_sample)

        # Se almeno un piede era a terra, registriamo la velocità
        if current_speeds_frame:
            speeds.append(max(current_speeds_frame))

    # Ripristino azione originale
    if prev_action:
        obj.animation_data.action = prev_action
    else:
        obj.animation_data.action = None
    
    # Calcolo Media
    if len(speeds) > 0:
        avg_speed = sum(speeds) / len(speeds)
        return avg_speed
    else:
        return 0.0

# ==================== MAIN ====================

def main():
    obj = bpy.data.objects.get(ARMATURE_NAME)
    if not obj:
        print(f"❌ ERRORE: Oggetto '{ARMATURE_NAME}' non trovato.")
        return

    print("="*60)
    print("👟 CALIBRAZIONE VELOCITÀ MULTIPLA (M/S)")
    print("="*60)

    results = {}

    for item in ACTIONS_TO_ANALYZE:
        speed = get_bone_speed(
            obj, 
            item["name"], 
            [BONE_LEFT, BONE_RIGHT], 
            item["direction"]
        )
        
        if speed > 0:
            results[item["name"]] = speed
            print(f"👉 '{item['name']}': \t{speed:.4f} m/s")
        else:
            print(f"⚠️ '{item['name']}': \t0.0000 m/s (O ferma, o laterale, o non trovata)")

    print("-"*60)
    print("COPIA QUESTO BLOCCO NEL TUO SCRIPT PRINCIPALE:")
    print("-" * 30)
    
    for name, spd in results.items():
        # Pulisce il nome per renderlo una variabile valida (es. slow-run -> SLOW_RUN_SPEED)
        clean_name = name.upper().replace(" ", "_").replace("-", "_") + "_SPEED"
        print(f"{clean_name} = {spd:.4f}")
        
    print("-" * 30)
    print("="*60)

if __name__ == "__main__":
    main()