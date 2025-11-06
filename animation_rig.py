import bpy
import os
import json
import math

# --- IMPOSTAZIONI DA PERSONALIZZARE ---
JSON_FILE_PATH = r"C:\Users\miklo\Desktop\Sport-Tech-Project\nba_tracking_data_tiny.json" 
TARGET_EVENT_ID = "273"
PLAYER_TEMPLATE_NAME = "player_rigged_template"  # Nome del template con rig
RUN_ANIMATION_NAME = "run"  # Nome dell'animazione di corsa
PLAYER_SCALE = 0.037 

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
            # Rimuovi completamente i player duplicati
            if obj_name.startswith("player_"):
                bpy.data.objects.remove(obj, do_unlink=True)
                print(f"Rimosso: {obj_name}")
            else:
                # Solo pulisci animazione per la palla
                obj.animation_data_clear()
    print("Pulizia completata.")

def setup_player_with_animation(template_name, new_name, action_name):
    """Duplica il template e imposta l'animazione"""
    
    if template_name not in bpy.data.objects:
        raise Exception(f"Template '{template_name}' non trovato!")
    
    template_obj = bpy.data.objects[template_name]
    
    # Deseleziona tutto
    bpy.ops.object.select_all(action='DESELECT')
    
    # Seleziona il template e tutti i suoi figli
    template_obj.select_set(True)
    for child in template_obj.children_recursive:
        child.select_set(True)
    
    # Duplica con gerarchia completa
    bpy.ops.object.duplicate(linked=False)
    
    # Ottieni il nuovo oggetto duplicato
    new_obj = bpy.context.selected_objects[0]
    new_obj.name = new_name
    
    # APPLICA LA SCALA
    new_obj.scale = (PLAYER_SCALE, PLAYER_SCALE, PLAYER_SCALE)
    
    # Imposta modalità rotazione Euler
    new_obj.rotation_mode = 'XYZ'
    
    # Trova l'armature e imposta l'animazione
    armature_obj = None
    if new_obj.type == 'ARMATURE':
        armature_obj = new_obj
    else:
        for child in new_obj.children:
            if child.type == 'ARMATURE':
                armature_obj = child
                break
    
    if armature_obj and action_name in bpy.data.actions:
        action = bpy.data.actions[action_name]
        if not armature_obj.animation_data:
            armature_obj.animation_data_create()
        armature_obj.animation_data.action = action
        print(f"✅ Animazione '{action_name}' assegnata a {new_name}")
    
    # Deseleziona tutto
    bpy.ops.object.select_all(action='DESELECT')
    
    return new_obj

try:
    cleanup_previous_animation()

    # Verifica template
    if PLAYER_TEMPLATE_NAME not in bpy.data.objects:
        raise Exception(f"ERRORE: Template '{PLAYER_TEMPLATE_NAME}' non trovato!")
    
    # Verifica animazione
    if RUN_ANIMATION_NAME not in bpy.data.actions:
        raise Exception(f"ERRORE: Animazione '{RUN_ANIMATION_NAME}' non trovata!")
    
    run_action = bpy.data.actions[RUN_ANIMATION_NAME]
    run_length = run_action.frame_range[1] - run_action.frame_range[0]
    print(f"✅ Template trovato: {PLAYER_TEMPLATE_NAME}")
    print(f"✅ Animazione trovata: {RUN_ANIMATION_NAME} (lunghezza: {run_length:.0f} frames)")

    # --- 1. Carica i dati JSON ---
    print(f"\nCaricamento dati da {JSON_FILE_PATH}...")
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

    # --- 3. Crea i 10 giocatori (COME VERSIONE 2) ---
    print("\nCreazione giocatori...")
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
                # Crea il giocatore dal template
                player_obj = setup_player_with_animation(PLAYER_TEMPLATE_NAME, obj_name, RUN_ANIMATION_NAME)
                player_id_to_object_name_map[player_id_str] = obj_name
                print(f"[HOME - Rosso] PlayerID {player_id_str} -> {obj_name}")
        elif team_id == visitor_team_id:
            if visitor_obj_names:
                obj_name = visitor_obj_names.pop(0)
                # Crea il giocatore dal template
                player_obj = setup_player_with_animation(PLAYER_TEMPLATE_NAME, obj_name, RUN_ANIMATION_NAME)
                player_id_to_object_name_map[player_id_str] = obj_name
                print(f"[VISITOR - Blu] PlayerID {player_id_str} -> {obj_name}")

    print(f"Mappatura completata. {len(player_id_to_object_name_map)} giocatori creati.")

    # Nascondi il template originale
    template_obj = bpy.data.objects[PLAYER_TEMPLATE_NAME]
    template_obj.hide_viewport = True
    template_obj.hide_render = True

    # --- 4. Ciclo di Animazione (COME VERSIONE 2 + LOOP ANIMAZIONE) ---
    print("\nInizio creazione keyframes...")
    start_game_clock = event['moments'][0]['game_clock']
    ball_obj = bpy.data.objects["ball"]
    num_moments = len(event['moments'])

    debug_stampato = False 

    for i, moment in enumerate(event['moments']):
        current_game_clock = moment['game_clock']
        frame_num = int(round((start_game_clock - current_game_clock) * 25))
        bpy.context.scene.frame_set(frame_num)

        if i % 50 == 0: 
            print(f"Processo moment {i}/{num_moments} (Frame: {frame_num})")

        # --- A. Anima la Palla ---
        ball_coords_nba = moment['ball_coordinates']
        ball_pos_2d = (ball_coords_nba['x'], ball_coords_nba['y'])
        ball_obj.location = convert_coords(ball_coords_nba['x'], ball_coords_nba['y'], ball_coords_nba['z'])
        ball_obj.keyframe_insert(data_path="location", frame=frame_num)

        # --- B. Anima i Giocatori ---
        for p_data in moment['player_coordinates']:
            player_id_str = str(p_data['playerid']) 
            obj_name = player_id_to_object_name_map.get(player_id_str)

            if obj_name and obj_name in bpy.data.objects:
                player_obj = bpy.data.objects[obj_name]

                # Leggi le coordinate NBA
                nba_x = p_data['x']
                nba_y = p_data['y']
                nba_z = p_data['z']

                # DEBUG (solo primo frame)
                if i == 0 and not debug_stampato:
                    print(f"-> DEBUG (Frame 0): {obj_name} (ID: {player_id_str}) -> ({nba_x:.1f}, {nba_y:.1f}, {nba_z:.1f})")

                # Applica le coordinate di POSIZIONE
                player_obj.location = convert_coords(nba_x, nba_y, nba_z)
                player_obj.keyframe_insert(data_path="location", frame=frame_num)

                # Calcola rotazione verso la palla
                current_pos_2d = (nba_x, nba_y)
                delta_to_ball_x = ball_pos_2d[0] - current_pos_2d[0]
                delta_to_ball_y = ball_pos_2d[1] - current_pos_2d[1]
                angle_z = math.atan2(delta_to_ball_x, delta_to_ball_y) + (math.pi / 2)
                
                player_obj.rotation_euler.z = angle_z
                player_obj.keyframe_insert(data_path="rotation_euler", frame=frame_num)
                
                # --- ANIMAZIONE RIG IN LOOP ---
                # Trova l'armature e anima il loop
                armature_obj = None
                if player_obj.type == 'ARMATURE':
                    armature_obj = player_obj
                else:
                    for child in player_obj.children:
                        if child.type == 'ARMATURE':
                            armature_obj = child
                            break
                
                if armature_obj and armature_obj.animation_data:
                    # Calcola il frame dell'animazione in loop
                    loop_frame = (frame_num % run_length)
                    
                    # Imposta il frame corrente dell'action
                    armature_obj.animation_data.action_frame = loop_frame
                    armature_obj.keyframe_insert(data_path='animation_data.action_frame', frame=frame_num)

        if i == 0:
            debug_stampato = True

    # --- 5. Imposta la Durata della Scena ---
    end_game_clock = event['moments'][-1]['game_clock']
    start_frame = 0
    end_frame = int(round((start_game_clock - end_game_clock) * 25))

    bpy.context.scene.frame_start = start_frame
    bpy.context.scene.frame_end = end_frame

    print(f"\n✅ Creazione keyframes completata.")
    print(f"✅ Animazione impostata da frame {start_frame} a {end_frame}.")
    print(f"✅ Scala giocatori: {PLAYER_SCALE}")

except Exception as e:
    print(f"\n❌ ERRORE CRITICO durante la Fase 3: {e}")
    import traceback
    traceback.print_exc()

print("\n--- SCRIPT DI ANIMAZIONE COMPLETATO ---")