import bpy
import json
import math
import os

# ==================== CONFIGURAZIONE ====================

# Percorsi (Assicurati che siano corretti)
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
DATASET_JSON = os.path.join(BASE_PATH, "dataset_3pt.json")
METADATA_JSON = os.path.join(BASE_PATH, "shot_metadata.json")

# Oggetti Blender
ARMATURE_NAME = "Armature"
BALL_NAME = "ball"

# Sincronizzazione Temporale
FPS_JSON = 25
FPS_ANIMATION = 360
FRAME_MULTIPLIER = FPS_ANIMATION / FPS_JSON  # 14.4

# === PARAMETRI CRITICI PER IL SYNC ===
JUMPSHOT_RELEASE_FRAME = 150  # Il frame nell'FBX dove la palla lascia la mano
SHOT_ANIMATION_TOTAL_FRAMES = 300 # Durata approssimativa dell'animazione jumpshot
# =====================================

# Soglie
POSSESSION_DISTANCE = 2.5     # piedi (aumentato leggermente per sicurezza)
WALK_SPEED_THRESHOLD = 2.0    # piedi/frame (ALZATO: 0.3 era troppo sensibile al rumore)
RUN_SPEED_THRESHOLD = 4.0     # piedi/frame

# Animazioni
# NOTA: Assicurati che l'azione "idle" esista in Blender (creata con lo script precedente)
ANIMATIONS = {
    "dribble_run_dx": "dribble_run_dx", "dribble_run_sx": "dribble_run_sx",
    "dribble_walk_dx": "dribble_walk_dx", "dribble_walk_sx": "dribble_walk_sx",
    "static_catch_dx": "static_catch_dx", "static_catch_sx": "static_catch_sx",
    "run_catch_dx": "run_catch_dx", "run_catch_sx": "run_catch_sx",
    "jumpshot_dx": "jumpshot_dx", "jumpshot_sx": "jumpshot_sx",
    "stationary_shot_dx": "stationary_shot_dx", "stationary_shot_sx": "stationary_shot_sx",
    "idle": "idle"  # <--- NUOVA VOCE MODIFICATA
}

# Blending
BLEND_FRAMES = 40 # Ridotto leggermente per transizioni più snappy a 360fps

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
            data = json.load(f) # Prova caricamento lista
            if isinstance(data, dict): data = [data]
            for event in data:
                if str(event.get('gameid')) == str(game_id) and str(event.get('event_info', {}).get('id')) == str(id):
                    return event
        except:
            f.seek(0)
            for line in f: # Fallback riga per riga
                try:
                    event = json.loads(line.strip().rstrip(','))
                    if str(event.get('gameid')) == str(game_id) and str(event.get('event_info', {}).get('id')) == str(id):
                        return event
                except: continue
    raise Exception("Evento non trovato")

def extract_shot_window(event, player_id, shot_frame):
    moments = event['moments']
    # Protezione contro shot_frame fuori range
    if shot_frame >= len(moments): 
        print(f"⚠️ Shot frame {shot_frame} oltre la lunghezza dati. Reset a metà.")
        shot_frame = len(moments) // 2
        
    # Estraiamo una finestra ampia per sicurezza
    start_idx = max(0, shot_frame - 50)
    end_idx = min(len(moments), shot_frame + 50)
    return moments[start_idx:end_idx], shot_frame - start_idx

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
        # Usa coordinate convertite per la distanza reale in Blender
        p_3d = convert_coords(*p)
        b_3d = convert_coords(*b)
        dist = calculate_distance_3d(p_3d, b_3d)
        
        if dist < POSSESSION_DISTANCE:
            possession_frames.append(i)
            
    if possession_frames:
        return possession_frames[0], possession_frames[-1], possession_frames
    return None, None, []

def calculate_speeds(traj):
    """Calcola la velocità 2D del giocatore frame per frame"""
    speeds = [0.0]
    for i in range(1, len(traj)):
        dist = calculate_distance_2d(traj[i-1], traj[i])
        speeds.append(dist)
    return speeds

def determine_side(player_pos, ball_pos):
    """Determina se la palla è a destra o sinistra"""
    p_x = player_pos[1] # In Blender X è la Y NBA
    b_x = ball_pos[1]
    return "dx" if b_x >= p_x else "sx"

# ==================== CORE LOGIC ====================

def determine_state_sequence(p_traj, b_traj, speeds, first_poss, shot_offset, shot_blender_start, shot_blender_end):
    """
    Determina lo STATO DI BASE (Idle, Catch, Dribble) frame per frame.
    Il Tiro non viene deciso qui, ma sovrascritto dopo.
    """
    print("🧠 Calcolo stati di base...")
    states = []
    
    for i in range(len(p_traj)):
        # Calcolo frame Blender attuale
        current_blender_frame = int(i * FRAME_MULTIPLIER)
        
        # Se siamo DOPO il tiro, forza IDLE
        if current_blender_frame > shot_blender_end:
            states.append("idle") # <--- MODIFICATO QUI
            continue
            
        # Se non abbiamo ancora la palla -> IDLE
        if first_poss is None or i < first_poss:
            states.append("idle") # <--- MODIFICATO QUI
            continue
            
        # Se abbiamo la palla:
        # Determiniamo se è Catch (primi 15 frame di possesso) o Dribble
        speed = speeds[i]
        side = determine_side(p_traj[i], b_traj[i])
        frames_since_poss = i - first_poss
        
        if frames_since_poss < 15: # Fase CATCH
            if speed < WALK_SPEED_THRESHOLD:
                states.append(f"static_catch_{side}")
            else:
                states.append(f"run_catch_{side}")
        else: # Fase DRIBBLE
            if speed < WALK_SPEED_THRESHOLD:
                states.append(f"dribble_walk_{side}")
            elif speed < RUN_SPEED_THRESHOLD:
                states.append(f"dribble_walk_{side}")
            else:
                states.append(f"dribble_run_{side}")
                
    return states

def setup_nla_tracks(armature, unique_anims, shot_anim_name, shot_blender_start_frame):
    """
    Configura le tracce NLA:
    Track 1 (Base): Contiene Idle, Catch, Dribble (in Loop/Repeat)
    Track 2 (Shot): Contiene SOLO il tiro (No Loop, posizione fissa)
    """
    if not armature.animation_data: armature.animation_data_create()
    
    # Rimuovi tracce vecchie
    for track in armature.animation_data.nla_tracks:
        armature.animation_data.nla_tracks.remove(track)
        
    base_track = armature.animation_data.nla_tracks.new()
    base_track.name = "Track_Base"
    
    shot_track = armature.animation_data.nla_tracks.new()
    shot_track.name = "Track_Shot"
    
    strips_dict = {}
    
    # 1. Setup Strip di Base (Loopabili)
    for anim_name in unique_anims:
        if anim_name == shot_anim_name: continue # Il tiro va nell'altra traccia
        if anim_name not in bpy.data.actions: continue
        
        act = bpy.data.actions[anim_name]
        strip = base_track.strips.new(anim_name, start=1, action=act)
        strip.repeat = 500 # Loop infinito
        strip.blend_type = 'REPLACE'
        strip.use_auto_blend = True
        strip.influence = 0.0 # Spente di default
        strips_dict[anim_name] = strip
        
    # 2. Setup Strip di Tiro (Singola, posizionata esatta)
    if shot_anim_name in bpy.data.actions:
        act = bpy.data.actions[shot_anim_name]
        # La strip inizia al frame calcolato per sincronizzare il rilascio
        strip = shot_track.strips.new(shot_anim_name, start=int(shot_blender_start_frame), action=act)
        strip.repeat = 1 # NO LOOP! IMPORTANTE!
        strip.blend_type = 'REPLACE' # O Replace, ma su track superiore vince comunque
        strip.influence = 0.0 # Spenta finché non serve
        strip.blend_in = 20   # Blend in entrata
        strip.blend_out = 20  # Blend in uscita
        strips_dict['SHOT'] = strip

    return strips_dict

def apply_animation_logic(strips, state_sequence, shot_blender_start, shot_blender_end, start_frame_offset=1):
    print("🔑 Applicazione keyframe logici...")
    
    current_base_anim = None
    is_shooting = False
    
    for i, state in enumerate(state_sequence):
        blender_frame = start_frame_offset + int(i * FRAME_MULTIPLIER)
        
        # Siamo nel momento del tiro?
        should_shoot = (shot_blender_start <= blender_frame <= shot_blender_end)
        
        # --- GESTIONE TIRO ---
        if 'SHOT' in strips:
            strip = strips['SHOT']
            if should_shoot != is_shooting:
                target = 1.0 if should_shoot else 0.0
                strip.influence = target
                try: strip.keyframe_insert(data_path="influence", frame=blender_frame)
                except: pass
                is_shooting = should_shoot

        # --- GESTIONE BASE ---
        # Se stiamo tirando, spegni TUTTO il resto forzatamente
        if is_shooting:
            if current_base_anim is not None:
                for name, strip in strips.items():
                    if name == 'SHOT': continue
                    strip.influence = 0.0
                    try: strip.keyframe_insert(data_path="influence", frame=blender_frame)
                    except: pass
                current_base_anim = None # Reset per forzare riattivazione dopo
        
        # Se NON stiamo tirando, gestisci le animazioni base normalmente
        else:
            if state != current_base_anim:
                for name, strip in strips.items():
                    if name == 'SHOT': continue
                    
                    target = 1.0 if name == state else 0.0
                    strip.influence = target
                    try: strip.keyframe_insert(data_path="influence", frame=blender_frame)
                    except: pass
                
                current_base_anim = state

def apply_transforms(obj, trajectory, b_traj, start_frame):
    """Applica posizione e rotazione corretta"""
    is_ball = (obj.name == BALL_NAME)
    
    for i, pos in enumerate(trajectory):
        frame = start_frame + int(i * FRAME_MULTIPLIER)
        
        # Posizione
        obj.location = convert_coords(*pos)
        obj.keyframe_insert("location", frame=frame)
        
        # Rotazione (Solo per giocatore)
        if not is_ball:
            # Guarda verso la palla
            pb = convert_coords(*pos)
            bb = convert_coords(*b_traj[i])
            dx = bb[0] - pb[0]
            dy = bb[1] - pb[1]
            
            # Angolo corretto per Blender (Y-forward solitamente richiede atan2(dx, dy) o offset)
            # Se guarda a lato, prova a rimuovere il - pi/2
            angle = math.atan2(dy, dx)
            
            obj.rotation_euler.z = angle
            obj.keyframe_insert("rotation_euler", frame=frame)

# ==================== MAIN ====================

def main():
    print("="*50)
    print("🚀 AVVIO SCRIPT SYNC TIRO 360/25 (CON NUOVO IDLE)")
    print("="*50)
    
    try:
        # 1. Dati
        metadata = load_metadata()
        event = find_event_in_dataset(metadata['game_id'], metadata['event_id'])
        moments, shot_offset = extract_shot_window(event, metadata['player_id'], metadata['shot_frame'])
        p_traj, b_traj = get_trajectories(moments, metadata['player_id'])
        speeds = calculate_speeds(p_traj)
        
        # 2. Analisi Possesso e Lato Tiro
        poss_start, _, _ = analyze_possession(p_traj, b_traj)
        
        # Calcoliamo il lato del tiro al momento del tiro (Frame statico)
        shot_idx = min(shot_offset, len(p_traj)-1)
        shot_side = determine_side(p_traj[shot_idx], b_traj[shot_idx])
        # --- MODIFICA QUI ---
        # Vecchio codice: controllava la velocità
        # shot_anim_name = f"jumpshot_{shot_side}" if speeds[shot_idx] > WALK_SPEED_THRESHOLD else f"stationary_shot_{shot_side}"
        
        # Nuovo codice: Forza sempre JUMPSHOT
        shot_anim_name = f"jumpshot_{shot_side}"
        
        print(f"🏀 Shot Frame (Dataset): {shot_offset}")
        print(f"🏀 Shot Side: {shot_side.upper()}")
        print(f"🏀 Animazione Tiro Scelta: {shot_anim_name}")
        
        # 3. Calcolo Sync Temporale
        # Il frame del dataset dove avviene il tiro convertito in Blender
        blender_shot_peak = shot_offset * FRAME_MULTIPLIER
        
        # L'animazione deve iniziare N frame prima affinché il rilascio (150) coincida con il picco
        shot_blender_start = blender_shot_peak - JUMPSHOT_RELEASE_FRAME
        shot_blender_end = shot_blender_start + SHOT_ANIMATION_TOTAL_FRAMES
        
        print(f"⏱️  Sync Timing:")
        print(f"   - Shot Peak (Blender): {blender_shot_peak}")
        print(f"   - Anim Start (Blender): {shot_blender_start}")
        print(f"   - Anim End (Blender): {shot_blender_end}")
        
        # 4. Calcolo Stati Base (ORA USA 'IDLE')
        base_states = determine_state_sequence(p_traj, b_traj, speeds, poss_start, shot_offset, shot_blender_start, shot_blender_end)
        
        # 5. Blender Setup
        armature = bpy.data.objects[ARMATURE_NAME]
        ball = bpy.data.objects[BALL_NAME]
        
        # Prepariamo tutte le animazioni uniche + quella del tiro
        unique_base = list(set(base_states))
        strips = setup_nla_tracks(armature, unique_base, shot_anim_name, shot_blender_start)
        
        # 6. Applicazione
        start_frame = 1
        apply_animation_logic(strips, base_states, shot_blender_start, shot_blender_end, start_frame)
        apply_transforms(armature, p_traj, b_traj, start_frame)
        apply_transforms(ball, b_traj, [convert_coords(*p) for p in b_traj], start_frame) # Ball rotation ignorata
        
        # Setup Finale
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = int(len(p_traj) * FRAME_MULTIPLIER)
        bpy.context.scene.render.fps = FPS_ANIMATION
        
        print("✅ GENERAZIONE COMPLETATA CON SUCCESSO")
        
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()