import bpy
import os
import json
import math

# USER CONFIGURATION
JSON_FILE_PATH = r"C:\Users\DISI\Documents\SportTech Students\Basket_Virtualisation\Sport-Tech-Project"
DATASET = "nba_tracking_data_tiny.json"
JSON_FILE_PATH = os.path.join(JSON_FILE_PATH, DATASET)

TARGET_GAME_ID = "0021500333"
TARGET_EVENT_ID = "202"  

# ######################################################################
# ---  DATA LOADING AND ANIMATION ---
# ######################################################################

def convert_coords(nba_x, nba_y, nba_z):
    blender_x = nba_y
    blender_y = nba_x
    blender_z = nba_z
    return (blender_x, blender_y, blender_z)

def cleanup_previous_animation():
    print("Cleaning up previous animation...")

    obj_names_to_clear = ["ball"] + [f"player_{i}" for i in range(10)]
    for obj_name in obj_names_to_clear:
        if obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            obj.animation_data_clear()
    print("Cleanup completed.")

try:
    cleanup_previous_animation()

    # Load JSON Data
    print(f"Loading data from {JSON_FILE_PATH}...")
    print(f"Searching for GAME_ID: {TARGET_GAME_ID} and EVENT_ID: {TARGET_EVENT_ID}")

    event = None
    target_game_str = str(TARGET_GAME_ID).strip()
    target_event_str = str(TARGET_EVENT_ID).strip()
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                current_event = json.loads(line)
                game_id_from_file = str(current_event.get('gameid', '')).strip()

                event_id_from_file = ""
                if 'event_info' in current_event and \
                    isinstance(current_event['event_info'], dict):
                        event_id_from_file = str(current_event['event_info'].get('id', '')).strip()

                # DOUBLE CHECK: Game AND Event
                if game_id_from_file == target_game_str and event_id_from_file == target_event_str:
                    event = current_event
                    print(f"FOUND! Game {target_game_str}, Event {target_event_str} at line {i+1}")
                    break

            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    if event is None:
        raise Exception(f"ERROR: Event '{target_event_str}' for game '{target_game_str}' was not found.")

    # Scene Settings
    bpy.context.scene.render.fps = 25

    # Player Mapping
    print("Mapping Player IDs -> 3D Objects...")
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
                print(f"[HOME - Red] PlayerID {player_id_str} -> {obj_name}")
        elif team_id == visitor_team_id:
            if visitor_obj_names:
                obj_name = visitor_obj_names.pop(0) 
                player_id_to_object_name_map[player_id_str] = obj_name
                print(f"[VISITOR - Blue] PlayerID {player_id_str} -> {obj_name}")

    print(f"Mapping completed. {len(player_id_to_object_name_map)} players mapped.")
    
    print("Setting rotation mode 'XYZ' (Euler) for players...")
    for player_id_str, obj_name in player_id_to_object_name_map.items():
        if obj_name in bpy.data.objects:
            player_obj = bpy.data.objects[obj_name]
            player_obj.rotation_mode = 'XYZ'
        else:
            print(f"WARNING: Object {obj_name} not found during Euler setting.")
    print("Rotation mode set.")

    # Animation Loop (look at ball only)
    print("Starting keyframe creation...")
    start_game_clock = event['moments'][0]['game_clock']
    ball_obj = bpy.data.objects["ball"]
    num_moments = len(event['moments'])

    debug_printed = False 

    for i, moment in enumerate(event['moments']):
        current_game_clock = moment['game_clock']
        frame_num = i
        bpy.context.scene.frame_set(frame_num)

        if i % 50 == 0: 
            print(f"Processing moment {i}/{num_moments} (Frame: {frame_num})")

        # Animate the Ball
        ball_coords_nba = moment['ball_coordinates']
        ball_pos_2d = (ball_coords_nba['x'], ball_coords_nba['y'])
        ball_obj.location = convert_coords(ball_coords_nba['x'], ball_coords_nba['y'], ball_coords_nba['z'])
        ball_obj.keyframe_insert(data_path="location", frame=frame_num)

        # Animate Players
        for p_data in moment['player_coordinates']:
            player_id_str = str(p_data['playerid']) 
            obj_name = player_id_to_object_name_map.get(player_id_str)

            if obj_name:
                player_obj = bpy.data.objects[obj_name]

                nba_x = p_data['x']
                nba_y = p_data['y']
                nba_z = p_data['z']

                if i == 0 and not debug_printed:
                    print(f"-> DEBUG (Frame 0): {obj_name} (ID: {player_id_str}) -> DATA READ: (x={nba_x:.1f}, y={nba_y:.1f}, z={nba_z:.1f})")

                player_obj.location = convert_coords(nba_x, nba_y, nba_z)
                player_obj.keyframe_insert(data_path="location", frame=frame_num)

                # rotation logic to look at the ball
                current_pos_2d = (nba_x, nba_y)
                
                # Calculate vector from player to ball
                delta_to_ball_x = ball_pos_2d[0] - current_pos_2d[0]
                delta_to_ball_y = ball_pos_2d[1] - current_pos_2d[1]
                
                # Calculate angle to look at the ball
                angle_z = math.atan2(delta_to_ball_x, delta_to_ball_y) + (math.pi / 2)
                
                # Apply rotation
                player_obj.rotation_euler.z = angle_z
                player_obj.keyframe_insert(data_path="rotation_euler", frame=frame_num)                
                # end rotation logic

        if i == 0:
            debug_printed = True

    # Set Scene Duration
    start_frame = 0
    end_frame = len(event['moments']) - 1
    bpy.context.scene.frame_start = start_frame
    bpy.context.scene.frame_end = end_frame

    print(f"Keyframe creation completed.")
    print(f"Animation set from frame {start_frame} to {end_frame}.")

except Exception as e:
    print(f"CRITICAL ERROR during Phase 3: {e}")
    import traceback
    traceback.print_exc()

print("\n--- ANIMATION SCRIPT COMPLETED ---")
print("Animation loaded in Blender.")