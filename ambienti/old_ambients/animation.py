import bpy
import os
import json

# --- IMPOSTAZIONI DA PERSONALIZZARE ---
JSON_FILE_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\nba_tracking_data_tiny.json" 
TARGET_EVENT_ID = "273" 
OUTPUT_VIDEO_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\animazioni"
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
    if "ShotClockText" in bpy.data.objects:
        bpy.data.objects["ShotClockText"].select_set(True)
        bpy.ops.object.delete()

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
                        print(f"✅ Evento {TARGET_EVENT_ID} TrovATO alla riga {i+1}!")
                        break
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
                
    if event is None:
        raise Exception(f"ERRORE: Evento con ID '{TARGET_EVENT_ID}' non trovato nel file.")

    # --- 2. Impostazioni Scena ---
    bpy.context.scene.render.fps = 25
    
    # --- 3. Crea lo Shot Clock ---
    bpy.ops.object.text_add(location=convert_coords(47, 25, 15)) 
    shot_clock_obj = bpy.context.active_object
    shot_clock_obj.name = "ShotClockText"
    shot_clock_obj.data.size = 4
    shot_clock_obj.data.align_x = 'CENTER'
    shot_clock_obj.data.align_y = 'CENTER'
    shot_clock_obj.rotation_euler = (0, 0, 0) 
    sc_mat = bpy.data.materials.new(name="ShotClock_Mat")
    sc_mat.use_nodes = True
    sc_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    shot_clock_obj.data.materials.append(sc_mat)

    # --- 4. Mappa Giocatori (ROBUSTA) ---
    print("Mappatura giocatori ID -> Oggetti 3D...")
    player_id_to_object_name_map = {}
    
    home_obj_names = [f"player_{i}" for i in range(5)]
    visitor_obj_names = [f"player_{i}" for i in range(5, 10)]
    
    home_team_id = event['home']['teamid']
    visitor_team_id = event['visitor']['teamid']
    first_moment = event['moments'][0]
    
    for p_data in first_moment['player_coordinates']:
        # FORZA L'ID A ESSERE UNA STRINGA
        player_id_str = str(p_data['playerid']) 
        team_id = p_data['teamid']
        
        if team_id == home_team_id:
            if home_obj_names:
                obj_name = home_obj_names.pop(0) 
                player_id_to_object_name_map[player_id_str] = obj_name # Usa la stringa
                print(f"  [HOME - Rosso] PlayerID {player_id_str} -> {obj_name}")
        elif team_id == visitor_team_id:
            if visitor_obj_names:
                obj_name = visitor_obj_names.pop(0) 
                player_id_to_object_name_map[player_id_str] = obj_name # Usa la stringa
                print(f"  [VISITOR - Blu] PlayerID {player_id_str} -> {obj_name}")
            
    print(f"Mappatura completata. {len(player_id_to_object_name_map)} giocatori mappati.")

    # --- 5. Ciclo di Animazione (CON DEBUG MIRATO) ---
    print("Inizio creazione keyframes...")
    start_game_clock = event['moments'][0]['game_clock']
    ball_obj = bpy.data.objects["ball"]
    num_moments = len(event['moments'])
    
    # Flag per stampare il debug solo una volta
    debug_stampato = False 
    
    for i, moment in enumerate(event['moments']):
        current_game_clock = moment['game_clock']
        frame_num = int(round((start_game_clock - current_game_clock) * 25))
        bpy.context.scene.frame_set(frame_num)
        
        if i % 50 == 0: 
           print(f"  Processo moment {i}/{num_moments} (Frame: {frame_num})")

        # --- A. Anima la Palla ---
        ball_coords_nba = moment['ball_coordinates']
        ball_obj.location = convert_coords(ball_coords_nba['x'], ball_coords_nba['y'], ball_coords_nba['z'])
        ball_obj.keyframe_insert(data_path="location", frame=frame_num)

        # --- B. Anima i Giocatori (ROBUSTO + DEBUG COORDINATE) ---
        for p_data in moment['player_coordinates']:
            # FORZA L'ID A ESSERE UNA STRINGA
            player_id_str = str(p_data['playerid']) 
            obj_name = player_id_to_object_name_map.get(player_id_str) # Cerca la stringa
            
            if obj_name:
                player_obj = bpy.data.objects[obj_name]
                
                # Leggi le coordinate NBA
                nba_x = p_data['x']
                nba_y = p_data['y']
                nba_z = p_data['z']
                
                # STAMPA DI DEBUG (solo per il primo frame)
                if i == 0 and debug_stampato == False: # (Usa il flag 'debug_stampato' che abbiamo già)
                    print(f"    -> DEBUG (Frame 0): {obj_name} (ID: {player_id_str}) -> DATI LETTI: (x={nba_x:.1f}, y={nba_y:.1f}, z={nba_z:.1f})")

                # Applica le coordinate
                player_obj.location = convert_coords(nba_x, nba_y, nba_z)
                player_obj.keyframe_insert(data_path="location", frame=frame_num)
        
        # Imposta il flag dopo aver processato tutti i giocatori del primo frame
        if i == 0:
            debug_stampato = True
            
        # # --- C. Anima lo Shot Clock ---
        # shot_clock_val = moment.get('shot_clock')
        # if shot_clock_val is not None:
        #     shot_clock_obj.data.body = f"{shot_clock_val:.1f}"
        #     shot_clock_obj.data.keyframe_insert(data_path="body", frame=frame_num)
    
      
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

# ######################################################################
# --- FASE 4: IMPOSTAZIONI DI RENDER E OUTPUT ---
# ######################################################################
# (Questa parte rimane invariata)
print("\n--- Inizio FASE 4: Impostazioni di Render ---")
try:
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT' 
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    safe_event_id = TARGET_EVENT_ID.replace("_", "-")
    final_output_filename = f"evento_{safe_event_id}.mp4"
    scene.render.filepath = os.path.join(OUTPUT_VIDEO_PATH, final_output_filename)
    print(f"Impostazioni di rendering configurate. Output su: {scene.render.filepath}")
except Exception as e:
    print(f"ERRORE durante la Fase 4 (Render): {e}")

print("\n--- SCRIPT DI ANIMAZIONE COMPLETATO ---")