import json
import math
import sys
import traceback
import os

# =========================================================================
# 🛠️ CONFIGURAZIONE UTENTE
# =========================================================================
JSON_FILE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project\dataset\nba_tracking_data_tiny.json"

TARGET_GAME_ID = "0021500333" 
TARGET_EVENT_ID = "179"       

OUTPUT_FILENAME = "shot_metadata.json" 

# --- COSTANTI FISICHE ---
FRAME_RATE_FPS = 25.0
DELTA_TIME = 1.0 / FRAME_RATE_FPS 
MIN_Z_TRIGGER = 10.5 
PUSH_ACCEL_THRESHOLD = 15.0 
MAX_2D_DISTANCE_TO_SHOOTER = 4.0 
MIN_SHOT_DISTANCE_2D = 13.0  # Minimo per considerare un tiro (es. evitare hand-off vicini)

# --- FILTRO 3 PUNTI ---
MIN_3PT_DIST_METERS = 6.70
MIN_3PT_DIST_FEET = MIN_3PT_DIST_METERS * 3.28084 # ~22 piedi

# =========================================================================
# 📐 FUNZIONI HELPER
# =========================================================================
def get_basket_coords(player_team_id, home_team_id):
    if player_team_id == home_team_id: return (88.75, 25.0) 
    else: return (5.25, 25.0)

def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

# =========================================================================
# 🧠 LOGICA DI ANALISI (IL CUORE DEL CODICE)
# =========================================================================
def find_shot_release_nearest_teammate(event_data):
    moments = event_data.get('moments', [])
    if len(moments) < 5: return None

    try:
        home_team_id = int(event_data['home']['teamid'])
        if 'primary_info' in event_data:
             shooter_team_id = int(event_data['primary_info']['team_id'])
        else:
             shooter_team_id = int(event_data.get('possession_team_id', 0))
    except: return None
    
    # 1. PRE-CALCOLO FISICA PER TUTTI I FRAME
    # Creiamo una lista pulita con posizione e accelerazione Z per ogni frame
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
    # Usiamo un while per poter controllare manualmente l'indice 'i'
    i = 0
    while i < len(ball_data_history):
        curr = ball_data_history[i]
        
        # A. Se la palla è BASSA o dati non validi -> vai al prossimo frame
        if not curr['valid'] or curr['pos'][2] <= MIN_Z_TRIGGER:
            i += 1
            continue

        # B. TRIGGER ATTIVATO: La palla è alta (> 10.5 ft)
        # Ora cerchiamo all'indietro il momento del "Push" (Spinta/Rilascio)
        push_found = False
        shot_frame_index = -1
        shooter_id = None
        dist_to_basket = 0.0
        
        # Cerchiamo indietro dal frame corrente 'i' fino all'inizio
        for j in range(i, 1, -1):
            b_curr = ball_data_history[j]
            b_prev = ball_data_history[j-1] 
            
            # Se troviamo un picco di accelerazione (il rilascio)
            if b_curr['a_z'] > PUSH_ACCEL_THRESHOLD:
                # Recuperiamo i dati dei giocatori in quel momento
                moment_data = moments[j-1]
                ball_xy = (b_prev['pos'][0], b_prev['pos'][1])
                
                # Cerchiamo il compagno più vicino alla palla
                min_dist_player = float('inf')
                closest_player_id = None
                closest_player_pos = None

                for p in moment_data['player_coordinates']:
                    if int(p['teamid']) == shooter_team_id:
                        p_pos = (p['x'], p['y'])
                        d = calculate_distance_2d(ball_xy, p_pos)
                        if d < min_dist_player:
                            min_dist_player = d
                            closest_player_pos = p_pos
                            closest_player_id = p['playerid']
                
                # Se il giocatore è plausibilmente colui che ha tirato (distanza < 4ft)
                if min_dist_player < MAX_2D_DISTANCE_TO_SHOOTER:
                    basket_pos = get_basket_coords(shooter_team_id, home_team_id)
                    dist_to_basket = calculate_distance_2d(closest_player_pos, basket_pos)
                    
                    # Abbiamo i dati del potenziale tiro
                    shot_frame_index = b_prev['frame']
                    shooter_id = closest_player_id
                    push_found = True
                    break # Interrompiamo il ciclo 'for' all'indietro, abbiamo trovato il push
        
        # C. VALUTAZIONE DEL TIRO TROVATO
        if push_found:
            print(f"🧐 Frame {i} (Trigger) -> Push trovato a frame {shot_frame_index}. Distanza canestro: {dist_to_basket:.2f} ft")
            
            # 1. CONTROLLO DISTANZA 3 PUNTI
            if dist_to_basket >= MIN_3PT_DIST_FEET:
                print(f"✅ TIRO DA 3 VALIDO! ({dist_to_basket:.2f} ft)")
                return shot_frame_index, shooter_id
            else:
                # 2. SCARTO E AVANZAMENTO
                print(f"🚫 SCARTATO: Tiro da 2 punti o passaggio ({dist_to_basket:.2f} ft). Cerco oltre...")
                
                # Qui sta il trucco: Dato che questo arco di parabola appartiene a un tiro da 2,
                # non ha senso controllare il frame i+1, i+2 ecc.
                # Facciamo avanzare 'i' finché la palla non scende di nuovo sotto i 10.5 piedi.
                while i < len(ball_data_history) and ball_data_history[i]['pos'][2] > MIN_Z_TRIGGER:
                    i += 1
                
                # Quando il while finisce, 'i' è al punto in cui la palla è scesa.
                # Al prossimo giro del while principale, cercheremo una NUOVA salita.
                continue 

        # Se non abbiamo trovato push o abbiamo finito l'analisi di questo frame senza successo
        i += 1

    return None

# =========================================================================
# 🚀 MAIN
# =========================================================================
if __name__ == "__main__":
    try:
        # ... (Codice di caricamento file identico a prima) ...
        target_event = None
        print(f"Lettura file: {JSON_FILE_PATH}")
        
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                ev = json.loads(line)
                if str(ev.get('gameid')) == TARGET_GAME_ID and str(ev['event_info']['id']) == TARGET_EVENT_ID:
                    target_event = ev
                    break
        
        if target_event:
            result = find_shot_release_nearest_teammate(target_event)
            
            if result:
                frame, pid = result
                # Salvataggio...
                output = {"game_id": TARGET_GAME_ID, "event_id": TARGET_EVENT_ID, "player_id": pid, "shot_frame": frame}
                with open(OUTPUT_FILENAME, "w") as f_out: json.dump(output, f_out, indent=4)
                print(f"✅ Salvato: Player {pid} al frame {frame}")
            else:
                print("❌ Nessun tiro da 3 valido trovato.")
        else:
            print("❌ Evento non trovato.")

    except Exception as e:
        traceback.print_exc()