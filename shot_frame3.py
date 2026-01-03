import json
import os
import math
import traceback
import os
import argparse

# USER CONFIGURATION
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(BASE_DIR, "nba_tracking_data_tiny.json")
OUTPUT_FILENAME = os.path.join(BASE_DIR, "shot_metadata.json") 
SHOTS_DATA_FILE = os.path.join(BASE_DIR, "shots_data.json")


# --- PHYSICAL CONSTANTS ---
FRAME_RATE_FPS = 25.0
DELTA_TIME = 1.0 / FRAME_RATE_FPS 
MIN_Z_TRIGGER = 10.5 
PUSH_ACCEL_THRESHOLD = 15.0 
MAX_2D_DISTANCE_TO_SHOOTER = 4 

# --- 3-POINT FILTER ---
MIN_3PT_DIST_METERS = 6.5
MIN_3PT_DIST_FEET = MIN_3PT_DIST_METERS * 3.28084 # 22 feet

# --- FIXED HOOP COORDINATES ---
BASKET_LEFT = (5.25, 25.0)
BASKET_RIGHT = (88.75, 25.0)

# HELPER FUNCTIONS
def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def format_clock(seconds):
    if seconds is None: return "00:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def get_player_name_by_id(event_data, target_id):
    # Search among home and visitor players
    for team_key in ['home', 'visitor']:
        for p in event_data.get(team_key, {}).get('players', []):
            if str(p['playerid']) == str(int(target_id)):
                return f"{p['firstname']} {p['lastname']}"
    return "Unknown"

# ANALYSIS LOGIC
def find_shot_release_nearest_teammate(event_data):
    moments = event_data.get('moments', [])
    if len(moments) < 5: return None

    try: 
        # we need shooter_team_id to filter teammates
        if 'primary_info' in event_data:
             shooter_team_id = int(event_data['primary_info']['team_id'])
        else:
             shooter_team_id = int(event_data.get('possession_team_id', 0))
    except: return None
    
    # PHYSICS PRE-CALCULATION FOR ALL FRAMES
    ball_data_history = [] 
    for i in range(len(moments)):
        m = moments[i]
        if 'ball_coordinates' not in m:
            ball_data_history.append({'pos': (0,0,0), 'a_z': 0, 'frame': i, 'valid': False})
            continue

        pos = (m['ball_coordinates']['x'], m['ball_coordinates']['y'], m['ball_coordinates']['z'])
        
        accel_z = 0.0
        if i > 1:
            prev_z = moments[i-1]['ball_coordinates']['z']
            prev_prev_z = moments[i-2]['ball_coordinates']['z']
            v_z = (pos[2] - prev_z) / DELTA_TIME
            v_z_prev = (prev_z - prev_prev_z) / DELTA_TIME
            accel_z = (v_z - v_z_prev) / DELTA_TIME

        ball_data_history.append({'pos': pos, 'a_z': accel_z, 'frame': i, 'valid': True})

    # TEMPORAL SCAN (LOOP)
    i = 0
    while i < len(ball_data_history):
        curr = ball_data_history[i]
        
        # If ball is LOW or invalid data -> go to next frame
        if not curr['valid'] or curr['pos'][2] <= MIN_Z_TRIGGER:
            i += 1
            continue

        print(f"--- TRIGGER ACTIVATED at frame {i} (Z={curr['pos'][2]:.2f}) ---")

        # TRIGGER ACTIVATED: Ball is high (> 10.5 ft)
        push_found = False
        shot_frame_index = -1
        shooter_id = None
        closest_player_pos = (0, 0) # Placeholder
        dist_to_basket = 0.0
        
        # Search backwards from current frame 'i' to the beginning
        for j in range(i, 1, -1):
            b_curr = ball_data_history[j]
            b_prev = ball_data_history[j-1] 
            
            if b_curr['a_z'] > 5.0:
                print(f"DEBUG: Checking frame {j}, Accel_Z: {b_curr['a_z']:.2f}")

            # If we find an acceleration peak (the release)
            if b_curr['a_z'] > PUSH_ACCEL_THRESHOLD:
                moment_data = moments[j-1]
                ball_xy = (b_prev['pos'][0], b_prev['pos'][1])
                print(f"ACCELERATION PEAK found at frame {j}: {b_curr['a_z']:.2f}")
                
                # Find the teammate closest to the ball
                min_dist_player = float('inf')
                temp_closest_pos = None
                temp_closest_id = None

                for p in moment_data['player_coordinates']:
                    if int(p['teamid']) == shooter_team_id:
                        p_pos = (p['x'], p['y'])
                        d = calculate_distance_2d(ball_xy, p_pos)
                        if d < min_dist_player:
                            min_dist_player = d
                            temp_closest_pos = p_pos
                            temp_closest_id = p['playerid']
                
                if temp_closest_id:
                    print(f"Closest player at frame {j}: ID {temp_closest_id} at {min_dist_player:.2f} ft")
                else:
                    print(f"No teammate found near the ball at frame {j}")

                # If the player is plausibly the shooter
                if min_dist_player < MAX_2D_DISTANCE_TO_SHOOTER:
                    closest_player_pos = temp_closest_pos
                    
                    # --- DISTANCE LOGIC MODIFICATION ---
                    # Calculate distance from both baskets
                    dist_left = calculate_distance_2d(closest_player_pos, BASKET_LEFT)
                    dist_right = calculate_distance_2d(closest_player_pos, BASKET_RIGHT)
                    dist_to_basket = min(dist_left, dist_right)
                    
                    shot_frame_index = b_prev['frame']
                    shooter_id = temp_closest_id
                    push_found = True
                    break 
        
        # EVALUATION OF FOUND SHOT
        if push_found:
            print(f"Frame {i} (Trigger) -> Push at frame {shot_frame_index}. Pos: {closest_player_pos}. Dist to nearest rim: {dist_to_basket:.2f} ft")
            
            # 3-POINT DISTANCE CHECK
            if dist_to_basket >= MIN_3PT_DIST_FEET:
                print(f"VALID 3-POINT SHOT! ({dist_to_basket:.2f} ft)")
                return shot_frame_index, shooter_id, closest_player_pos[0], closest_player_pos[1], moments[shot_frame_index]
            else:
                # DISCARD AND ADVANCE
                print(f"DISCARDED: Insufficient distance ({dist_to_basket:.2f} ft). Searching further...")
                
                while i < len(ball_data_history) and ball_data_history[i]['pos'][2] > MIN_Z_TRIGGER:
                    i += 1
                continue 

        i += 1

    return None

# MAIN
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description= "Process NBA tracking data to find the shot frame of a 3-point shot event.")
    parser.add_argument("--game_id", type=str, help="ID of the match (es. 0021500333)")
    parser.add_argument("--event_id", type=str, help="ID of the event (es. 179)")
    
    args = parser.parse_args()
    
    TARGET_GAME_ID = args.game_id
    TARGET_EVENT_ID = args.event_id

    try:
        target_event = None
        print(f"Finding Game ID: {TARGET_GAME_ID}, Event ID: {TARGET_EVENT_ID}")
        print(f"Reading file: {JSON_FILE_PATH}")
        
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                ev = json.loads(line)
                if str(ev.get('gameid')) == TARGET_GAME_ID and str(ev['event_info']['id']) == TARGET_EVENT_ID:
                    target_event = ev
                    break
        
        if target_event:
            event_type = target_event['event_info'].get('type', 'N/A')
            print(f"Event Found! ID: {TARGET_EVENT_ID}, Type: {event_type}")

            result = find_shot_release_nearest_teammate(target_event)
            
            if result:
                frame, pid, shot_x, shot_y, shot_moment = result
                
                primary_pid = target_event.get('primary_info', {}).get('player_id', 0)
                primary_name = get_player_name_by_id(target_event, primary_pid)

                home_team = target_event.get('home', {})
                visitor_team = target_event.get('visitor', {})

                poss_id = target_event.get('possession_team_id')
                if poss_id is None:
                    poss_id = target_event.get('event_info', {}).get('possession_team_id')
                if poss_id is None:
                    poss_id = target_event.get('primary_info', {}).get('team_id')

                output = {
                    "game_id": TARGET_GAME_ID,
                    "game_date": target_event.get('gamedate'),
                    "event_id": TARGET_EVENT_ID,
                    "event_type": event_type,
                    "possession_team_id": poss_id,
                    "primary_player_name": primary_name,
                    "player_id": pid,
                    "shot_frame": frame,
                    "period": shot_moment.get('quarter'),
                    "game_clock": format_clock(shot_moment.get('game_clock')),
                    "shot_clock": shot_moment.get('shot_clock'),
                    "shot_location_x": shot_x,
                    "shot_location_y": shot_y,
                    "teams": {
                        "home": {
                            "name": home_team.get('name'),
                            "team_id": home_team.get('teamid'),
                            "abbreviation": home_team.get('abbreviation')
                        },
                        "visitor": {
                            "name": visitor_team.get('name'),
                            "team_id": visitor_team.get('teamid'),
                            "abbreviation": visitor_team.get('abbreviation')
                        }
                    }
                }
                
                with open(OUTPUT_FILENAME, "w") as f_out: 
                    json.dump(output, f_out, indent=4)
                
                shots_history = []

                if os.path.exists(SHOTS_DATA_FILE):
                    try:
                        with open(SHOTS_DATA_FILE, "r") as f_hist:
                            content = json.load(f_hist)
                            if isinstance(content, list):
                                shots_history = content
                    except:
                        shots_history = []

                # Append new event to list
                shots_history.append(output)

                # Save updated list
                with open(SHOTS_DATA_FILE, "w") as f_hist:
                    json.dump(shots_history, f_hist, indent=4)

                print(f"Saved single file to {OUTPUT_FILENAME}")
                
                print(f"Saved: {primary_name} involved, shot detected for player {pid}")
            else:
                print("No valid 3-point shot found.")
        else:
            print("Event not found.")

    except Exception as e:
        traceback.print_exc()