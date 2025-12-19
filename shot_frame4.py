import json
import math
import sys
import traceback
import os

# =========================================================================
# 🛠️ CONFIGURAZIONE UTENTE
# =========================================================================
JSON_FILE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project\nba_tracking_data_tiny.json" #DA CAMBIARE

TARGET_GAME_ID = "0021500333" 
TARGET_EVENT_ID = "43"       

OUTPUT_FILENAME = "shot_metadata.json" 

# --- COSTANTI FISICHE ---
FRAME_RATE_FPS = 25.0
DELTA_TIME = 1.0 / FRAME_RATE_FPS 
MIN_Z_TRIGGER = 10.5 
PUSH_ACCEL_THRESHOLD = 15.0 
MAX_2D_DISTANCE_TO_SHOOTER = 4 
ASSUMED_PLAYER_Z = 6.5
MAX_3D_DISTANCE_TO_BALL = 3.0

# --- FILTRO 3 PUNTI ---
MIN_3PT_DIST_METERS = 6.5
MIN_3PT_DIST_FEET = MIN_3PT_DIST_METERS * 3.28084 # ~22 piedi

# --- COORDINATE CANESTRI FISSI ---
BASKET_LEFT = (5.25, 25.0)
BASKET_RIGHT = (88.75, 25.0)

# =========================================================================
# 📐 FUNZIONI HELPER
# =========================================================================
def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def format_clock(seconds):
    if seconds is None: return "00:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def get_player_name_by_id(event_data, target_id):
    # Cerca tra i giocatori home e visitor
    for team_key in ['home', 'visitor']:
        for p in event_data.get(team_key, {}).get('players', []):
            if str(p['playerid']) == str(int(target_id)):
                return f"{p['firstname']} {p['lastname']}"
    return "Unknown"

# =========================================================================
# 🧠 LOGICA DI ANALISI
# =========================================================================
def find_shot_release_nearest_teammate(event_data):
    moments = event_data.get('moments', [])
    if len(moments) < 5: return None

    try:
        # Non ci serve più l'home_team_id per capire il canestro, 
        # ma ci serve shooter_team_id per filtrare i compagni
        if 'primary_info' in event_data:
             shooter_team_id = int(event_data['primary_info']['team_id'])
        else:
             shooter_team_id = int(event_data.get('possession_team_id', 0))
    except: return None
    
    # 1. PRE-CALCOLO FISICA PER TUTTI I FRAME
    ball_data_history = [] 
    for i in range(len(moments)):
        m = moments[i]
        if 'ball_coordinates' not in m:
            ball_data_history.append({'pos': (0,0,0), 'a_z': 0, 'frame': i, 'valid': False})
            continue

        pos = (m['ball_coordinates']['x'], m['ball_coordinates']['y'], m['ball_coordinates']['z'])
        
        accel_z = 0.0
        if i > 1:
            prev_z = moments[i-1]['ball_coordinates']['z']
            prev_prev_z = moments[i-2]['ball_coordinates']['z']
            v_z = (pos[2] - prev_z) / DELTA_TIME
            v_z_prev = (prev_z - prev_prev_z) / DELTA_TIME
            accel_z = (v_z - v_z_prev) / DELTA_TIME

        ball_data_history.append({'pos': pos, 'a_z': accel_z, 'frame': i, 'valid': True})

    # 2. SCANSIONE TEMPORALE (LOOP)
    i = 0
    while i < len(ball_data_history):
        curr = ball_data_history[i]
        
        # A. Se la palla è BASSA o dati non validi -> vai al prossimo frame
        if not curr['valid'] or curr['pos'][2] <= MIN_Z_TRIGGER:
            i += 1
            continue

        print(f"--- TRIGGER ATTIVATO al frame {i} (Z={curr['pos'][2]:.2f}) ---")

        # B. TRIGGER ATTIVATO: La palla è alta (> 10.5 ft)
        push_found = False
        shot_frame_index = -1
        shooter_id = None
        closest_player_pos = (0, 0) # Placeholder
        dist_to_basket = 0.0
        
        home_id = event_data.get('home', {}).get('teamid')
        visitor_id = event_data.get('visitor', {}).get('teamid')

        # Cerchiamo indietro dal frame corrente 'i' fino all'inizio
        for j in range(i, 1, -1):
            b_curr = ball_data_history[j]
            b_prev = ball_data_history[j-1] 

            # Se troviamo un picco di accelerazione (il rilascio)
            if b_curr['a_z'] > PUSH_ACCEL_THRESHOLD:
                moment_data = moments[j-1]
                ball_xy = (b_prev['pos'][0], b_prev['pos'][1])
                print(f"🔥 PICCO ACCELERAZIONE trovato al frame {j}: {b_curr['a_z']:.2f}")
                
                # Cerchiamo il compagno più vicino alla palla
                min_dist_3d = float('inf')
                temp_closest_pos = None
                temp_closest_id = None
                temp_side = "Unknown"

                for p in moment_data['player_coordinates']:
                    # Rimosso il filtro: if int(p['teamid']) == shooter_team_id:
                    
                    p_pos_2d = (p['x'], p['y'])
                    dist_2d = calculate_distance_2d(ball_xy, p_pos_2d)
                    
                    # Calcolo distanza 3D simulata: sqrt(dist_2d^2 + (z_palla - 6.5)^2)
                    dist_z = abs(b_prev['pos'][2] - ASSUMED_PLAYER_Z)
                    dist_3d = math.sqrt(dist_2d**2 + dist_z**2)

                    if dist_3d < min_dist_3d:
                        min_dist_3d = dist_3d
                        temp_closest_pos = p_pos_2d
                        temp_closest_id = p['playerid']

                        # Identificazione lato
                        p_team_id = int(p['teamid'])
                        if p_team_id == home_id:
                            temp_side = "home"
                        elif p_team_id == visitor_id:
                            temp_side = "visitor"

                # Debug per capire se è un difensore o attaccante
                if temp_closest_id:
                    # Recuperiamo il nome per il log
                    p_name = get_player_name_by_id(event_data, temp_closest_id)
                    print(f"   👤 {temp_side.upper()} | {p_name} (ID: {temp_closest_id}) a {min_dist_3d:.2f} ft")
                else:
                    print(f"   ⚠️ Nessun compagno trovato vicino alla palla al frame {j}")

                # Se il giocatore è plausibilmente colui che ha tirato
                if min_dist_3d < MAX_2D_DISTANCE_TO_SHOOTER:
                    closest_player_pos = temp_closest_pos
                    
                    # --- MODIFICA LOGICA DISTANZA ---
                    # Calcoliamo la distanza da entrambi i canestri
                    dist_left = calculate_distance_2d(closest_player_pos, BASKET_LEFT)
                    dist_right = calculate_distance_2d(closest_player_pos, BASKET_RIGHT)
                    
                    # Consideriamo la distanza minore (la palla è vicina a QUEL canestro?)
                    # O meglio: siamo lontani da QUALSIASI canestro per essere da 3?
                    # Se min(d_left, d_right) > 22ft, allora siamo lontani da entrambi i ferri.
                    dist_to_basket = min(dist_left, dist_right)
                    
                    shot_frame_index = b_prev['frame']
                    shooter_id = temp_closest_id
                    push_found = True
                    break 
        
        # C. VALUTAZIONE DEL TIRO TROVATO
        if push_found:
            print(f"🧐 Frame {i} (Trigger) -> Push a frame {shot_frame_index}. Pos: {closest_player_pos}. Distanza dal ferro più vicino: {dist_to_basket:.2f} ft")
            
            # 1. CONTROLLO DISTANZA 3 PUNTI (Sulla distanza minore calcolata)
            if dist_to_basket >= MIN_3PT_DIST_FEET:
                print(f"✅ TIRO DA 3 VALIDO! ({dist_to_basket:.2f} ft)")
                # Restituiamo anche le coordinate x, y
                return shot_frame_index, shooter_id, closest_player_pos[0], closest_player_pos[1], moments[shot_frame_index]
            else:
                # 2. SCARTO E AVANZAMENTO
                print(f"🚫 SCARTATO: Distanza insufficiente ({dist_to_basket:.2f} ft). Cerco oltre...")
                
                while i < len(ball_data_history) and ball_data_history[i]['pos'][2] > MIN_Z_TRIGGER:
                    i += 1
                continue 

        i += 1

    return None

# =========================================================================
# 🚀 MAIN
# =========================================================================
if __name__ == "__main__":
    try:
        target_event = None
        print(f"Lettura file: {JSON_FILE_PATH}")
        
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                ev = json.loads(line)
                # --- MODIFICA: Controllo ID e salvo l'evento ---
                if str(ev.get('gameid')) == TARGET_GAME_ID and str(ev['event_info']['id']) == TARGET_EVENT_ID:
                    target_event = ev
                    break
        
        if target_event:
            # --- MODIFICA: Stampa Event Type ---
            event_type = target_event['event_info'].get('type', 'N/A')
            print(f"📂 Evento Trovato! ID: {TARGET_EVENT_ID}, Type: {event_type}")

            result = find_shot_release_nearest_teammate(target_event)
            
            if result:
                # Unpacking di 5 valori ora
                frame, pid, shot_x, shot_y, shot_moment = result
                
                # 1. Recupero nome dal primary_info (come richiesto)
                primary_pid = target_event.get('primary_info', {}).get('player_id', 0)
                primary_name = get_player_name_by_id(target_event, primary_pid)

                # 2. Preparazione dati Team
                home_team = target_event.get('home', {})
                visitor_team = target_event.get('visitor', {})

                poss_id = target_event.get('possession_team_id')
                if poss_id is None:
                    poss_id = target_event.get('event_info', {}).get('possession_team_id')
                if poss_id is None:
                    poss_id = target_event.get('primary_info', {}).get('team_id')

                output = {
                    "game_id": TARGET_GAME_ID,
                    "game_date": target_event.get('gamedate'),
                    "event_id": TARGET_EVENT_ID,
                    "event_type": event_type,
                    "possession_team_id": poss_id,
                    "primary_player_name": primary_name,  # Nome del primary_info
                    "player_id": pid,            # ID di chi ha tirato davvero
                    "shot_frame": frame,
                    "period": shot_moment.get('quarter'),
                    "game_clock": format_clock(shot_moment.get('game_clock')),
                    "shot_clock": shot_moment.get('shot_clock'),
                    "shot_location_x": shot_x,
                    "shot_location_y": shot_y,
                    "teams": {
                        "home": {
                            "name": home_team.get('name'),
                            "team_id": home_team.get('teamid'),
                            "abbreviation": home_team.get('abbreviation')
                        },
                        "visitor": {
                            "name": visitor_team.get('name'),
                            "team_id": visitor_team.get('teamid'),
                            "abbreviation": visitor_team.get('abbreviation')
                        }
                    }
                }
                
                with open(OUTPUT_FILENAME, "w") as f_out: 
                    json.dump(output, f_out, indent=4)
                print(f"✅ Salvato: {primary_name} coinvolto, tiro rilevato per player {pid}")
            else:
                print("❌ Nessun tiro da 3 valido trovato.")
        else:
            print("❌ Evento non trovato.")

    except Exception as e:
        traceback.print_exc()