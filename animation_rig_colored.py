import bpy
import os
import json
import math

# --- IMPOSTAZIONI DA PERSONALIZZARE ---
JSON_FILE_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\nba_tracking_data_tiny.json" 
TARGET_EVENT_ID = "273"
PLAYER_TEMPLATE_NAME = "player_rigged_template"
PLAYER_SCALE = 0.037 

# --- IMPOSTAZIONI STATE MACHINE ---
ANIMATION_NAMES = {
    "idle": "idle",
    "walk": "walk",
    "run": "run",
    "dribble": "dribble"
}

# Soglie
IDLE_THRESHOLD = 0.3        # (piedi/frame) Sotto questa velocità, il giocatore è "idle"
WALK_THRESHOLD = 1.0        # (piedi/frame) Sotto questa velocità, il giocatore è "walk"
                            # Sopra, è "run"
POSSESSION_THRESHOLD = 4.5  # (piedi) Distanza 3D massima per essere considerati in "possesso"
BALL_HEIGHT_THRESHOLD = 6.0 # (piedi) Altezza massima della palla per essere in "possesso" (evita tiri/passaggi)

# NLA Blending
BLEND_FRAMES = 5.0          # Numero di frame per sfumare tra le animazioni

# --- NOMI MATERIALI (DALLO SCRIPT DEL COMPAGNO) ---
TEAM_A_MAT_NAME = "Team_A_Material"
TEAM_B_MAT_NAME = "Team_B_Material"

# --- FINE IMPOSTAZIONI ---


# =========================================================================
# 🎨 CREAZIONE MATERIALI SQUADRA (Rosso e Blu)
# (Logica unita dallo script del compagno)
# =========================================================================
try:
    # Colore Squadra A (Rosso)
    if TEAM_A_MAT_NAME not in bpy.data.materials:
        team_a_mat = bpy.data.materials.new(name=TEAM_A_MAT_NAME)
        team_a_mat.use_nodes = True
        team_a_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.0, 0.0, 1.0) # Rosso
        print(f"Creato materiale Team A (Rosso): {TEAM_A_MAT_NAME}")
    else:
        print(f"Materiale Team A (Rosso) '{TEAM_A_MAT_NAME}' già esistente.")

    # Colore Squadra B (Blu)
    if TEAM_B_MAT_NAME not in bpy.data.materials:
        team_b_mat = bpy.data.materials.new(name=TEAM_B_MAT_NAME)
        team_b_mat.use_nodes = True
        team_b_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.0, 0.0, 0.8, 1.0) # Blu
        print(f"Creato materiale Team B (Blu): {TEAM_B_MAT_NAME}")
    else:
        print(f"Materiale Team B (Blu) '{TEAM_B_MAT_NAME}' già esistente.")
except Exception as e:
    print(f"Errore creazione materiali: {e}")
# =========================================================================


print("\n--- Inizio FASE 3: Animazione NBA (State Machine + Colori) ---")

def convert_coords(nba_x, nba_y, nba_z):
    blender_x = nba_y
    blender_y = nba_x
    blender_z = nba_z
    return (blender_x, blender_y, blender_z)

def calculate_distance(pos1, pos2):
    """Distanza 2D (per velocità)"""
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def calculate_distance_3d(pos1, pos2):
    """Distanza 3D (per possesso)"""
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

def cleanup_previous_animation():
    """Pulizia COMPLETA di tutto"""
    print("\n🧹 Pulizia completa scena...")
    
    # Rimuovi tutti i player duplicati
    obj_names_to_remove = [f"player_{i}" for i in range(20)]
    for obj_name in obj_names_to_remove:
        if obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            for child in list(obj.children):
                bpy.data.objects.remove(child, do_unlink=True)
            bpy.data.objects.remove(obj, do_unlink=True)
            # print(f"   Rimosso: {obj_name}") # Opzionale, per un log più pulito
    
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

# =========================================================================
# MODIFICATA: Aggiunto 'team_mat_name' e logica di assegnazione materiale
# =========================================================================
def setup_player_simple(template_name, new_name, team_mat_name):
    """Duplica il template E ASSEGNA IL MATERIALE"""
    
    if template_name not in bpy.data.objects:
        raise Exception(f"Template '{template_name}' non trovato!")
    
    template_obj = bpy.data.objects[template_name]
    
    bpy.ops.object.select_all(action='DESELECT')
    template_obj.select_set(True)
    
    for child in template_obj.children_recursive:
        child.select_set(True)
    
    bpy.ops.object.duplicate(linked=False)
    new_obj = bpy.context.selected_objects[0]
    new_obj.name = new_name
    
    new_obj.scale = (PLAYER_SCALE, PLAYER_SCALE, PLAYER_SCALE)
    new_obj.rotation_mode = 'XYZ'
    
    # --- LOGICA UNITA (Armatura + Materiale) ---
    armature_obj = None
    applied_to_surface = False
    
    mat = bpy.data.materials.get(team_mat_name)
    if not mat:
        print(f"     ⚠ Materiale '{team_mat_name}' non trovato per l'assegnazione.")

    # Itera sull'oggetto duplicato e tutti i suoi figli
    for obj in [new_obj] + list(new_obj.children_recursive):
        # 1. Trova l'armatura
        if obj.type == 'ARMATURE' and not armature_obj:
            armature_obj = obj

        # 2. Applica il materiale alla MESH visibile
        if obj.type == 'MESH' and mat:
            # Assumiamo che la mesh principale sia 'surface' o 'body'
            if "surface" in obj.name.lower() or "body" in obj.name.lower():
                obj.data.materials.clear()
                obj.data.materials.append(mat)
                print(f"     ✅ Assegnato: {team_mat_name} a {obj.name}")
                applied_to_surface = True
            elif "joint" in obj.name.lower():
                 obj.data.materials.clear() # Pulisce i joints

    if not applied_to_surface:
        print(f"     ⚠ Nessuna mesh 'surface' o 'body' trovata per il colore su {new_name}.")
    # --- FINE LOGICA UNITA ---

    bpy.ops.object.select_all(action='DESELECT')
    
    return new_obj, armature_obj

def remove_root_motion_from_action(action, root_bone_name="Armature"):
    """Rimuove le curve di location del root bone"""
    if not action:
        return False
    
    removed = False
    fcurves_to_remove = []
    
    for fc in list(action.fcurves): 
        data_path = fc.data_path
        if f'pose.bones["{root_bone_name}"].location' in data_path:
            fcurves_to_remove.append(fc)
            removed = True
    
    for fc in fcurves_to_remove:
        data_path_str = fc.data_path
        array_index_str = fc.array_index
        action.fcurves.remove(fc)
        print(f"   🔒 Rimossa: {data_path_str}[{array_index_str}]")
        
    return removed

try:
    cleanup_previous_animation()

    # --- 1. VERIFICA E PULIZIA ANIMAZIONI ---
    print("\n✅ Verifica e pulizia animazioni...")
    if PLAYER_TEMPLATE_NAME not in bpy.data.objects:
        raise Exception(f"ERRORE: Template '{PLAYER_TEMPLATE_NAME}' non trovato!")
    
    print(f"✅ Template: {PLAYER_TEMPLATE_NAME}")

    actions = {}
    NOME_OSSO_TROVATO = "mixamorig:Hips"
    
    for state, anim_name in ANIMATION_NAMES.items():
        if anim_name not in bpy.data.actions:
            raise Exception(f"ERRORE: Animazione '{anim_name}' (per stato '{state}') non trovata!")
        
        action = bpy.data.actions[anim_name]
        actions[state] = action
        print(f"✅ Animazione '{state}' caricata: {anim_name} ({int(action.frame_range[0])}→{int(action.frame_range[1])}f)")
        
        # Rimuovi root motion (tranne che per 'idle')
        if state != "idle":
            print(f"   🔒 Tentativo rimozione root motion per '{anim_name}'...")
            removed = False
            for bone_name in [NOME_OSSO_TROVATO, "Root", "root", "Hips", "hips", "Pelvis", "pelvis"]:
                if remove_root_motion_from_action(action, bone_name):
                    print(f"   ✅ Root motion rimosso (bone: '{bone_name}')")
                    removed = True
                    break
            if not removed:
                print(f"   ⚠  Root motion non trovato - l'animazione '{anim_name}' potrebbe già essere sul posto.")

    # --- 2. CARICA JSON ---
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

    # --- 3. CREA GIOCATORI ---
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
        team_mat = None # <<< VARIABILE PER IL MATERIALE
        
        if team_id == home_team_id and home_obj_names:
            obj_name = home_obj_names.pop(0)
            team_label = "HOME"
            team_mat = TEAM_A_MAT_NAME # <<< ASSEGNA MATERIALE A (Rosso)
        elif team_id == visitor_team_id and visitor_obj_names:
            obj_name = visitor_obj_names.pop(0)
            team_label = "VISITOR"
            team_mat = TEAM_B_MAT_NAME # <<< ASSEGNA MATERIALE B (Blu)
        
        if obj_name:
            # Passa il nome del materiale alla funzione di setup
            player_obj, armature_obj = setup_player_simple(PLAYER_TEMPLATE_NAME, obj_name, team_mat)
            
            player_id_to_object_name_map[player_id_str] = obj_name
            player_armatures[obj_name] = armature_obj
            player_nla_strips[obj_name] = {} 

            initial_pos = convert_coords(p_data['x'], p_data['y'], p_data['z'])
            player_obj.location = initial_pos
            
            print(f"   [{team_label}] {player_id_str} → {obj_name} @ ({initial_pos[0]:.1f}, {initial_pos[1]:.1f})")

    print(f"✅ {len(player_id_to_object_name_map)} giocatori creati\n")

    template_obj = bpy.data.objects[PLAYER_TEMPLATE_NAME]
    template_obj.hide_viewport = True
    template_obj.hide_render = True

    # --- 4. SETUP NLA STATE MACHINE ---
    print("🎬 Setup NLA tracks (State Machine)...")
    for obj_name, armature_obj in player_armatures.items():
        if armature_obj:
            if not armature_obj.animation_data:
                armature_obj.animation_data_create()
            
            armature_obj.animation_data.action = None
            
            for state, action in actions.items():
                track = armature_obj.animation_data.nla_tracks.new()
                track.name = f"{obj_name}_{state}"
                
                strip = track.strips.new(action.name, start=1, action=action)
                strip.blend_type = 'REPLACE'
                
                # --- CORREZIONE T-POSE ---
                # TUTTE le animazioni (incluso 'idle') devono ciclare,
                # altrimenti lo strip 'idle' finisce e causa una T-Pose.
                strip.repeat = 500
                strip.use_animated_time_cyclic = True
                # --- FINE CORREZIONE T-POSE ---
                
                # Impostazioni di Blending
                strip.blend_in = BLEND_FRAMES
                strip.blend_out = BLEND_FRAMES
                strip.use_auto_blend = True
                
                # Abilita l'animazione della 'influence'
                strip.use_animated_influence = True
                
                # Stato iniziale:
                if state == "idle":
                    strip.influence = 1.0
                else:
                    strip.influence = 0.0
                    
                player_nla_strips[obj_name][state] = strip
    
    print("✅ NLA State Machine configurata")


    # --- 5. ANIMAZIONE ---
    print(f"\n⏱  Creazione keyframes...")
    start_game_clock = event['moments'][0]['game_clock']
    ball_obj = bpy.data.objects["ball"]
    num_moments = len(event['moments'])

    previous_positions = {}
    player_locations_3d = {} 
    
    for i, moment in enumerate(event['moments']):
        current_game_clock = moment['game_clock']
        frame_num = int(round((start_game_clock - current_game_clock) * 25))
        
        if i % 100 == 0: 
            print(f"   Frame {frame_num} ({i}/{num_moments})")

        # Palla
        ball_coords = moment['ball_coordinates']
        ball_pos_2d = (ball_coords['x'], ball_coords['y'])
        ball_pos_3d_blender = convert_coords(ball_coords['x'], ball_coords['y'], ball_coords['z'])
        ball_obj.location = ball_pos_3d_blender
        ball_obj.keyframe_insert(data_path="location", frame=frame_num)

        # --- 1. TROVA POSSESSORE ---
        possessor_obj_name = None
        min_dist_to_ball = float('inf')
        
        temp_player_locations = {}
        for p_data in moment['player_coordinates']:
            player_id_str = str(p_data['playerid'])
            obj_name = player_id_to_object_name_map.get(player_id_str)
            if obj_name:
                loc_3d = convert_coords(p_data['x'], p_data['y'], p_data['z'])
                temp_player_locations[obj_name] = loc_3d
                player_locations_3d[obj_name] = loc_3d 

        for obj_name, loc_3d in temp_player_locations.items():
            dist = calculate_distance_3d(loc_3d, ball_pos_3d_blender)
            if dist < min_dist_to_ball:
                min_dist_to_ball = dist
                possessor_obj_name = obj_name
        
        if min_dist_to_ball > POSSESSION_THRESHOLD or ball_coords['z'] > BALL_HEIGHT_THRESHOLD:
            possessor_obj_name = None
            
        # --- 2. ANIMA GIOCATORI ---
        for p_data in moment['player_coordinates']:
            player_id_str = str(p_data['playerid']) 
            obj_name = player_id_to_object_name_map.get(player_id_str)

            if obj_name and obj_name in bpy.data.objects:
                player_obj = bpy.data.objects[obj_name]
                
                nba_x, nba_y, nba_z = p_data['x'], p_data['y'], p_data['z']
                current_pos_2d = (nba_x, nba_y)

                player_obj.location = player_locations_3d[obj_name]
                player_obj.keyframe_insert(data_path="location", frame=frame_num)

                # Rotazione verso palla
                dx = ball_pos_2d[0] - current_pos_2d[0]
                dy = ball_pos_2d[1] - current_pos_2d[1]
                angle_z = math.atan2(dx, dy) + (math.pi / 2)
                player_obj.rotation_euler.z = angle_z
                player_obj.keyframe_insert(data_path="rotation_euler", frame=frame_num)
                
                # --- LOGICA STATE MACHINE (PIÙ ROBUSTA) ---
                
                distance = 0.0
                if obj_name in previous_positions:
                    distance = calculate_distance(current_pos_2d, previous_positions[obj_name])
                
                (idle_inf, walk_inf, run_inf, dribble_inf) = (0.0, 0.0, 0.0, 0.0)
                
                # 1. Determina stato di movimento
                if distance < IDLE_THRESHOLD:
                    idle_inf = 1.0
                elif distance < WALK_THRESHOLD:
                    walk_inf = 1.0
                else:
                    run_inf = 1.0
                
                # 2. Sovrascrivi se è in possesso
                if obj_name == possessor_obj_name:
                    dribble_inf = 1.0 
                    idle_inf = 0.0
                    walk_inf = 0.0
                    run_inf = 0.0
                
                # Applica keyframes
                strips = player_nla_strips[obj_name]
                
                strips["idle"].influence = idle_inf
                strips["idle"].keyframe_insert(data_path="influence", frame=frame_num)
                
                strips["walk"].influence = walk_inf
                strips["walk"].keyframe_insert(data_path="influence", frame=frame_num)
                
                strips["run"].influence = run_inf
                strips["run"].keyframe_insert(data_path="influence", frame=frame_num)
                
                strips["dribble"].influence = dribble_inf
                strips["dribble"].keyframe_insert(data_path="influence", frame=frame_num)
                
                # --- FINE STATE MACHINE LOGIC ---
                
                previous_positions[obj_name] = current_pos_2d 

    # Timeline
    end_game_clock = event['moments'][-1]['game_clock']
    end_frame = int(round((start_game_clock - end_game_clock) * 25))

    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = end_frame

    print("\n✅ NLA tracks mantenute per l'animazione.")
    
    print(f"\n✅ COMPLETATO!")
    print(f"   Frames: 0 → {end_frame}")
    print(f"   Giocatori: {len(player_id_to_object_name_map)}")
    print(f"   State Machine: Attiva")

except Exception as e:
    print(f"\n❌ ERRORE: {e}")
    import traceback
    traceback.print_exc()

print("\n--- FINE SCRIPT ---")