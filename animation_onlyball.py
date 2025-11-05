import bpy
import os
import json
import math
# from collections import deque # RIMOSSO

# --- IMPOSTAZIONI DA PERSONALIZZARE ---
JSON_FILE_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\nba_tracking_data_tiny.json" 
TARGET_EVENT_ID = "273" 

# --- Soglia di velocità RIMOSSA ---
# SPEED_THRESHOLD = 0.3
# --- FINE IMPOSTAZIONI ---


# ######################################################################
# --- FASE 3: CARICAMENTO DATI E ANIMAZIONE ---
# ######################################################################

print("--- Inizio FASE 3: Animazione ---")

def convert_coords(nba_x, nba_y, nba_z):
    blender_x = nba_y
    blender_y = nba_x
    blender_z = nba_z
    return (blender_x, blender_y, blender_z)

def cleanup_previous_animation():
    print("Pulizia animazione precedente...")

    obj_names_to_clear = ["ball"] + [f"player_{i}" for i in range(10)]
    for obj_name in obj_names_to_clear:
        if obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            obj.animation_data_clear()
    print("Pulizia completata.")

try:
    cleanup_previous_animation()

    # --- 1. Carica i dati JSON ---
    print(f"Caricamento dati da {JSON_FILE_PATH}...")
    print(f"Ricerca di TARGET_EVENT_ID: {TARGET_EVENT_ID}")

    event = None
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                current_event = json.loads(line)
                if 'event_info' in current_event and \
                   isinstance(current_event['event_info'], dict) and \
                       'id' in current_event['event_info']:

                    event_id_from_file = str(current_event['event_info']['id']).strip()
                    target_id_str = str(TARGET_EVENT_ID).strip()

                    if event_id_from_file == target_id_str:
                        event = current_event
                        print(f"✅ Evento {TARGET_EVENT_ID} trovato alla riga {i+1}!")
                        break
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

    if event is None:
        raise Exception(f"ERRORE: Evento con ID '{TARGET_EVENT_ID}' non trovato nel file.")

    # --- 2. Impostazioni Scena ---
    bpy.context.scene.render.fps = 25

    # --- 4. Mappa Giocatori (ROBUSTA) ---
    print("Mappatura giocatori ID -> Oggetti 3D...")
    player_id_to_object_name_map = {}

    home_obj_names = [f"player_{i}" for i in range(5)]
    visitor_obj_names = [f"player_{i}" for i in range(5, 10)]

    home_team_id = event['home']['teamid']
    visitor_team_id = event['visitor']['teamid']
    first_moment = event['moments'][0]

    for p_data in first_moment['player_coordinates']:
        player_id_str = str(p_data['playerid']) 
        team_id = p_data['teamid']

        if team_id == home_team_id:
            if home_obj_names:
                obj_name = home_obj_names.pop(0) 
                player_id_to_object_name_map[player_id_str] = obj_name
                print(f"[HOME - Rosso] PlayerID {player_id_str} -> {obj_name}")
        elif team_id == visitor_team_id:
            if visitor_obj_names:
                obj_name = visitor_obj_names.pop(0) 
                player_id_to_object_name_map[player_id_str] = obj_name
                print(f"[VISITOR - Blu] PlayerID {player_id_str} -> {obj_name}")

    print(f"Mappatura completata. {len(player_id_to_object_name_map)} giocatori mappati.")
    
    print("Impostazione modalità di rotazione 'XYZ' (Euler) per i giocatori...")
    for player_id_str, obj_name in player_id_to_object_name_map.items():
        if obj_name in bpy.data.objects:
            player_obj = bpy.data.objects[obj_name]
            player_obj.rotation_mode = 'XYZ'
        else:
            print(f"ATTENZIONE: Oggetto {obj_name} non trovato durante impostazione Euler.")
    print("Modalità rotazione impostata.")

    # --- 5. Ciclo di Animazione (SOLO GUARDA PALLA) ---
    print("Inizio creazione keyframes...")
    start_game_clock = event['moments'][0]['game_clock']
    ball_obj = bpy.data.objects["ball"]
    num_moments = len(event['moments'])

    # --- Dizionari per la rotazione RIMOSSI ---
    # player_last_pos = {} 

    # Flag per stampare il debug solo una volta
    debug_stampato = False 

    for i, moment in enumerate(event['moments']):
        current_game_clock = moment['game_clock']
        frame_num = int(round((start_game_clock - current_game_clock) * 25))
        bpy.context.scene.frame_set(frame_num)

        if i % 50 == 0: 
            print(f"Processo moment {i}/{num_moments} (Frame: {frame_num})")

        # --- A. Anima la Palla ---
        ball_coords_nba = moment['ball_coordinates']
        ball_pos_2d = (ball_coords_nba['x'], ball_coords_nba['y']) # Posizione 2D palla
        ball_obj.location = convert_coords(ball_coords_nba['x'], ball_coords_nba['y'], ball_coords_nba['z'])
        ball_obj.keyframe_insert(data_path="location", frame=frame_num)

        # --- B. Anima i Giocatori (SOLO GUARDA PALLA) ---
        for p_data in moment['player_coordinates']:
            player_id_str = str(p_data['playerid']) 
            obj_name = player_id_to_object_name_map.get(player_id_str)

            if obj_name:
                player_obj = bpy.data.objects[obj_name]

                # Leggi le coordinate NBA
                nba_x = p_data['x']
                nba_y = p_data['y']
                nba_z = p_data['z']

                # STAMPA DI DEBUG (solo per il primo frame)
                if i == 0 and not debug_stampato:
                    print(f"-> DEBUG (Frame 0): {obj_name} (ID: {player_id_str}) -> DATI LETTI: (x={nba_x:.1f}, y={nba_y:.1f}, z={nba_z:.1f})")

                # Applica le coordinate di POSIZIONE
                player_obj.location = convert_coords(nba_x, nba_y, nba_z)
                player_obj.keyframe_insert(data_path="location", frame=frame_num)

                # --- INIZIO LOGICA DI ROTAZIONE (SOLO GUARDA PALLA) ---
                
                current_pos_2d = (nba_x, nba_y)
                
                # Calcola il vettore dal giocatore alla palla
                delta_to_ball_x = ball_pos_2d[0] - current_pos_2d[0]
                delta_to_ball_y = ball_pos_2d[1] - current_pos_2d[1]
                
                # Calcola l'angolo per guardare la palla (Convertito per Blender)
                # math.atan2(Y_Blender, X_Blender) - offset 90 gradi
                angle_z = math.atan2(delta_to_ball_x, delta_to_ball_y) + (math.pi / 2)
                
                # Applica la rotazione
                player_obj.rotation_euler.z = angle_z
                player_obj.keyframe_insert(data_path="rotation_euler", frame=frame_num)
                
                # --- FINE LOGICA DI ROTAZIONE ---

        # Imposta il flag dopo aver processato tutti i giocatori del primo frame
        if i == 0:
            debug_stampato = True

    # --- 6. Imposta la Durata della Scena ---
    end_game_clock = event['moments'][-1]['game_clock']
    start_frame = 0
    end_frame = int(round((start_game_clock - end_game_clock) * 25))

    bpy.context.scene.frame_start = start_frame
    bpy.context.scene.frame_end = end_frame

    print(f"Creazione keyframes completata.")
    print(f"Animazione impostata da frame {start_frame} a {end_frame}.")

except Exception as e:
    print(f"ERRORE CRITICO durante la Fase 3: {e}")
    import traceback
    traceback.print_exc()

print("\n--- SCRIPT DI ANIMAZIONE COMPLETATO ---")
print("L'animazione è caricata in Blender. Imposta manualmente il rendering se necessario.")