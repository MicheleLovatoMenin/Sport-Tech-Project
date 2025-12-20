import bpy
import json
import math
import os
from itertools import groupby

# ==================== CONFIGURAZIONE ====================

# Percorsi (Assicurati che siano corretti)
BASE_PATH = r"C:\Users\DISI\Documents\SportTech Students\Basket_Virtualisation\Sport-Tech-Project"
DATASET_JSON = os.path.join(BASE_PATH, "nba_tracking_data_tiny.json")
METADATA_JSON = os.path.join(BASE_PATH, "shot_metadata.json")

# Oggetti Blender
ARMATURE_NAME = "Armature"
BALL_NAME = "ball"

# Sincronizzazione Temporale
FPS_JSON = 25
FPS_ANIMATION = 120
FRAME_MULTIPLIER = FPS_ANIMATION / FPS_JSON 



# Dimensioni campo NBA (in piedi)
COURT_LENGTH = 94.0
COURT_WIDTH = 50.0

# Coordinate canestri (assumi centro campo a 0,0)
BASKET_1 = (COURT_WIDTH / 2, COURT_LENGTH)  # Canestro a Y = 47
BASKET_2 = (COURT_WIDTH / 2, 0)  # Canestro a Y = -47

# === PARAMETRI CRITICI PER IL SYNC ===
# === PARAMETRI CRITICI PER IL SYNC (SPECIFICI PER LATO) ===
# Struttura: "nome_animazione": {"crop": Inizio, "release": Rilascio, "end": Fine}
SHOT_CONFIGS = {
    "jumpshot_dx": {"crop": 50, "release": 144, "end": 340},
    "jumpshot_sx": {"crop": 50, "release": 150, "end": 363}
}
# Fallback di sicurezza (se il nome non combacia)
DEFAULT_SHOT_CONFIG = {"crop": 50, "release": 150, "end": 300}

# === CONFIGURAZIONE VELOCITÀ ANIMAZIONI (Anti-Sliding) ===
# Valori in Piedi/Secondo (ft/s) ottenuti da calibrazione
SPEED_MAP = {
    # Movimento Base
    "walk": 5.5362,
    "slow_run": 7.6720,
    "fast_run": 9.0487,
    "back_run": 5.9016,  # Valore precedente mantenuto
    
    # Dribbling Movimento
    "dribble_walk_dx": 6.2386,
    "dribble_walk_sx": 6.1800,
    "dribble_run_dx": 9.5703,
    "dribble_run_sx": 9.0724,
    
    # Catch in movimento
    "run_catch_dx": 2.6300,
    "run_catch_sx": 3.4021,
    
    # Extra
    "celly_lebron": 3.8624
}

# ... (dopo SPEED_MAP)

# === CONFIGURAZIONE COLORI SQUADRE ===
TEAM_MAPPING = {
    1610612737: {'name': 'ATL', 'color': '#E13A3E', 'color2': '#C8102E'},
    1610612738: {'name': 'BOS', 'color': '#008348', 'color2': '#BB9753'},
    1610612751: {'name': 'BKN', 'color': '#061922', 'color2': '#FFFFFF'},
    1610612766: {'name': 'CHA', 'color': '#007885', 'color2': '#FFFFFF'},
    1610612741: {'name': 'CHI', 'color': '#CE1141', 'color2': '#000000'},
    1610612739: {'name': 'CLE', 'color': '#860038', 'color2': '#FDBB30'},
    1610612742: {'name': 'DAL', 'color': '#007DC5', 'color2': '#00538C'},
    1610612743: {'name': 'DEN', 'color': "#0C3256", 'color2': '#FDB927'},
    1610612765: {'name': 'DET', 'color': '#006BB6', 'color2': '#ED174C'},
    1610612744: {'name': 'GSW', 'color': '#006BB6', 'color2': '#FDB927'},
    1610612745: {'name': 'HOU', 'color': '#CE1141', 'color2': '#000000'},
    1610612754: {'name': 'IND', 'color': '#FDBB30', 'color2': '#00275D'},
    1610612746: {'name': 'LAC', 'color': '#ED174C', 'color2': '#006BB6'},
    1610612747: {'name': 'LAL', 'color': '#552582', 'color2': '#FDB927'},
    1610612763: {'name': 'MEM', 'color': '#0F586C', 'color2': "#11C0DF"},
    1610612748: {'name': 'MIA', 'color': '#98002E', 'color2': '#ffffff'},
    1610612749: {'name': 'MIL', 'color': '#00471B', 'color2': '#EEE1C6'},
    1610612750: {'name': 'MIN', 'color': '#005083', 'color2': '#FFFFFF'},
    1610612740: {'name': 'NOP', 'color': '#002B5C', 'color2': '#B4975A'},
    1610612752: {'name': 'NYK', 'color': '#F58426', 'color2': '#006BB6'},
    1610612760: {'name': 'OKC', 'color': '#007DC3', 'color2': '#F05133'},
    1610612753: {'name': 'ORL', 'color': '#007DC5', 'color2': '#000000'},
    1610612755: {'name': 'PHI', 'color': '#006BB6', 'color2': '#ED174C'},
    1610612756: {'name': 'PHX', 'color': '#1D1160', 'color2': '#E56020'},
    1610612757: {'name': 'POR', 'color': '#E03A3E', 'color2': '#000000'},
    1610612758: {'name': 'SAC', 'color': '#724C9F', 'color2': '#63727A'},
    1610612759: {'name': 'SAS', 'color': '#BAC3C9', 'color2': '#000000'},
    1610612761: {'name': 'TOR', 'color': '#CE1141', 'color2': '#000000'},
    1610612762: {'name': 'UTA', 'color': '#1D1160', 'color2': '#F9A01B'},
    1610612764: {'name': 'WAS', 'color': '#002B5C', 'color2': '#E31837'},
}

# =====================================

# Soglie
POSSESSION_DISTANCE = 2.5     # piedi (aumentato leggermente per sicurezza)
WALK_SPEED_THRESHOLD = 2.0    # piedi/frame (ALZATO: 0.3 era troppo sensibile al rumore)
RUN_SPEED_THRESHOLD = 4.0     # piedi/frame

# Animazioni
# NOTA: Assicurati che l'azione "idle" esista in Blender (creata con lo script precedente)
# === MAPPING ANIMAZIONI ===
ANIM_MAP = {
    # NO PALLA (MOVIMENTO)
    "idle": "idle",
    "walk": "walk",
    "slow_run": "slow_run",
    "fast_run": "fast_run",
    "back_run": "back_run",
    
    # HOLDING (Palla ferma in mano)
    "holding": "idle_ball",  # Assicurati di avere questa azione o usa un placeholder
    
    # CATCH
    "static_catch_dx": "static_catch_dx", "static_catch_sx": "static_catch_sx",
    "run_catch_dx": "run_catch_dx", "run_catch_sx": "run_catch_sx",
    
    # DRIBBLE MOVIMENTO
    "dribble_walk_dx": "dribble_walk_dx", "dribble_walk_sx": "dribble_walk_sx",
    "dribble_run_dx": "dribble_run_dx", "dribble_run_sx": "dribble_run_sx",
    
    # DRIBBLE STATICO
    "dribble_static_dx": "stationary_dribble_dx",
    "dribble_static_sx": "stationary_shot_dribble_sx",
    
    # TIRO
    "jumpshot_dx": "jumpshot_dx", "jumpshot_sx": "jumpshot_sx",
    
    # EXTRAS
    "celly_lebron": "celly_lebron"
}

# ==================== HELPER FUNCTIONS ====================

def convert_coords(nba_x, nba_y, nba_z):
    return (nba_y, nba_x, nba_z)

def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def calculate_distance_3d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

def load_metadata():
    print(f"📂 Caricamento metadata...")
    with open(METADATA_JSON, 'r') as f:
        return json.load(f)

def find_event_in_dataset(game_id, id):
    print(f"🔍 Ricerca evento {id}...")
    with open(DATASET_JSON, 'r', encoding='utf-8') as f:
        try:
            for line in f:
                data = json.loads(line)
                if str(data.get('gameid')) == str(game_id) and str(data['event_info']['id']) == str(id):
                    return data

        except:
            f.seek(0)
            for line in f: # Fallback riga per riga
                try:
                    data = json.loads(line.strip().rstrip(','))
                    if str(data.get('gameid')) == str(game_id) and str(data.get('event_info', {}).get('id')) == str(id):
                        return data
                except: continue
    raise Exception("Evento non trovato")

def extract_shot_window(event, shot_frame):
    moments = event['moments']

    FPS_DATA = 25
    frames_before = 3 * FPS_DATA  # 75 frame
    frames_after = 2 * FPS_DATA   # 50 frame
    # Protezione contro shot_frame fuori range
    if shot_frame >= len(moments): 
        print(f"⚠️ Shot frame {shot_frame} oltre la lunghezza dati. Reset a metà.")
        shot_frame = len(moments) // 2
        
    # Estraiamo una finestra ampia per sicurezza
    start_idx = max(0, shot_frame - frames_before)
    end_idx = min(len(moments), shot_frame + 50)
    new_shot_frame = shot_frame - start_idx
    
    return moments[start_idx:end_idx], new_shot_frame

def get_trajectories(moments, player_id):
    p_traj, b_traj = [], []
    for m in moments:
        b = m['ball_coordinates']
        b_traj.append((b['x'], b['y'], b['z']))
        found = False
        for p in m['player_coordinates']:
            if str(p['playerid']) == str(player_id):
                p_traj.append((p['x'], p['y'], p['z']))
                found = True
                break
        if not found: # Se il giocatore manca in un frame, usa l'ultimo noto
            if p_traj: p_traj.append(p_traj[-1])
            else: p_traj.append((0,0,0))
    return p_traj, b_traj

def analyze_possession(player_traj, ball_traj):
    """Determina in quali frame il giocatore ha la palla in mano"""
    possession_frames = []
    for i, (p, b) in enumerate(zip(player_traj, ball_traj)):
        dist = calculate_distance_2d(p[:2], b[:2])
        if dist < POSSESSION_DISTANCE:
            possession_frames.append(i)
            
    if possession_frames:
        return possession_frames[0], possession_frames[-1], possession_frames
    return None, None, []

def calculate_speeds(traj):
    speeds = [0.0]
    for i in range(1, len(traj)):
        speeds.append(calculate_distance_2d(traj[i-1], traj[i]))
    return speeds

def determine_basket_target(player_pos):
    p_y = player_pos[1]
    dist_1 = abs(p_y - BASKET_1[1])
    dist_2 = abs(p_y - BASKET_2[1])
    return BASKET_1 if dist_1 < dist_2 else BASKET_2

def get_relative_side(player_pos, ball_pos, target_pos):
    look_dir = (target_pos[0] - player_pos[0], target_pos[1] - player_pos[1])
    ball_dir = (ball_pos[0] - player_pos[0], ball_pos[1] - player_pos[1])
    cross_product = (look_dir[0] * ball_dir[1]) - (look_dir[1] * ball_dir[0])
    return "sx" if cross_product > 0 else "dx"

def is_ball_bouncing(ball_traj, current_frame, window=10, threshold=1):
    start = max(0, current_frame - window)
    end = min(len(ball_traj), current_frame + 1)
    z_values = [b[2] for b in ball_traj[start:end]]
    if not z_values: return False
    return (max(z_values) - min(z_values)) > threshold

def is_moving_backwards(player_pos, prev_player_pos, target_pos):
    look_dx = target_pos[0] - player_pos[0]
    look_dy = target_pos[1] - player_pos[1]
    move_dx = player_pos[0] - prev_player_pos[0]
    move_dy = player_pos[1] - prev_player_pos[1]
    dot_product = (look_dx * move_dx) + (look_dy * move_dy)
    return dot_product < -0.5

def hex_to_rgba(hex_str):
    """Converte stringa HEX (#RRGGBB) in tupla Blender (R, G, B, 1.0)"""
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16)/255.0 for i in (0, 2, 4)) + (1.0,)

def apply_team_colors(team_id):
    """Colora Surface e Joints in base al Team ID"""
    print(f"🎨 Applicazione colori per Team ID: {team_id}")
    
    # 1. Recupera Dati Team (conversione float -> int sicura)
    try:
        t_id = int(float(team_id))
    except:
        print(f"⚠️ ID Team non valido: {team_id}")
        return

    team_data = TEAM_MAPPING.get(t_id)
    if not team_data:
        print(f"⚠️ Team ID {t_id} non trovato nel mapping. Uso colori default.")
        return

    print(f"   Squadra trovata: {team_data['name']}")

    # 2. Definisci Target e Colori
    # Surface -> color (primary)
    # Joints -> color2 (secondary)
    targets = [
        ("Beta_Surface", team_data['color']),
        ("Beta_Joints", team_data['color2'])
    ]

    # 3. Applica Materiali
    for obj_name, hex_color in targets:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            # Crea o recupera materiale
            if not obj.data.materials:
                mat = bpy.data.materials.new(name=f"Mat_{team_data['name']}_{obj_name}")
                obj.data.materials.append(mat)
            else:
                mat = obj.data.materials[0]
                mat.name = f"Mat_{team_data['name']}_{obj_name}" # Rinomina per ordine

            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            bsdf = nodes.get("Principled BSDF")
            
            if bsdf:
                rgba = hex_to_rgba(hex_color)
                bsdf.inputs['Base Color'].default_value = rgba
                print(f"   ✅ {obj_name} -> {hex_color}")
            else:
                print(f"   ❌ Principled BSDF mancante su {obj_name}")
        else:
            print(f"   ❌ Oggetto non trovato: {obj_name}")

# ==================== CORE LOGIC ====================

def determine_state_sequence(p_traj, b_traj, speeds, shot_offset, shot_blender_start, shot_blender_end):
    print("🧠 Calcolo stati (Logica v4 - Full Movement)...")
    print(f"   📍 Shot window: {shot_blender_start} → {shot_blender_end}")  # ← AGGIUNGI
    print(f"   📍 Total frames: {len(p_traj)}, moltiplicati: {int(len(p_traj) * FRAME_MULTIPLIER)}")  # ← AGGIUNGI
    first_poss, _, _ = analyze_possession(p_traj, b_traj)
    states = []

    for i in range(len(p_traj)):
        current_blender_frame = int(i * FRAME_MULTIPLIER)

        # === PROTEZIONE TIRO (FORCE OVERRIDE) ===
        # Se siamo nella finestra temporale del tiro, forziamo lo stato "SHOT"
        # Ignoriamo qualsiasi calcolo di velocità o possesso.
        if shot_blender_start <= current_blender_frame <= shot_blender_end:
            states.append("SHOT")
            continue

        player_pos = p_traj[i]
        prev_pos = p_traj[max(0, i-1)]
        ball_pos = b_traj[i]
        speed = speeds[i]
        dist_ball = calculate_distance_2d(player_pos[:2], ball_pos[:2])
        has_ball = dist_ball < POSSESSION_DISTANCE

        if first_poss is None or i < first_poss:
            look_target = b_traj[i] 
        else:
            look_target = determine_basket_target(player_pos)

        # 1. DOPO IL TIRO 
        if current_blender_frame > shot_blender_end:
            if speed > 0.2 and is_moving_backwards(player_pos, prev_pos, look_target):
                states.append("back_run")
            elif speed > 5.5: states.append("fast_run")
            elif speed > 3.0: states.append("slow_run")
            elif speed > 0.2: states.append("walk")
            else: states.append("idle")
            continue

        # 2. SENZA PALLA
        if not has_ball:
            if speed > 0.2 and is_moving_backwards(player_pos, prev_pos, look_target):
                states.append("back_run")
            elif speed > 5.5: states.append("fast_run")
            elif speed > 3.0: states.append("slow_run")
            elif speed > 0.2: states.append("walk")
            else: states.append("idle")
            continue
            
        # 3. CON PALLA
        side = get_relative_side(player_pos, ball_pos, look_target)
        past_idx = max(0, i-5)
        past_dist = calculate_distance_2d(p_traj[past_idx][:2], b_traj[past_idx][:2])
        is_catch_phase = (past_dist >= POSSESSION_DISTANCE and has_ball)
        
        if is_catch_phase and i > 5:
            if speed > RUN_SPEED_THRESHOLD: states.append(f"run_catch_{side}")
            else: states.append(f"static_catch_{side}")
            continue

        if speed > RUN_SPEED_THRESHOLD: states.append(f"dribble_run_{side}")
        elif speed > WALK_SPEED_THRESHOLD: states.append(f"dribble_walk_{side}")
        else:
            if is_ball_bouncing(b_traj, i): states.append(f"dribble_static_{side}") 
            else: states.append("holding") 
    
    # DEBUG: Verifica stati
    print(f"📊 Distribuzione stati:")
    from collections import Counter
    counter = Counter(states)
    for state, count in counter.most_common():
        print(f"  {state}: {count} frames")

    return states



def create_sequential_strips(armature, state_sequence, shot_anim_name, p_traj):
    print("🎬 Creazione Timeline Sequenziale (Anti-Sliding Universale v2)...")
    
    # 1. Setup Animazione
    if not armature.animation_data:
        armature.animation_data_create()
    
    # Pulizia TRACCE
    while armature.animation_data.nla_tracks:
        armature.animation_data.nla_tracks.remove(armature.animation_data.nla_tracks[0])
        
    # Pulizia AZIONE ATTIVA
    armature.animation_data.action = None

    main_track = armature.animation_data.nla_tracks.new()
    main_track.name = "Main_Animation_Track"
    
    current_blender_frame = 0
    nba_frame_index = 0
    FRAME_GAP = 10

    grouped_states = groupby(state_sequence)
    
    for state, group in grouped_states:
        # Calcoliamo quanti frame NBA dura questo blocco
        nba_frames_in_group = len(list(group))

        # Calcoliamo durata in Blender (Tempo target sulla timeline)
        duration_frames = int(nba_frames_in_group * FRAME_MULTIPLIER)
        
        if duration_frames <= 0: 
            nba_frame_index += nba_frames_in_group
            continue

        # --- LOGICA DI SCALING UNIVERSALE ---
        scale_factor = 1.0
        
        # Se lo stato ha una velocità di riferimento, calcoliamo l'anti-sliding
        if state in SPEED_MAP:
            reference_speed = SPEED_MAP[state]
            
            # 1. Calcola distanza reale percorsa in questo segmento (Piedi)
            start_idx = nba_frame_index
            end_idx = min(nba_frame_index + nba_frames_in_group, len(p_traj) - 1)
            
            segment_distance = 0.0
            for k in range(start_idx, end_idx):
                p1 = p_traj[k]
                p2 = p_traj[k+1]
                # Distanza 2D (X,Y) per ignorare salti verticali
                dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                segment_distance += dist
            
            # 2. Calcola tempo reale in secondi (NBA @ 25 fps)
            duration_seconds = nba_frames_in_group / FPS_JSON
            
            # 3. Calcola Velocità Target (Piedi/Secondo richiesti dal tracking)
            target_speed = 0.0
            if duration_seconds > 0:
                target_speed = segment_distance / duration_seconds
            
            # 4. Calcola Scale NLA (Ref / Target)
            # Se devo andare a 10 ft/s ma l'anim va a 5 ft/s -> Scale 0.5 (Velocizzo l'animazione)
            if target_speed > 0.1: # Soglia minima per evitare divisioni assurde se è quasi fermo
                raw_scale = reference_speed / target_speed
                
                # CLAMPING DI SICUREZZA (0.5x - 2.0x)
                # Evita che l'animazione diventi ridicolmente veloce o lenta per errori nei dati
                scale_factor = max(0.5, min(2.0, raw_scale))
                
                # Debug info per capire cosa succede
                # print(f" ⚙️ {state} | Dist: {segment_distance:.1f}ft | Speed: {target_speed:.1f} f/s | Ref: {reference_speed} | Scale: {scale_factor:.3f}")
            else:
                scale_factor = 1.0 # Se la velocità target è quasi 0, non scalare (evita freeze)

        # --- SELEZIONE AZIONE ---
        action_name = ""
        if state == "SHOT":
            action_name = shot_anim_name
        elif state in ANIM_MAP:
            action_name = ANIM_MAP[state]
        else:
            action_name = ANIM_MAP.get("idle", "idle")
            
        if action_name not in bpy.data.actions:
            print(f"❌ Azione mancante: {action_name}")
            current_blender_frame += duration_frames
            nba_frame_index += nba_frames_in_group
            continue
            
        action = bpy.data.actions[action_name]

        # Lunghezza frame originale dell'azione
        source_duration = max(0.1, action.frame_range[1] - action.frame_range[0])
        
        # --- CREAZIONE STRIP ---
        try:
            strip = main_track.strips.new(
                name=state,
                start=int(current_blender_frame),
                action=action
            )

            # Applica lo scale calcolato
            strip.scale = scale_factor
            
            if state == "SHOT":
                s_conf = SHOT_CONFIGS.get(shot_anim_name, DEFAULT_SHOT_CONFIG)
                strip.action_frame_start = s_conf["crop"]
                strip.action_frame_end = s_conf["end"]
                strip.scale = 1.0 # Override: Il tiro NON si scala dinamicamente
            else:
                strip.action_frame_start = action.frame_range[0]
                strip.action_frame_end = action.frame_range[1]
                
                # Calcola quante ripetizioni servono per coprire la durata temporale
                # Formula: (Durata Blender / Scale Factor) / Durata Originale Azione
                needed_action_frames = duration_frames / scale_factor
                strip.repeat = needed_action_frames / source_duration

            # Imposta la fine corretta sulla timeline
            strip.frame_end = int(current_blender_frame + duration_frames - FRAME_GAP)

            # Settings Blender
            strip.blend_type = 'REPLACE'
            strip.extrapolation = 'HOLD'
            strip.use_auto_blend = False
            
            current_blender_frame = int(current_blender_frame + duration_frames)

        except Exception as e:
            print(f"Errore strip {state}: {e}")

        nba_frame_index += nba_frames_in_group

    print(f"✅ Timeline generata con Anti-Sliding su {len(SPEED_MAP)} stati.")

def apply_transforms(obj, trajectory, b_traj, start_frame, shot_start, shot_end):
    """Applica posizione e rotazione corretta con interpolazione migliorata"""
    is_ball = (obj.name == BALL_NAME)
    
    # Per la palla, inseriamo keyframe per OGNI frame Blender per ridurre il fluttuare
    if is_ball:
        for i in range(len(trajectory)):
            frame = start_frame + int(i * FRAME_MULTIPLIER)
            obj.location = convert_coords(*trajectory[i])
            obj.keyframe_insert("location", frame=frame)
            
            # Interpolazione: aggiungi frame intermedi
            if i < len(trajectory) - 1:
                next_frame = start_frame + int((i + 1) * FRAME_MULTIPLIER)
                frames_between = next_frame - frame
                
                if frames_between > 1:
                    current_pos = trajectory[i]
                    next_pos = trajectory[i + 1]
                    
                    for j in range(1, frames_between):
                        interp_frame = frame + j
                        alpha = j / frames_between
                        
                        interp_x = current_pos[0] + (next_pos[0] - current_pos[0]) * alpha
                        interp_y = current_pos[1] + (next_pos[1] - current_pos[1]) * alpha
                        interp_z = current_pos[2] + (next_pos[2] - current_pos[2]) * alpha
                        
                        obj.location = convert_coords(interp_x, interp_y, interp_z)
                        obj.keyframe_insert("location", frame=interp_frame)
    
    # Per il giocatore
    else:
        for i, pos in enumerate(trajectory):
            frame = int(start_frame + (i * FRAME_MULTIPLIER))
            current_blender_frame = int(i * FRAME_MULTIPLIER)
            
            # Posizione (con interpolazione come la palla)
            obj.location = convert_coords(*pos)
            obj.keyframe_insert("location", frame=frame)
            
            pb = convert_coords(*pos)
            dist_ball = calculate_distance_2d(pos[:2], b_traj[i][:2])

            # Interpolazione posizione
            if i < len(trajectory) - 1:
                next_frame = start_frame + int((i + 1) * FRAME_MULTIPLIER)
                frames_between = next_frame - frame
                
                if frames_between > 1:
                    current_pos = pos
                    next_pos = trajectory[i + 1]
                    
                    for j in range(1, frames_between):
                        interp_frame = frame + j
                        alpha = j / frames_between
                        
                        interp_x = current_pos[0] + (next_pos[0] - current_pos[0]) * alpha
                        interp_y = current_pos[1] + (next_pos[1] - current_pos[1]) * alpha
                        interp_z = current_pos[2] + (next_pos[2] - current_pos[2]) * alpha
                        
                        obj.location = convert_coords(interp_x, interp_y, interp_z)
                        obj.keyframe_insert("location", frame=interp_frame)


            # DETERMINA COSA GUARDARE (Dinamico)
            # Se è nella finestra di tiro O ha la palla vicino -> Canestro
            if (shot_start <= current_blender_frame <= shot_end) or (dist_ball < POSSESSION_DISTANCE):
                target_type = "BASKET"
                basket = determine_basket_target(pos)
                target = convert_coords(basket[1], basket[0], 10.0)
                angle_offset = math.radians(+90)
            else:
                target_type = "PALLA"
                target = convert_coords(*b_traj[i])
                angle_offset = 0

            dx, dy = target[0] - pb[0], target[1] - pb[1]
            angle = math.atan2(dy, dx) + angle_offset

            # 3. DEBUG PRINT (Ogni 50 frame per non intasare la console)
            if i % 20 == 0:
                print(f"DEBUG Frame {i}: Target={target_type} | Offset={math.degrees(angle_offset):.1f}°")

            obj.rotation_euler.z = angle
            obj.keyframe_insert("rotation_euler", frame=frame)
            
# Interpolazione rotazione (per evitare scatti nel cambio target)
            if i < len(trajectory) - 1:
                next_frame = start_frame + int((i + 1) * FRAME_MULTIPLIER)
                frames_between = next_frame - frame
                if frames_between > 1:
                    n_pos = trajectory[i + 1]
                    n_dist = calculate_distance_2d(n_pos[:2], b_traj[i+1][:2])
                    n_blender = int((i+1) * FRAME_MULTIPLIER)
                    
                    if (shot_start <= n_blender <= shot_end) or (n_dist < POSSESSION_DISTANCE):
                        nb = determine_basket_target(n_pos)
                        n_target = convert_coords(nb[1], nb[0], 10.0)
                        n_offset = math.radians(+90)
                    else:
                        n_target = convert_coords(*b_traj[i+1])
                        n_offset = 0
                    
                    npb = convert_coords(*n_pos)
                    next_angle = math.atan2(n_target[1]-npb[1], n_target[0]-npb[0]) + n_offset
                    angle_diff = (next_angle - angle + math.pi) % (2 * math.pi) - math.pi
                    
                    for j in range(1, frames_between):
                        obj.rotation_euler.z = angle + (angle_diff * (j / frames_between))
                        obj.keyframe_insert("rotation_euler", frame=frame + j)

# ==================== MAIN ====================

def main():
    print("="*50)
    print("🚀 AVVIO SCRIPT SYNC TIRO (FINAL FIX)")
    print("="*50)
    
    try:
        metadata = load_metadata()

        poss_team_id = metadata.get('possession_team_id')
        if poss_team_id is not None:
            apply_team_colors(poss_team_id)
        else:
            print("⚠️ possession_team_id mancante nei metadata")

        event = find_event_in_dataset(metadata['game_id'], metadata['event_id'])
        moments, shot_offset = extract_shot_window(event, metadata['shot_frame'])
        p_traj, b_traj = get_trajectories(moments, metadata['player_id'])
        speeds = calculate_speeds(p_traj)
        
        poss_start, poss_end, _ = analyze_possession(p_traj, b_traj)

        shot_idx = min(shot_offset, len(p_traj)-1)
        basket_target = determine_basket_target(p_traj[shot_idx])
        shot_side = get_relative_side(p_traj[shot_idx], b_traj[shot_idx], basket_target)
        shot_anim_key = f"jumpshot_{shot_side}"
        shot_anim_real_name = ANIM_MAP.get(shot_anim_key, "jumpshot_dx")
        
        print(f"🏀 Tiro: {shot_anim_real_name} ({shot_side})")
        
        # === MODIFICA: CALCOLO DINAMICO DX/SX ===
        # 1. Recuperiamo i parametri specifici per questo tiro
        s_conf = SHOT_CONFIGS.get(shot_anim_real_name, DEFAULT_SHOT_CONFIG)
        
        # 2. Calcoliamo il picco sulla timeline di Blender
        blender_shot_peak = shot_offset * FRAME_MULTIPLIER
        
        # 3. Calcoliamo quanti frame "utili" ci sono prima del rilascio (Release - Start)
        # Es. DX: 144 - 50 = 94 frame prima del picco
        frames_before_peak = s_conf["release"] - s_conf["crop"]
        
        # 4. Calcoliamo quanti frame ci sono dopo il rilascio (End - Release)
        # Es. DX: 340 - 144 = 196 frame dopo il picco
        frames_after_peak = s_conf["end"] - s_conf["release"]
        
        # 5. Definiamo inizio e fine sulla timeline globale
        shot_blender_start = blender_shot_peak - frames_before_peak
        shot_blender_end = blender_shot_peak + frames_after_peak

        states = determine_state_sequence(p_traj, b_traj, speeds, shot_offset, shot_blender_start, shot_blender_end)
        print(f"🧠 Stati: {list(set(states))}")

        armature = bpy.data.objects[ARMATURE_NAME]
        ball = bpy.data.objects[BALL_NAME]
        
        # FIX: Pulizia azione attiva
        if armature.animation_data:
            armature.animation_data.action = None

        create_sequential_strips(armature, states, shot_anim_real_name, p_traj)

        look_target_traj = []
        for p in p_traj:
            b = determine_basket_target(p)
            look_target_traj.append((b[0], b[1], 10.0))

        # Passiamo shot_blender_start e shot_blender_end invece di poss_start
        apply_transforms(armature, p_traj, b_traj, 1, shot_blender_start, shot_blender_end)
        apply_transforms(ball, b_traj, b_traj, 1, None, None) # Per la palla i tempi non servono
                
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = int(len(p_traj) * FRAME_MULTIPLIER)
        bpy.context.scene.render.fps = FPS_ANIMATION
        
        print("✅ FINE.")
        
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()