import bpy
import os
import json
import math

# --- IMPOSTAZIONI DA PERSONALIZZARE ---
JSON_FILE_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\nba_tracking_data_tiny.json" 
TARGET_EVENT_ID = "273"
PLAYER_TEMPLATE_NAME = "player_rigged_template"
RUN_ANIMATION_NAME = "run"
PLAYER_SCALE = 0.037 

# --- IMPOSTAZIONI ANIMAZIONE ---
ANIMATION_SPEED_MULTIPLIER = 2.0  # Velocità base animazione
USE_SPEED_BASED_ANIMATION = True  # Adatta velocità al movimento reale
MIN_SPEED_THRESHOLD = 0.3  # Soglia minima per animare (piedi/frame)

print("--- Inizio FASE 3: Animazione NBA ---")

def convert_coords(nba_x, nba_y, nba_z):
    blender_x = nba_y
    blender_y = nba_x
    blender_z = nba_z
    return (blender_x, blender_y, blender_z)

def cleanup_previous_animation():
    """Pulizia COMPLETA di tutto"""
    print("\n🧹 Pulizia completa scena...")
    
    # Rimuovi tutti i player duplicati
    obj_names_to_remove = [f"player_{i}" for i in range(20)]  # Margine di sicurezza
    for obj_name in obj_names_to_remove:
        if obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            # Rimuovi anche i figli (armature, mesh)
            for child in list(obj.children):
                bpy.data.objects.remove(child, do_unlink=True)
            bpy.data.objects.remove(obj, do_unlink=True)
            print(f"   Rimosso: {obj_name}")
    
    # Pulisci animazione della palla
    if "ball" in bpy.data.objects:
        ball = bpy.data.objects["ball"]
        if ball.animation_data:
            ball.animation_data_clear()
    
    # Pulisci NLA tracks orfani
    for obj in bpy.data.objects:
        if obj.animation_data:
            while len(obj.animation_data.nla_tracks) > 0:
                obj.animation_data.nla_tracks.remove(obj.animation_data.nla_tracks[0])
    
    print("✅ Pulizia completata\n")

def setup_player_simple(template_name, new_name):
    """Duplica il template SENZA configurare NLA (lo faremo dopo)"""
    
    if template_name not in bpy.data.objects:
        raise Exception(f"Template '{template_name}' non trovato!")
    
    template_obj = bpy.data.objects[template_name]
    
    bpy.ops.object.select_all(action='DESELECT')
    template_obj.select_set(True)
    
    # Seleziona tutti i figli
    for child in template_obj.children_recursive:
        child.select_set(True)
    
    # Duplica
    bpy.ops.object.duplicate(linked=False)
    new_obj = bpy.context.selected_objects[0]
    new_obj.name = new_name
    
    new_obj.scale = (PLAYER_SCALE, PLAYER_SCALE, PLAYER_SCALE)
    new_obj.rotation_mode = 'XYZ'
    
    # Trova armature
    armature_obj = None
    if new_obj.type == 'ARMATURE':
        armature_obj = new_obj
    else:
        for child in new_obj.children:
            if child.type == 'ARMATURE':
                armature_obj = child
                break
    
    bpy.ops.object.select_all(action='DESELECT')
    
    return new_obj, armature_obj

def remove_root_motion_from_action(action, root_bone_name="Armature"):
    """Rimuove le curve di location del root bone"""
    if not action:
        return False
    
    removed = False
    fcurves_to_remove = []
    
    # 1. Cerca tutte le curve del root bone
    #    Convertiamo in list() per creare una copia statica ed evitare errori
    #    mentre iteriamo e modifichiamo
    for fc in list(action.fcurves): 
        data_path = fc.data_path
        # Controlla se è una curva di location del root
        if f'pose.bones["{root_bone_name}"].location' in data_path:
            fcurves_to_remove.append(fc)
            removed = True
    
    # 2. Rimuovi le curve trovate
    for fc in fcurves_to_remove:
        # --- INIZIO CORREZIONE ---
        # Salva i dati per il log PRIMA di rimuovere!
        data_path_str = fc.data_path
        array_index_str = fc.array_index
        
        # Rimuovi la curva
        action.fcurves.remove(fc)
        
        # Stampa usando i dati salvati
        print(f"   🔒 Rimossa: {data_path_str}[{array_index_str}]")
        # --- FINE CORREZIONE ---
        
    return removed

def calculate_distance(pos1, pos2):
    """Distanza 2D"""
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

try:
    cleanup_previous_animation()

    # Verifica risorse
    if PLAYER_TEMPLATE_NAME not in bpy.data.objects:
        raise Exception(f"ERRORE: Template '{PLAYER_TEMPLATE_NAME}' non trovato!")
    
    if RUN_ANIMATION_NAME not in bpy.data.actions:
        raise Exception(f"ERRORE: Animazione '{RUN_ANIMATION_NAME}' non trovata!")
    
    run_action = bpy.data.actions[RUN_ANIMATION_NAME]
    run_start = int(run_action.frame_range[0])
    run_end = int(run_action.frame_range[1])
    run_length = run_end - run_start
    
    print(f"✅ Template: {PLAYER_TEMPLATE_NAME}")
    print(f"✅ Animazione: {RUN_ANIMATION_NAME} ({run_start}→{run_end}, {run_length}f)")
    
    # Rimuovi root motion
    print(f"\n🔒 Tentativo rimozione root motion (bone: 'Armature')...")
    removed = remove_root_motion_from_action(run_action, "Armature")
    NOME_OSSO_TROVATO = "mixamorig:Hips"
    if not removed:
        print(f"⚠  Nessuna curva trovata. Proviamo altri nomi comuni...")
        for bone_name in [NOME_OSSO_TROVATO, "Root", "root", "Hips", "hips", "Pelvis", "pelvis"]:
            if remove_root_motion_from_action(run_action, bone_name):
                print(f"✅ Root motion rimosso (bone: '{bone_name}')")
                removed = True
                break
    else:
        print(f"✅ Root motion rimosso (bone: 'Armature')")
    
    if not removed:
        print(f"⚠  Root motion non trovato - l'animazione potrebbe già essere sul posto")

    # Carica JSON
    print(f"\n📂 Caricamento {JSON_FILE_PATH}...")
    
    event = None
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                current_event = json.loads(line)
                if 'event_info' in current_event and \
                   isinstance(current_event['event_info'], dict) and \
                   'id' in current_event['event_info']:
                    
                    if str(current_event['event_info']['id']).strip() == str(TARGET_EVENT_ID).strip():
                        event = current_event
                        print(f"✅ Evento {TARGET_EVENT_ID} trovato (riga {i+1})")
                        break
            except:
                pass

    if event is None:
        raise Exception(f"ERRORE: Evento ID '{TARGET_EVENT_ID}' non trovato")

    bpy.context.scene.render.fps = 25

    # Crea giocatori
    print(f"\n👥 Creazione giocatori...")
    player_id_to_object_name_map = {}
    player_armatures = {}
    player_nla_strips = {}

    home_obj_names = [f"player_{i}" for i in range(5)]
    visitor_obj_names = [f"player_{i}" for i in range(5, 10)]

    home_team_id = event['home']['teamid']
    visitor_team_id = event['visitor']['teamid']
    first_moment = event['moments'][0]

    for p_data in first_moment['player_coordinates']:
        player_id_str = str(p_data['playerid']) 
        team_id = p_data['teamid']

        obj_name = None
        if team_id == home_team_id and home_obj_names:
            obj_name = home_obj_names.pop(0)
            team_label = "HOME"
        elif team_id == visitor_team_id and visitor_obj_names:
            obj_name = visitor_obj_names.pop(0)
            team_label = "VISITOR"
        
        if obj_name:
            player_obj, armature_obj = setup_player_simple(PLAYER_TEMPLATE_NAME, obj_name)
            player_id_to_object_name_map[player_id_str] = obj_name
            player_armatures[obj_name] = armature_obj
            player_nla_strips[obj_name] = None

            initial_pos = convert_coords(p_data['x'], p_data['y'], p_data['z'])
            player_obj.location = initial_pos
            
            print(f"   [{team_label}] {player_id_str} → {obj_name} @ ({initial_pos[0]:.1f}, {initial_pos[1]:.1f})")

    print(f"✅ {len(player_id_to_object_name_map)} giocatori creati\n")

    # Nascondi template
    template_obj = bpy.data.objects[PLAYER_TEMPLATE_NAME]
    template_obj.hide_viewport = True
    template_obj.hide_render = True

    # Setup NLA per tutti i giocatori
    print("🎬 Setup NLA tracks...")
    for obj_name, armature_obj in player_armatures.items():
        if armature_obj:
            if not armature_obj.animation_data:
                armature_obj.animation_data_create()
            
            # Rimuovi action diretta
            armature_obj.animation_data.action = None
            
            # Crea NLA track
            track = armature_obj.animation_data.nla_tracks.new()
            track.name = f"{obj_name}_run"
            
            # Crea strip con repeat
            strip = track.strips.new(RUN_ANIMATION_NAME, start=1, action=run_action)
            strip.blend_type = 'REPLACE'
            strip.influence = 1.0
            #strip.use_animated_time = True
            strip.repeat = 500              # <-- AGGIUNGI QUESTA
            strip.use_animated_time_cyclic = True # <-- AGGIUNGI QUESTA
            player_nla_strips[obj_name] = strip
    
    print("✅ NLA configurato")

    # Animazione
    print(f"\n⏱  Creazione keyframes...")
    start_game_clock = event['moments'][0]['game_clock']
    ball_obj = bpy.data.objects["ball"]
    num_moments = len(event['moments'])

    previous_positions = {}
    animation_time = {}  # Tempo accumulato per ogni giocatore
    
    for obj_name in player_armatures.keys():
        animation_time[obj_name] = 0.0

    for i, moment in enumerate(event['moments']):
        current_game_clock = moment['game_clock']
        frame_num = int(round((start_game_clock - current_game_clock) * 25))
        
        if i % 100 == 0: 
            print(f"   Frame {frame_num} ({i}/{num_moments})")

        # Palla
        ball_coords = moment['ball_coordinates']
        ball_pos_2d = (ball_coords['x'], ball_coords['y'])
        ball_obj.location = convert_coords(ball_coords['x'], ball_coords['y'], ball_coords['z'])
        ball_obj.keyframe_insert(data_path="location", frame=frame_num)

        # Giocatori
        for p_data in moment['player_coordinates']:
            player_id_str = str(p_data['playerid']) 
            obj_name = player_id_to_object_name_map.get(player_id_str)

            if obj_name and obj_name in bpy.data.objects:
                player_obj = bpy.data.objects[obj_name]
                armature_obj = player_armatures.get(obj_name)

                nba_x, nba_y, nba_z = p_data['x'], p_data['y'], p_data['z']
                current_pos = (nba_x, nba_y)

                # Posizione
                player_obj.location = convert_coords(nba_x, nba_y, nba_z)
                player_obj.keyframe_insert(data_path="location", frame=frame_num)

                # Rotazione verso palla
                dx = ball_pos_2d[0] - current_pos[0]
                dy = ball_pos_2d[1] - current_pos[1]
                angle_z = math.atan2(dx, dy) + (math.pi / 2)
                player_obj.rotation_euler.z = angle_z
                player_obj.keyframe_insert(data_path="rotation_euler", frame=frame_num)
                
                # Velocità animazione
                # ...dopo "player_obj.keyframe_insert(data_path="rotation_euler", frame=frame_num)"

                # --- TUTTO QUESTO BLOCCO DEVE ESSERE SOSTITUITO ---
                # (Da "Velocità animazione" fino a "bone.keyframe_insert(data_path="location", frame=frame_num)")

                # --- INIZIO NUOVO BLOCCO ---
                
                # Calcolo velocità
                # speed_mult = ANIMATION_SPEED_MULTIPLIER

                # if USE_SPEED_BASED_ANIMATION and obj_name in previous_positions:
                #     distance = calculate_distance(current_pos, previous_positions[obj_name])
                    
                #     if distance < MIN_SPEED_THRESHOLD:
                #         speed_mult = 0.2
                #     else:
                #         speed_mult = (distance / 0.4) * ANIMATION_SPEED_MULTIPLIER
                #         speed_mult = max(0.3, min(speed_mult, 4.0))
                
                # # Avanza tempo animazione
                # # NOTA: Usiamo += speed_mult solo se non è il primo frame (i > 0)
                # if i > 0:
                #     animation_time[obj_name] += speed_mult
                # else:
                #     animation_time[obj_name] = run_start # Inizia dal primo frame dell'azione

                # # Anima la proprietà strip_time!
                # strip = player_nla_strips.get(obj_name)
                # if strip:
                #     # --- INIZIO MODIFICA ---
                #     # Calcoliamo il frame ciclico corretto
                    
                #     # 1. Quanto tempo è passato dall'inizio dell'azione
                #     time_since_start = animation_time[obj_name] - run_start
                    
                #     # 2. Quante volte siamo "dentro" il ciclo (es. 1.5, 2.3)
                #     # Usiamo max(1, run_length) per evitare divisione per zero se run_length = 0
                #     time_in_cycle = time_since_start % max(1, run_length)
                    
                #     # 3. Aggiungi di nuovo l'offset iniziale
                #     current_strip_frame = time_in_cycle + run_start
                    
                #     # Diciamo all'NLA strip a quale frame CICLICO deve essere
                #     strip.strip_time = current_strip_frame
                #     # --- FINE MODIFICA ---
                    
                #     # Inseriamo un keyframe per questa proprietà
                #     strip.keyframe_insert(data_path="strip_time", frame=frame_num)

                previous_positions[obj_name] = current_pos

    # Timeline
    end_game_clock = event['moments'][-1]['game_clock']
    end_frame = int(round((start_game_clock - end_game_clock) * 25))

    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = end_frame

    # Rimuovi NLA (ora abbiamo keyframe diretti)
    print("\n🧹 Rimozione NLA tracks...")
    # for armature_obj in player_armatures.values():
    #     if armature_obj and armature_obj.animation_data:
    #         while len(armature_obj.animation_data.nla_tracks) > 0:
    #             armature_obj.animation_data.nla_tracks.remove(
    #                 armature_obj.animation_data.nla_tracks[0]
    #             )

    print(f"\n✅ COMPLETATO!")
    print(f"   Frames: 0 → {end_frame}")
    print(f"   Giocatori: {len(player_id_to_object_name_map)}")
    print(f"   Velocità base: {ANIMATION_SPEED_MULTIPLIER}x")
    print(f"   Root motion: {'Rimosso' if removed else 'N/D'}")

except Exception as e:
    print(f"\n❌ ERRORE: {e}")
    import traceback
    traceback.print_exc()

print("\n--- FINE SCRIPT ---")