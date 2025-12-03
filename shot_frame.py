import json
import math
import sys
import traceback
import os

# =========================================================================
# 🛠️ CONFIGURAZIONE UTENTE
# =========================================================================
JSON_FILE_PATH = r"C:\Users\miklo\Desktop\Sport-Tech-Project\dataset_3pt.json" 

# ORA FILTRIAMO PER ENTRAMBI
TARGET_GAME_ID = "0021500333" # <--- Inserisci qui il GAME ID corretto (es. dal nome del file o dai dati)
TARGET_EVENT_ID = "215"       # <--- Inserisci qui l'EVENT ID

OUTPUT_FILENAME = "shot_metadata.json" 

# --- COSTANTI FISICHE ---
FRAME_RATE_FPS = 25.0
DELTA_TIME = 1.0 / FRAME_RATE_FPS 
MIN_Z_TRIGGER = 10.5 
PUSH_ACCEL_THRESHOLD = 15.0 
MAX_2D_DISTANCE_TO_SHOOTER = 4.0 
MIN_SHOT_DISTANCE_2D = 13.0 

# =========================================================================
# 📐 FUNZIONI HELPER (Invariate)
# =========================================================================
def get_basket_coords(player_team_id, home_team_id):
    if player_team_id == home_team_id: return (88.75, 25.0) 
    else: return (5.25, 25.0)

def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

# =========================================================================
# 🧠 LOGICA DI ANALISI
# =========================================================================
def find_shot_release_nearest_teammate(event_data):
    moments = event_data.get('moments', [])
    if len(moments) < 5: return None

    try:
        home_team_id = int(event_data['home']['teamid'])
        # A volte primary_info non c'è, gestiamo l'errore
        if 'primary_info' in event_data:
             shooter_team_id = int(event_data['primary_info']['team_id'])
        else:
             # Fallback: prova a dedurlo dal possessore (meno preciso ma utile)
             shooter_team_id = int(event_data.get('possession_team_id', 0))
    except: return None
    
    # 1. Calcolo Fisica
    ball_data_history = [] 
    for i in range(len(moments)):
        m = moments[i]
        pos = (m['ball_coordinates']['x'], m['ball_coordinates']['y'], m['ball_coordinates']['z'])
        
        accel_z = 0.0
        if i > 1:
            prev_z = moments[i-1]['ball_coordinates']['z']
            prev_prev_z = moments[i-2]['ball_coordinates']['z']
            v_z = (pos[2] - prev_z) / DELTA_TIME
            v_z_prev = (prev_z - prev_prev_z) / DELTA_TIME
            accel_z = (v_z - v_z_prev) / DELTA_TIME

        ball_data_history.append({'pos': pos, 'a_z': accel_z, 'frame': i})

    # 2. Trigger Altezza
    trigger_index = -1
    for i in range(len(ball_data_history)):
        if ball_data_history[i]['pos'][2] > MIN_Z_TRIGGER:
            trigger_index = i
            break
            
    if trigger_index == -1: return None

    # 3. Ricerca Inversa Spinta
    for i in range(trigger_index, 1, -1):
        curr = ball_data_history[i]
        prev = ball_data_history[i-1] 
        
        if curr['a_z'] > PUSH_ACCEL_THRESHOLD:
            moment_data = moments[i-1]
            ball_pos_2d = (prev['pos'][0], prev['pos'][1])
            
            min_dist_teammate = float('inf')
            closest_teammate_id = None
            closest_teammate_pos = None
            
            for p in moment_data['player_coordinates']:
                if int(p['teamid']) == shooter_team_id:
                    p_pos = (p['x'], p['y'])
                    dist = calculate_distance_2d(ball_pos_2d, p_pos)
                    
                    if dist < min_dist_teammate:
                        min_dist_teammate = dist
                        closest_teammate_pos = p_pos
                        closest_teammate_id = p['playerid']
            
            if min_dist_teammate < MAX_2D_DISTANCE_TO_SHOOTER:
                basket_pos = get_basket_coords(shooter_team_id, home_team_id)
                dist_to_basket = calculate_distance_2d(closest_teammate_pos, basket_pos)
                
                if dist_to_basket >= MIN_SHOT_DISTANCE_2D:
                    return prev['frame'], closest_teammate_id 
    return None

# =========================================================================
# 🚀 MAIN E SALVATAGGIO
# =========================================================================
if __name__ == "__main__":
    try:
        target_event = None
        print(f"Lettura file: {JSON_FILE_PATH}")
        print(f"Cercando GameID: {TARGET_GAME_ID} | EventID: {TARGET_EVENT_ID}...")
        
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line in ['[', ']']: continue
                if line.endswith(','): line = line[:-1]
                
                try:
                    ev = json.loads(line)
                    
                    # --- ESTRAZIONE ID ---
                    # Gestiamo sia stringhe che int convertendo tutto a stringa pulita
                    json_game_id = str(ev.get('gameid', '')).strip()
                    json_event_id = str(ev.get('event_info', {}).get('id', '')).strip()
                    
                    # --- DOPPIO CONTROLLO ---
                    if json_game_id == str(TARGET_GAME_ID) and json_event_id == str(TARGET_EVENT_ID):
                        print(f"✅ TROVATO! Game {json_game_id}, Event {json_event_id}")
                        target_event = ev
                        break
                except: pass

        if target_event:
            result = find_shot_release_nearest_teammate(target_event)
            
            if result:
                frame_idx, player_id = result
                
                # --- DATI DA SALVARE ---
                output_data = {
                    "game_id": TARGET_GAME_ID,   # <--- Aggiunto
                    "event_id": TARGET_EVENT_ID,
                    "player_id": player_id,
                    "shot_frame": frame_idx,
                    "source_file": JSON_FILE_PATH
                }

                # Percorso di salvataggio
                output_path = os.path.join(os.getcwd(), OUTPUT_FILENAME)
                
                with open(output_path, "w", encoding='utf-8') as f_out:
                    json.dump(output_data, f_out, indent=4)
                
                print("\n" + "="*50)
                print(f"💾 FILE PONTE SALVATO: {OUTPUT_FILENAME}")
                print(f"--------------------------------------------------")
                print(f"GAME ID    : {TARGET_GAME_ID}")
                print(f"EVENT ID   : {TARGET_EVENT_ID}")
                print(f"PLAYER ID  : {player_id}")
                print(f"FRAME TIRO : {frame_idx}")
                print("="*50)

            else:
                print("❌ Trovato l'evento, ma l'analisi fisica non ha rilevato il tiro.")
        else:
            print(f"❌ Nessun evento trovato con GameID {TARGET_GAME_ID} e EventID {TARGET_EVENT_ID}.")

    except Exception as e:
        print(f"❌ Errore critico: {e}")
        traceback.print_exc()