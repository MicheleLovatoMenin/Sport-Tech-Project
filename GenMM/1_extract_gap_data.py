import bpy
import json
import math
import os
from itertools import groupby

# ==================== CONFIGURATION ====================

# Paths
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
DATASET_JSON = os.path.join(BASE_PATH, "nba_tracking_data_tiny.json")
METADATA_JSON = os.path.join(BASE_PATH, "shot_metadata.json")

# Blender Objects
ARMATURE_NAME = "Armature"
BALL_NAME = "ball"

# Time Synchronization
FPS_JSON = 25
FPS_ANIMATION = 120
FRAME_MULTIPLIER = FPS_ANIMATION / FPS_JSON 

# NBA Court Dimensions
COURT_LENGTH = 94.0
COURT_WIDTH = 50.0

# Basket Coordinates
BASKET_1 = (COURT_WIDTH / 2, COURT_LENGTH)
BASKET_2 = (COURT_WIDTH / 2, 0)

# === CRITICAL SYNC PARAMETERS
SHOT_CONFIGS = {
    "jumpshot_dx": {"crop": 50, "release": 144, "end": 340},
    "jumpshot_sx": {"crop": 50, "release": 150, "end": 363}
}
# Safety Fallback
DEFAULT_SHOT_CONFIG = {"crop": 50, "release": 150, "end": 300}

# === ANIMATION SPEED CONFIGURATION (Anti-Sliding) ===
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
    
    # Moving Catch
    "run_catch_dx": 2.6300,
    "run_catch_sx": 3.4021
}

# =====================================

# Thresholds
POSSESSION_DISTANCE = 2.5
WALK_SPEED_THRESHOLD = 2.0
RUN_SPEED_THRESHOLD = 4.0

# === ANIMATION MAPPING ===
ANIM_MAP = {
    # NO BALL
    "idle": "idle",
    "walk": "walk",
    "slow_run": "slow_run",
    "fast_run": "fast_run",
    "back_run": "back_run",
    
    # HOLDING (Ball still in hand)
    "holding": "idle_ball",
    
    # CATCH
    "static_catch_dx": "static_catch_dx", "static_catch_sx": "static_catch_sx",
    "run_catch_dx": "run_catch_dx", "run_catch_sx": "run_catch_sx",
    
    # DRIBBLE MOVEMENT
    "dribble_walk_dx": "dribble_walk_dx", "dribble_walk_sx": "dribble_walk_sx",
    "dribble_run_dx": "dribble_run_dx", "dribble_run_sx": "dribble_run_sx",
    
    # STATIC DRIBBLE
    "dribble_static_dx": "stationary_dribble_dx",
    "dribble_static_sx": "stationary_shot_dribble_sx",
    
    # SHOT
    "jumpshot_dx": "jumpshot_dx", "jumpshot_sx": "jumpshot_sx"
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
    print(f"Searching for event {id}...")
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
        print(f"Shot frame {shot_frame} beyond data length. Resetting to middle.")
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
    """Determines in which frames the player holds the ball"""
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

# ==================== CORE LOGIC ====================

def determine_state_sequence(p_traj, b_traj, speeds, shot_offset, shot_blender_start, shot_blender_end):
    print("Calculating states (Logic v4 - Full Movement)...")
    print(f"   Shot window: {shot_blender_start} -> {shot_blender_end}")
    print(f"   Total frames: {len(p_traj)}, multiplied: {int(len(p_traj) * FRAME_MULTIPLIER)}")
    first_poss, _, _ = analyze_possession(p_traj, b_traj)
    states = []

    for i in range(len(p_traj)):
        current_blender_frame = int(i * FRAME_MULTIPLIER)

        # === SHOT PROTECTION (FORCE OVERRIDE) ===
        # If we are in the time window of the shot, force "SHOT" state
        # Ignoring any speed or possession calculation.
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

        # AFTER THE SHOT 
        if current_blender_frame > shot_blender_end:
            if speed > 0.2 and is_moving_backwards(player_pos, prev_pos, look_target):
                states.append("back_run")
            elif speed > 5.5: states.append("fast_run")
            elif speed > 3.0: states.append("slow_run")
            elif speed > 0.2: states.append("walk")
            else: states.append("idle")
            continue

        #WITHOUT BALL
        if not has_ball:
            if speed > 0.2 and is_moving_backwards(player_pos, prev_pos, look_target):
                states.append("back_run")
            elif speed > 5.5: states.append("fast_run")
            elif speed > 3.0: states.append("slow_run")
            elif speed > 0.2: states.append("walk")
            else: states.append("idle")
            continue
            
        # WITH BALL
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
    
    # DEBUG: State check
    print(f"State distribution:")
    from collections import Counter
    counter = Counter(states)
    for state, count in counter.most_common():
        print(f"  {state}: {count} frames")

    return states

def create_sequential_strips(armature, state_sequence, shot_anim_name, p_traj):
    print("Creating Sequential Timeline (Anti-Sliding Universal v2)...")
    
    # Animation Setup
    if not armature.animation_data:
        armature.animation_data_create()
    
    # Tracks Cleanup
    while armature.animation_data.nla_tracks:
        armature.animation_data.nla_tracks.remove(armature.animation_data.nla_tracks[0])
        
    # Active Action Cleanup
    armature.animation_data.action = None

    main_track = armature.animation_data.nla_tracks.new()
    main_track.name = "Main_Animation_Track"
    
    current_blender_frame = 0
    nba_frame_index = 0
    FRAME_GAP = 10

    grouped_states = groupby(state_sequence)
    
    for state, group in grouped_states:
        # Calculate how many NBA frames this block lasts
        nba_frames_in_group = len(list(group))

        # Calculate duration in Blender
        duration_frames = int(nba_frames_in_group * FRAME_MULTIPLIER)
        
        if duration_frames <= 0: 
            nba_frame_index += nba_frames_in_group
            continue

        # Universal Scaling logic
        scale_factor = 1.0
        
        # If the state has a reference speed, calculate anti-sliding
        if state in SPEED_MAP:
            reference_speed = SPEED_MAP[state]
            
            # 1. Calculate actual distance traveled in this segment
            start_idx = nba_frame_index
            end_idx = min(nba_frame_index + nba_frames_in_group, len(p_traj) - 1)
            
            segment_distance = 0.0
            for k in range(start_idx, end_idx):
                p1 = p_traj[k]
                p2 = p_traj[k+1]
                dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                segment_distance += dist
            
            # Calculate real time in seconds (NBA @ 25 fps)
            duration_seconds = nba_frames_in_group / FPS_JSON
            
            # Calculate Target Speed (Feet/Second required by tracking)
            target_speed = 0.0
            if duration_seconds > 0:
                target_speed = segment_distance / duration_seconds
            
            # Calculate NLA Scale (Ref / Target)
            if target_speed > 0.1:
                raw_scale = reference_speed / target_speed
                
                scale_factor = max(0.5, min(2.0, raw_scale))
                
            else:
                scale_factor = 1.0 # If target speed is almost 0, do not scale (avoids freeze)

        # --- ACTION SELECTION ---
        action_name = ""
        if state == "SHOT":
            action_name = shot_anim_name
        elif state in ANIM_MAP:
            action_name = ANIM_MAP[state]
        else:
            action_name = ANIM_MAP.get("idle", "idle")
            
        if action_name not in bpy.data.actions:
            print(f"Missing Action: {action_name}")
            current_blender_frame += duration_frames
            nba_frame_index += nba_frames_in_group
            continue
            
        action = bpy.data.actions[action_name]

        # Original frame length of the action
        source_duration = max(0.1, action.frame_range[1] - action.frame_range[0])
        
        # --- STRIP CREATION ---
        try:
            strip = main_track.strips.new(
                name=state,
                start=int(current_blender_frame),
                action=action
            )

            # Apply calculated scale
            strip.scale = scale_factor
            
            if state == "SHOT":
                s_conf = SHOT_CONFIGS.get(shot_anim_name, DEFAULT_SHOT_CONFIG)
                strip.action_frame_start = s_conf["crop"]
                strip.action_frame_end = s_conf["end"]
                strip.scale = 1.0
            else:
                strip.action_frame_start = action.frame_range[0]
                strip.action_frame_end = action.frame_range[1]
                
                # Calculate how many repetitions are needed to cover the time duration
                needed_action_frames = duration_frames / scale_factor
                strip.repeat = needed_action_frames / source_duration

            # Set the correct end on the timeline
            strip.frame_end = int(current_blender_frame + duration_frames - FRAME_GAP)

            # Blender Settings
            strip.blend_type = 'REPLACE'
            strip.extrapolation = 'HOLD'
            strip.use_auto_blend = False
            
            current_blender_frame = int(current_blender_frame + duration_frames)

        except Exception as e:
            print(f"Strip error {state}: {e}")

        nba_frame_index += nba_frames_in_group

    print(f"Timeline generated with Anti-Sliding on {len(SPEED_MAP)} states.")

def apply_transforms(obj, trajectory, b_traj, start_frame, first_poss):
    """Applies position and correct rotation with improved interpolation"""
    is_ball = (obj.name == BALL_NAME)
    
    # For the ball, insert keyframes for every Blender frame to reduce floating
    if is_ball:
        for i in range(len(trajectory)):
            frame = start_frame + int(i * FRAME_MULTIPLIER)
            obj.location = convert_coords(*trajectory[i])
            obj.keyframe_insert("location", frame=frame)
            
            # Interpolation: add intermediate frames
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
    
    # For the player
    else:
        for i, pos in enumerate(trajectory):
            frame = int(start_frame + (i * FRAME_MULTIPLIER))
            current_blender_frame = int(i * FRAME_MULTIPLIER)
            
            # Position
            obj.location = convert_coords(*pos)
            obj.keyframe_insert("location", frame=frame)
            
            # Position interpolation
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
            
            pb = convert_coords(*pos)

            # Determine what to look at
            if first_poss is None or i < first_poss:
                # BEFORE possession: look at the ball
                target = convert_coords(*b_traj[i])
                angle_offset = 0
            else:
                # DURING or AFTER possession: look at the basket
                basket = determine_basket_target(pos)
                target = convert_coords(basket[1], basket[0], 10.0)
                angle_offset = math.radians(+90)

            dx = target[0] - pb[0]
            dy = target[1] - pb[1]
            angle = math.atan2(dy, dx) + angle_offset

            obj.rotation_euler.z = angle
            obj.keyframe_insert("rotation_euler", frame=frame)
            
            # Rotation interpolation
            if i < len(trajectory) - 1:
                next_frame = start_frame + int((i + 1) * FRAME_MULTIPLIER)
                frames_between = next_frame - frame
                
                if frames_between > 1:
                    next_pos = trajectory[i + 1]
                    next_pb = convert_coords(*next_pos)
                    
                    if first_poss is None or (i + 1) < first_poss:
                        next_target = convert_coords(*b_traj[i + 1])
                        next_angle_offset = 0
                    else:
                        next_basket = determine_basket_target(next_pos)
                        next_target = convert_coords(next_basket[1], next_basket[0], 10.0)
                        next_angle_offset = math.radians(+90)
                    next_dx = next_target[0] - next_pb[0]
                    next_dy = next_target[1] - next_pb[1]
                    next_angle = math.atan2(next_dy, next_dx) + next_angle_offset
                    
                    # Interpolate angles (handling wrap-around)
                    angle_diff = next_angle - angle
                    if angle_diff > math.pi:
                        angle_diff -= 2 * math.pi
                    elif angle_diff < -math.pi:
                        angle_diff += 2 * math.pi
                    
                    for j in range(1, frames_between):
                        interp_frame = frame + j
                        alpha = j / frames_between
                        interp_angle = angle + angle_diff * alpha
                        
                        obj.rotation_euler.z = interp_angle
                        obj.keyframe_insert("rotation_euler", frame=interp_frame)

def extract_gaps_from_nla_post_process():
    """
    Reads already created strips in NLA Track and exports gap data.
    """
    print("\nSTARTING NLA INSPECTOR (Post-Process)...")
    
    obj = bpy.data.objects.get("Armature")
    if not obj or not obj.animation_data:
        print("Error: No armature or animation data found.")
        return

    # Find the right track
    track = None
    for t in obj.animation_data.nla_tracks:
        if "Main" in t.name:
            track = t
            break
    
    if not track:
        if obj.animation_data.nla_tracks:
            track = obj.animation_data.nla_tracks[0]
        else:
            print("No NLA Track found.")
            return

    # Sort strips by start frame
    strips = sorted(track.strips, key=lambda s: s.frame_start)
    
    found_gaps = []
    
    print(f"Analysis of {len(strips)} strips on track '{track.name}'...")

    for i in range(len(strips) - 1):
        strip_a = strips[i]
        strip_b = strips[i+1]
        
        # Gap duration calculation
        gap_duration = strip_b.frame_start - strip_a.frame_end
        
        # Precise calculation of 'Cut Point'
        duration_timeline_a = strip_a.frame_end - strip_a.frame_start
        cut_frame_end_a = strip_a.action_frame_start + (duration_timeline_a / strip_a.scale)
        
        cut_frame_start_b = strip_b.action_frame_start
        
        if gap_duration > 1.0: 
            gap_info = {
                "index": len(found_gaps), # 0, 1, 2...
                "frame_start_timeline": strip_a.frame_end,
                "frame_end_timeline": strip_b.frame_start,
                "gap_duration": gap_duration,
                "clip_a": {
                    "name": strip_a.name,
                    "action_name": strip_a.action.name if strip_a.action else "Unknown",
                    "scale": strip_a.scale,
                    "cut_frame_end": cut_frame_end_a
                },
                "clip_b": {
                    "name": strip_b.name,
                    "action_name": strip_b.action.name if strip_b.action else "Unknown",
                    "scale": strip_b.scale,
                    "cut_frame_start": cut_frame_start_b
                }
            }
            found_gaps.append(gap_info)
            print(f"   Gap #{len(found_gaps)-1} detected: {strip_a.name} -> {strip_b.name} ({gap_duration:.1f} frames)")

    # JSON saving
    output_path = os.path.join(BASE_PATH, "baby_step/gap_export.json")
    with open(output_path, 'w') as f:
        json.dump(found_gaps, f, indent=4)
        
    print(f"Data saved in: {output_path}")
    print("="*50)
# ==================== MAIN ====================

def main():
    print("="*50)
    print("STARTING SHOT SYNC SCRIPT")
    print("="*50)
    
    try:
        metadata = load_metadata()
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
        
        print(f"Shot: {shot_anim_real_name} ({shot_side})")
        
        # DYNAMIC RIGHT/LEFT CALCULATION
        s_conf = SHOT_CONFIGS.get(shot_anim_real_name, DEFAULT_SHOT_CONFIG)
        
        # Calculate the peak on Blender timeline
        blender_shot_peak = shot_offset * FRAME_MULTIPLIER
        
        # Calculate how many 'useful' frames exist before release (Release - Start)
        frames_before_peak = s_conf["release"] - s_conf["crop"]
        
        # Calculate how many frames exist after release (End - Release)
        frames_after_peak = s_conf["end"] - s_conf["release"]
        
        # Define start and end on global timeline
        shot_blender_start = blender_shot_peak - frames_before_peak
        shot_blender_end = blender_shot_peak + frames_after_peak

        states = determine_state_sequence(p_traj, b_traj, speeds, shot_offset, shot_blender_start, shot_blender_end)
        print(f"States: {list(set(states))}")

        armature = bpy.data.objects[ARMATURE_NAME]
        ball = bpy.data.objects[BALL_NAME]
        
        # Active action cleanup
        if armature.animation_data:
            armature.animation_data.action = None

        create_sequential_strips(armature, states, shot_anim_real_name, p_traj)

        look_target_traj = []
        for p in p_traj:
            b = determine_basket_target(p)
            look_target_traj.append((b[0], b[1], 10.0))

        apply_transforms(armature, p_traj, b_traj, 1, poss_start)
        apply_transforms(ball, b_traj, b_traj, 1, None)
        
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = int(len(p_traj) * FRAME_MULTIPLIER)
        bpy.context.scene.render.fps = FPS_ANIMATION
        # === ADDED EXTRACTOR ===
        extract_gaps_from_nla_post_process()
        
        print("DONE.")
        
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()