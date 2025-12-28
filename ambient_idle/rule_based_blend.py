import bpy
import json
import math
import os
from itertools import groupby

# ==================== CONFIGURATION ====================

# Paths
BASE_PATH = r"C:\Users\DISI\Documents\SportTech Students\Basket_Virtualisation\Sport-Tech-Project"
DATASET_JSON = os.path.join(BASE_PATH, "nba_tracking_data_tiny.json")
METADATA_JSON = os.path.join(BASE_PATH, "shot_metadata.json")

# Blender Objects
ARMATURE_NAME = "Armature"
BALL_NAME = "ball"

# Time Sync
FPS_JSON = 25
FPS_ANIMATION = 120
FRAME_MULTIPLIER = FPS_ANIMATION / FPS_JSON 

# NBA Court Dimensions (in feet)
COURT_LENGTH = 94.0
COURT_WIDTH = 50.0

BASKET_1 = (COURT_LENGTH, COURT_WIDTH / 2)  # Right/Top Basket
BASKET_2 = (0, COURT_WIDTH / 2)             # Left/Bottom Basket

# === SHOT SYNC PARAMETERS ===
SHOT_CONFIGS = {
    "jumpshot_dx": {"crop": 50, "release": 144, "end": 276},
    "jumpshot_sx": {"crop": 50, "release": 150, "end": 340}
}
DEFAULT_SHOT_CONFIG = {"crop": 50, "release": 150, "end": 300}

# === ANIMATION SPEEDS (Anti-Sliding) ===
# Values in ft/s
SPEED_MAP = {
    # Base Movement
    "walk": 5.5362,
    "slow_run": 7.6720,
    "fast_run": 9.0487,
    "back_run": 5.9016,
    
    # Dribbling Movement
    "dribble_walk_dx": 6.2386,
    "dribble_walk_sx": 6.1800,
    "dribble_run_dx": 9.5703,
    "dribble_run_sx": 9.0724,
    
    # Catch
    "run_catch_dx": 2.6300,
    "run_catch_sx": 3.4021,
    
    # Extra
    "celly_lebron": 3.8624
}

# === TEAM COLORS ===
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

# Soglie
POSSESSION_DISTANCE = 2.5
WALK_SPEED_THRESHOLD = 0.3
RUN_SPEED_THRESHOLD = 3.0

# === ANIMATION MAPPING ===
ANIM_MAP = {
    # NO BALL (MOVEMENT)
    "idle": "idle",
    "walk": "walk",
    "slow_run": "slow_run",
    "fast_run": "fast_run",
    "back_run": "back_run",
    
    # HOLDING
    "holding": "idle_ball",
    
    # CATCH
    "static_catch_dx": "static_catch_dx", "static_catch_sx": "static_catch_sx",
    "run_catch_dx": "run_catch_dx", "run_catch_sx": "run_catch_sx",
    
    # DRIBBLE MOVE
    "dribble_walk_dx": "dribble_walk_dx", "dribble_walk_sx": "dribble_walk_sx",
    "dribble_run_dx": "dribble_run_dx", "dribble_run_sx": "dribble_run_sx",
    
    # DRIBBLE STATIC
    "dribble_static_dx": "stationary_dribble_dx",
    "dribble_static_sx": "stationary_shot_dribble_sx",
    
    # SHOT
    "jumpshot_dx": "jumpshot_dx", "jumpshot_sx": "jumpshot_sx",
}

# ==================== HELPER FUNCTIONS ====================

def convert_coords(nba_x, nba_y, nba_z):
    return (nba_y, nba_x, nba_z)

def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def calculate_distance_3d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

def load_metadata():
    print(f"Loading metadata...")
    with open(METADATA_JSON, 'r') as f:
        return json.load(f)

def find_event_in_dataset(game_id, id):
    print(f"Searching event {id}...")
    with open(DATASET_JSON, 'r', encoding='utf-8') as f:
        try:
            for line in f:
                data = json.loads(line)
                if str(data.get('gameid')) == str(game_id) and str(data['event_info']['id']) == str(id):
                    return data
        except:
            f.seek(0)
            for line in f:
                try:
                    data = json.loads(line.strip().rstrip(','))
                    if str(data.get('gameid')) == str(game_id) and str(data.get('event_info', {}).get('id')) == str(id):
                        return data
                except: continue
    raise Exception("Event not found")

def extract_shot_window(event, shot_frame):
    moments = event['moments']
    FPS_DATA = 25
    frames_before = 3 * FPS_DATA
    frames_after = 2 * FPS_DATA
    
    if shot_frame >= len(moments): 
        print(f"Shot frame {shot_frame} out of range. Resetting to middle.")
        shot_frame = len(moments) // 2
        
    start_idx = max(0, shot_frame - frames_before)
    end_idx = min(len(moments), shot_frame + frames_after)
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
        if not found:
            if p_traj: p_traj.append(p_traj[-1])
            else: p_traj.append((0,0,0))
    return p_traj, b_traj

def analyze_possession(player_traj, ball_traj):
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
    dist_1 = calculate_distance_2d(player_pos, BASKET_1)
    dist_2 = calculate_distance_2d(player_pos, BASKET_2)
    return BASKET_1 if dist_1 < dist_2 else BASKET_2
    
def get_relative_side(player_pos, ball_pos, target_pos):
    look_dir = (target_pos[0] - player_pos[0], target_pos[1] - player_pos[1])
    ball_dir = (ball_pos[0] - player_pos[0], ball_pos[1] - player_pos[1])
    cross_product = (look_dir[0] * ball_dir[1]) - (look_dir[1] * ball_dir[0])
    return "dx" if cross_product > 0 else "sx"

def is_ball_bouncing(ball_traj, current_frame, window=10, threshold=1.5):
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
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16)/255.0 for i in (0, 2, 4)) + (1.0,)

def apply_team_colors(team_id):
    print(f"Applying colors for Team ID: {team_id}")
    try:
        t_id = int(float(team_id))
    except:
        print(f"Invalid Team ID: {team_id}")
        return

    team_data = TEAM_MAPPING.get(t_id)
    if not team_data:
        print(f"Team ID {t_id} not found in mapping. Using default.")
        return

    print(f"  Team found: {team_data['name']}")

    targets = [
        ("Beta_Surface", team_data['color']),
        ("Beta_Joints", team_data['color2'])
    ]

    for obj_name, hex_color in targets:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            if not obj.data.materials:
                mat = bpy.data.materials.new(name=f"Mat_{team_data['name']}_{obj_name}")
                obj.data.materials.append(mat)
            else:
                mat = obj.data.materials[0]
                mat.name = f"Mat_{team_data['name']}_{obj_name}"

            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            bsdf = nodes.get("Principled BSDF")
            
            if bsdf:
                rgba = hex_to_rgba(hex_color)
                bsdf.inputs['Base Color'].default_value = rgba
                print(f"    {obj_name} -> {hex_color}")
            else:
                print(f"    Principled BSDF missing on {obj_name}")
        else:
            print(f"    Object not found: {obj_name}")

# ==================== CORE LOGIC ====================

def determine_state_sequence(p_traj, b_traj, speeds, shot_offset, shot_blender_start, shot_blender_end):
    print("Calculating states (Full Movement Logic)...")
    print(f"  Shot window: {shot_blender_start} -> {shot_blender_end}")
    print(f"  Total frames: {len(p_traj)}")
    
    first_poss, _, _ = analyze_possession(p_traj, b_traj)
    states = []

    for i in range(len(p_traj)):
        current_blender_frame = int(i * FRAME_MULTIPLIER)

        # === SHOT PROTECTION (FORCE OVERRIDE) ===
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

        # 1. AFTER SHOT
        if current_blender_frame > shot_blender_end:
            if speed > 0.2 and is_moving_backwards(player_pos, prev_pos, look_target):
                states.append("back_run")
            elif speed > 5.5: states.append("fast_run")
            elif speed > 3.0: states.append("slow_run")
            elif speed > 0.2: states.append("walk")
            else: states.append("idle")
            continue

        # 2. OFF BALL
        if not has_ball:
            if speed > 0.2 and is_moving_backwards(player_pos, prev_pos, look_target):
                states.append("back_run")
            elif speed > 5.5: states.append("fast_run")
            elif speed > 3.0: states.append("slow_run")
            elif speed > 0.2: states.append("walk")
            else: states.append("idle")
            continue
            
        # 3. ON BALL
        past_idx = max(0, i-5)
        past_dist = calculate_distance_2d(p_traj[past_idx][:2], b_traj[past_idx][:2])
        is_catch_phase = (past_dist >= POSSESSION_DISTANCE and has_ball)
        
        if is_catch_phase and i > 5:
            # Latching logic for catch
            prev_state = states[-1] if len(states) > 0 else ""
            if prev_state == "holding" or "catch" in prev_state:
                states.append(prev_state) 
                continue

            basket_ref = determine_basket_target(player_pos)
            look_vec = (basket_ref[0] - player_pos[0], basket_ref[1] - player_pos[1])
            look_mag = math.sqrt(look_vec[0]**2 + look_vec[1]**2)
            ball_vec = (ball_pos[0] - player_pos[0], ball_pos[1] - player_pos[1])
            ball_mag = math.sqrt(ball_vec[0]**2 + ball_vec[1]**2)

            is_central = False
            side_raw = "dx"

            if look_mag > 0 and ball_mag > 0:
                look_norm = (look_vec[0] / look_mag, look_vec[1] / look_mag)
                ball_norm = (ball_vec[0] / ball_mag, ball_vec[1] / ball_mag)
                cross_val = (look_norm[0] * ball_norm[1]) - (look_norm[1] * ball_norm[0])
                dot_val = (look_norm[0] * ball_norm[0]) + (look_norm[1] * ball_norm[1])

                if abs(cross_val) < 0.35 and dot_val > 0:
                    is_central = True
                side_raw = "dx" if cross_val > 0 else "sx"

            if is_central:
                states.append("holding")
            else:
                if speed > WALK_SPEED_THRESHOLD: 
                    states.append(f"run_catch_{side_raw}")
                else: 
                    states.append(f"static_catch_{side_raw}")
            continue

        side = get_relative_side(player_pos, ball_pos, look_target)

        if speed > RUN_SPEED_THRESHOLD: states.append(f"dribble_run_{side}")
        elif speed > WALK_SPEED_THRESHOLD: states.append(f"dribble_walk_{side}")
        else:
            if is_ball_bouncing(b_traj, i): states.append(f"dribble_static_{side}") 
            else: states.append("holding") 
    
    print(f"State distribution:")
    from collections import Counter
    counter = Counter(states)
    for state, count in counter.most_common():
        print(f"  {state}: {count} frames")

    return states

def create_sequential_strips(armature, state_sequence, shot_anim_name, p_traj, shot_blender_start):
    print("Creating Sequential Timeline (Staircase Method - NO T-POSE)...")

    BLEND_FRAMES = 5

    if not armature.animation_data:
        armature.animation_data_create()
    
    # Clean existing tracks
    while armature.animation_data.nla_tracks:
        armature.animation_data.nla_tracks.remove(armature.animation_data.nla_tracks[0])
    armature.animation_data.action = None

    current_blender_frame = 1
    nba_frame_index = 0
    prev_strip = None
    
    # Track counter to always create new tracks on top
    track_counter = 1

    grouped_states = groupby(state_sequence)
    
    for state, group in grouped_states:
        group_list = list(group)
        nba_frames_in_group = len(group_list)
        duration_frames = int(nba_frames_in_group * FRAME_MULTIPLIER)
        
        if duration_frames <= 0: 
            nba_frame_index += nba_frames_in_group
            continue

        # === 1. START CALCULATION ===
        if state == "SHOT":
            strip_start = int(shot_blender_start)
        else:
            strip_start = int(current_blender_frame)

        # === 2. EXTEND PREVIOUS STRIP ===
        # The strip underneath must last long enough to cover the blend.
        if prev_strip:
            overlap_end = strip_start + BLEND_FRAMES
            if overlap_end > prev_strip.frame_start:
                 prev_strip.frame_end = int(overlap_end)
            else:
                 prev_strip.frame_end = int(strip_start)

        # === 3. SCALE CALCULATION (ANTI-SLIDING) ===
        scale_factor = 1.0
        if state in SPEED_MAP:
            reference_speed = SPEED_MAP[state]
            start_idx = nba_frame_index
            end_idx = min(nba_frame_index + nba_frames_in_group, len(p_traj) - 1)
            
            segment_dist = 0.0
            for k in range(start_idx, end_idx):
                p1 = p_traj[k]
                p2 = p_traj[k+1]
                dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                segment_dist += dist
            
            duration_sec = nba_frames_in_group / FPS_JSON
            target_speed = segment_dist / duration_sec if duration_sec > 0 else 0

            if target_speed > 0.1:
                scale_factor = max(0.5, min(2.0, reference_speed / target_speed))

        # === 4. ACTION SELECTION ===
        action_name = shot_anim_name if state == "SHOT" else ANIM_MAP.get(state, ANIM_MAP.get("idle", "idle"))
        if action_name not in bpy.data.actions:
            current_blender_frame += duration_frames
            nba_frame_index += nba_frames_in_group
            continue
        action = bpy.data.actions[action_name]
        source_duration = max(0.1, action.frame_range[1] - action.frame_range[0])
        
        # === 5. CREATE NEW TRACK ===
        current_track = armature.animation_data.nla_tracks.new()
        current_track.name = f"Track_{track_counter:03d}_{state}"
        track_counter += 1
        
        try:
            strip = current_track.strips.new(name=state, start=strip_start, action=action)
            strip.scale = scale_factor
            
            if state == "SHOT":
                s_conf = SHOT_CONFIGS.get(shot_anim_name, DEFAULT_SHOT_CONFIG)
                strip.action_frame_start = s_conf["crop"]
                strip.action_frame_end = s_conf["end"]
                strip.scale = 1.0 
                strip.repeat = 1.0 
            elif state == "dribble_static_sx":
                strip.action_frame_start = 163
                strip.action_frame_end = action.frame_range[1]
                strip.repeat = (duration_frames / scale_factor) / max(0.1, strip.action_frame_end - strip.action_frame_start)
            elif state in ["run_catch_dx", "run_catch_sx"]:
                strip.action_frame_start = 180
                strip.action_frame_end = action.frame_range[1]
                strip.repeat = (duration_frames / scale_factor) / max(0.1, strip.action_frame_end - strip.action_frame_start)
            else:
                strip.action_frame_start = action.frame_range[0]
                strip.action_frame_end = action.frame_range[1]
                strip.repeat = (duration_frames / scale_factor) / source_duration

            strip.frame_end = int(strip_start + duration_frames)
            strip.extrapolation = 'HOLD' 
            strip.blend_type = 'REPLACE' 
            
            # === 6. BLEND SETUP ===
            strip.use_auto_blend = False
            strip.blend_out = 0
            
            if prev_strip:
                strip.blend_in = BLEND_FRAMES # Fade in over the previous track
                prev_strip.blend_out = 0      # Previous track remains solid underneath
            else:
                strip.blend_in = 0

            prev_strip = strip
            current_blender_frame = strip.frame_end

        except Exception as e:
            print(f"Error strip {state}: {e}")
            current_blender_frame += duration_frames

        nba_frame_index += nba_frames_in_group

    print(f"Timeline completed ({track_counter} tracks generated).")

def apply_transforms(obj, trajectory, b_traj, start_frame, shot_start, shot_end):
    # Applies position and rotation with improved interpolation
    is_ball = (obj.name == BALL_NAME)
    
    # For ball, insert keyframe every frame
    if is_ball:
        for i in range(len(trajectory)):
            frame = start_frame + int(i * FRAME_MULTIPLIER)
            obj.location = convert_coords(*trajectory[i])
            obj.keyframe_insert("location", frame=frame)
            
            # Interpolation
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
    
    # For player
    else:
        for i, pos in enumerate(trajectory):
            frame = int(start_frame + (i * FRAME_MULTIPLIER))
            current_blender_frame = int(i * FRAME_MULTIPLIER)
            
            obj.location = convert_coords(*pos)
            obj.keyframe_insert("location", frame=frame)
            
            pb = convert_coords(*pos)
            dist_ball = calculate_distance_2d(pos[:2], b_traj[i][:2])

            # Position Interpolation
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


            # DETERMINE LOOK TARGET
            if (shot_start <= current_blender_frame <= shot_end) or (dist_ball < POSSESSION_DISTANCE):
                target_type = "BASKET"
                basket = determine_basket_target(pos)

                target = convert_coords(basket[0], basket[1], 10.0)
                angle_offset = math.radians(0)
            else:
                target_type = "BALL"
                target = convert_coords(*b_traj[i])
                angle_offset = 0

            dx, dy = target[0] - pb[0], target[1] - pb[1]
            angle = math.atan2(dy, dx) + angle_offset

            if i % 20 == 0:
                print(f"DEBUG Frame {i}: Target={target_type} | Offset={math.degrees(angle_offset):.1f} deg")

            obj.rotation_euler.z = angle
            obj.keyframe_insert("rotation_euler", frame=frame)
            
            # Rotation Interpolation
            if i < len(trajectory) - 1:
                next_frame = start_frame + int((i + 1) * FRAME_MULTIPLIER)
                frames_between = next_frame - frame
                if frames_between > 1:
                    n_pos = trajectory[i + 1]
                    n_dist = calculate_distance_2d(n_pos[:2], b_traj[i+1][:2])
                    n_blender = int((i+1) * FRAME_MULTIPLIER)
                    
                    if (shot_start <= n_blender <= shot_end) or (n_dist < POSSESSION_DISTANCE):
                        nb = determine_basket_target(n_pos)
                        n_target = convert_coords(nb[0], nb[1], 10.0)
                        n_offset = math.radians(0)
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
    print("STARTING SHOT SYNC SCRIPT")
    print("="*50)
    
    try:
        metadata = load_metadata()

        poss_team_id = metadata.get('possession_team_id')
        if poss_team_id is not None:
            apply_team_colors(poss_team_id)
        else:
            print("possession_team_id missing in metadata")

        event = find_event_in_dataset(metadata['game_id'], metadata['event_id'])
        moments, shot_offset = extract_shot_window(event, metadata['shot_frame'])
        p_traj, b_traj = get_trajectories(moments, metadata['player_id'])
        speeds = calculate_speeds(p_traj)
        
        poss_start, poss_end, _ = analyze_possession(p_traj, b_traj)

        shot_idx = min(shot_offset-50, len(p_traj)-1)
        basket_target = determine_basket_target(p_traj[shot_idx])
        shot_side = get_relative_side(p_traj[shot_idx], b_traj[shot_idx], basket_target)
        shot_anim_key = f"jumpshot_{shot_side}"
        shot_anim_real_name = ANIM_MAP.get(shot_anim_key, "jumpshot_dx")
        
        print(f"Shot: {shot_anim_real_name} ({shot_side})")
        
        # === DYNAMIC SHOT CALCULATION ===
        s_conf = SHOT_CONFIGS.get(shot_anim_real_name, DEFAULT_SHOT_CONFIG)
        blender_shot_peak = shot_offset * FRAME_MULTIPLIER
        frames_before_peak = s_conf["release"] - s_conf["crop"]
        frames_after_peak = s_conf["end"] - s_conf["release"]
        
        shot_blender_start = blender_shot_peak - frames_before_peak
        shot_blender_end = blender_shot_peak + frames_after_peak

        states = determine_state_sequence(p_traj, b_traj, speeds, shot_offset, shot_blender_start, shot_blender_end)
        print(f"States: {list(set(states))}")

        armature = bpy.data.objects[ARMATURE_NAME]
        ball = bpy.data.objects[BALL_NAME]
        
        if armature.animation_data:
            armature.animation_data.action = None

        create_sequential_strips(armature, states, shot_anim_real_name, p_traj, shot_blender_start)

        look_target_traj = []
        for p in p_traj:
            b = determine_basket_target(p)
            look_target_traj.append((b[0], b[1], 10.0))

        apply_transforms(armature, p_traj, b_traj, 1, shot_blender_start, shot_blender_end)
        apply_transforms(ball, b_traj, b_traj, 1, None, None)
                
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = int(len(p_traj) * FRAME_MULTIPLIER)
        bpy.context.scene.render.fps = FPS_ANIMATION
        
        print("DONE.")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()