import bpy
import json
import math
import sys
import traceback

# =========================================================================
# 🛠️ CONFIGURAZIONE UTENTE
# =========================================================================
JSON_FILE_PATH = r"C:\Users\miklo\Desktop\Sport-Tech-Project\nba_tracking_data_tiny.json" 
TARGET_EVENT_ID = "4"  # <--- INSERISCI QUI L'ID CHE VUOI TESTARE

# --- COSTANTI FISICHE E REGOLE ---
FRAME_RATE_FPS = 25.0
DELTA_TIME = 1.0 / FRAME_RATE_FPS 
MIN_Z_TRIGGER = 10.5           # Altezza minima per attivare la ricerca (piedi)
PUSH_ACCEL_THRESHOLD = 15.0    # Accelerazione Z minima per essere una "spinta" (ft/s^2)
MAX_2D_DISTANCE_TO_SHOOTER = 4.0 # Distanza massima palla-giocatore per il possesso (piedi)
MIN_SHOT_DISTANCE_2D = 13.0    # Distanza minima dal canestro per considerare il tiro (piedi)

SHOT_EVENT_TYPES = [1, 2]      # 1: Segnato, 2: Sbagliato

# =========================================================================
# 📢 LOG DI AVVIO
# =========================================================================
print("\n" + "="*60)
print(f"🚀 START DEBUGGING: Rilevamento Tiro (Nearest Teammate Logic)")
print(f"📄 File: {JSON_FILE_PATH}")
print(f"🎯 Cerco Evento ID: {TARGET_EVENT_ID}")
print(f"📏 Regola Distanza Canestro: > {MIN_SHOT_DISTANCE_2D} ft")
print("="*60 + "\n")

# =========================================================================
# 📐 FUNZIONI HELPER
# =========================================================================
def get_basket_coords(player_team_id, home_team_id):
    # Se il team è HOME, tira verso il canestro a destra (X ~ 89)
    # Se il team è VISITORS, tira verso il canestro a sinistra (X ~ 5)
    if player_team_id == home_team_id:
        return (88.75, 25.0) 
    else:
        return (5.25, 25.0)

def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

# =========================================================================
# 🧠 LOGICA DI RILEVAMENTO
# =========================================================================
def find_shot_release_nearest_teammate(event_data):
    
    moments = event_data['moments']
    num_moments = len(moments)
    print(f"📊 Analisi Dati: L'evento contiene {num_moments} momenti (frames).")
    
    if num_moments < 3: 
        print("❌ ERRORE: Troppi pochi momenti per calcolare la fisica.")
        return None

    home_team_id = int(event_data['home']['teamid'])
    
    # 1. IDENTIFICHIAMO IL TEAM CHE TIRA
    try:
        shooter_team_id = int(event_data['primary_info']['team_id'])
    except:
        print("❌ ERRORE CRITICO: Impossibile leggere il Team ID dai metadati.")
        return None
    
    print(f"🏀 Squadra Attaccante (ID): {shooter_team_id}")

    # --- FASE 1: Calcolo Fisica Palla ---
    print("⚙️  Calcolo velocità e accelerazioni...", end="")
    ball_data_history = [] 
    for i in range(num_moments):
        m = moments[i]
        pos = (m['ball_coordinates']['x'], m['ball_coordinates']['y'], m['ball_coordinates']['z'])
        
        accel_z = 0.0
        if i > 1:
            prev_z = moments[i-1]['ball_coordinates']['z']
            prev_prev_z = moments[i-2]['ball_coordinates']['z']
            v_z = (pos[2] - prev_z) / DELTA_TIME
            v_z_prev = (prev_z - prev_prev_z) / DELTA_TIME
            accel_z = (v_z - v_z_prev) / DELTA_TIME

        frame_num = int(round((moments[0]['game_clock'] - m['game_clock']) * FRAME_RATE_FPS))

        ball_data_history.append({
            'pos': pos, 'frame': frame_num, 'a_z': accel_z, 'moment_index': i
        })
    print(" Fatto.")

    # --- FASE 2: Trigger Altezza ---
    trigger_index = -1
    for i in range(len(ball_data_history)):
        if ball_data_history[i]['pos'][2] > MIN_Z_TRIGGER:
            trigger_index = i
            print(f"🔔 TRIGGER ALTEZZA ATTIVATO: Z={ball_data_history[i]['pos'][2]:.2f} ft al Frame {ball_data_history[i]['frame']}")
            print("   --> Inizio ricerca a ritroso per la spinta...")
            break
            
    if trigger_index == -1:
        print(f"❌ FALLITO: La palla non ha mai superato i {MIN_Z_TRIGGER} ft di altezza.")
        return None

    # --- FASE 3: Ricerca Inversa (Nearest Teammate) ---
    for i in range(trigger_index, 1, -1):
        curr = ball_data_history[i]
        prev = ball_data_history[i-1] # Frame candidato rilascio
        
        # Se rileviamo una spinta forte verso l'alto
        if curr['a_z'] > PUSH_ACCEL_THRESHOLD:
            
            print(f"\n🔎 Frame {prev['frame']}: Spinta rilevata (Acc Z: {curr['a_z']:.2f})")
            
            moment_data = moments[i-1]
            ball_pos_2d = (prev['pos'][0], prev['pos'][1])
            
            # Cerchiamo il compagno PIÙ VICINO
            min_dist_teammate = float('inf')
            closest_teammate_pos = None
            closest_teammate_id = "Nessuno"
            
            for p in moment_data['player_coordinates']:
                # FILTRO: Solo giocatori della squadra che attacca
                if int(p['teamid']) == shooter_team_id:
                    p_pos = (p['x'], p['y'])
                    dist = calculate_distance_2d(ball_pos_2d, p_pos)
                    
                    if dist < min_dist_teammate:
                        min_dist_teammate = dist
                        closest_teammate_pos = p_pos
                        closest_teammate_id = p['playerid']
            
            print(f"   👀 Compagno più vicino ID: {closest_teammate_id} (Dist: {min_dist_teammate:.2f} ft)")

            # VERIFICA 1: Vicinanza Palla-Giocatore
            if min_dist_teammate < MAX_2D_DISTANCE_TO_SHOOTER:
                
                # VERIFICA 2: Distanza dal Canestro
                basket_pos = get_basket_coords(shooter_team_id, home_team_id)
                dist_to_basket = calculate_distance_2d(closest_teammate_pos, basket_pos)
                
                if dist_to_basket >= MIN_SHOT_DISTANCE_2D:
                    print(f"   ✅ SUCCESSO! Distanza canestro: {dist_to_basket:.2f} ft (Valida > {MIN_SHOT_DISTANCE_2D})")
                    print(f"\n🎉 RILASCIO CONFERMATO AL FRAME {prev['frame']}")
                    return prev['frame']
                else:
                     print(f"   ❌ SCARTATO: Tiro troppo vicino al canestro ({dist_to_basket:.2f} ft). Cercato > {MIN_SHOT_DISTANCE_2D}.")
            
            else:
                 print(f"   ❌ SCARTATO: Giocatore troppo lontano dalla palla (> {MAX_2D_DISTANCE_TO_SHOOTER} ft).")

    print("\n❌ ESITO FINALE: Nessun rilascio valido trovato nei frame precedenti al trigger.")
    return None

# =========================================================================
# 🎬 ESECUZIONE PRINCIPALE
# =========================================================================
try:
    target_event = None
    found_id = False
    
    # Lettura File JSON
    with open(JSON_FILE_PATH, 'r') as f:
        for line in f:
            try:
                ev = json.loads(line)
                # Verifica ID
                if str(ev['event_info']['id']).strip() == str(TARGET_EVENT_ID).strip():
                    found_id = True
                    ev_type = ev['event_info']['type']
                    print(f"✅ ID {TARGET_EVENT_ID} trovato nel file! (Tipo: {ev_type})")
                    
                    if ev_type in SHOT_EVENT_TYPES:
                        target_event = ev
                        print("   --> Tipo evento valido (Tiro). Procedo con l'analisi.")
                        break
                    else:
                        print(f"   ❌ ID trovato ma il tipo ({ev_type}) non è un tiro (1 o 2). Stop.")
                        break
            except: pass

    # Avvio Analisi se evento valido
    if target_event:
        bpy.context.scene.render.fps = int(FRAME_RATE_FPS)
        frame = find_shot_release_nearest_teammate(target_event)
        
        if frame is not None:
            bpy.context.scene.frame_current = frame
            bpy.context.scene.frame_start = max(0, frame - 50)
            bpy.context.scene.frame_end = frame + 20
            print(f"\n🛑 ANIMAZIONE POSIZIONATA SUL FRAME {frame}")
    elif not found_id:
        print(f"\n❌ ERRORE: ID Evento {TARGET_EVENT_ID} non presente nel file JSON.")

except Exception as e:
    print(f"\n❌ ERRORE CRITICO PYTHON: {e}")
    traceback.print_exc()

print("\n" + "="*60)
print("FINE SCRIPT")
print("="*60)