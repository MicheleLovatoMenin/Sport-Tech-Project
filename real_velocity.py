import bpy
import mathutils

# ==================== CONFIGURATION ====================
ARMATURE_NAME = "Armature"
BONE_LEFT = "mixamorig:LeftFoot"
BONE_RIGHT = "mixamorig:RightFoot"

# UPDATED ANIMATION LIST
ACTIONS_TO_ANALYZE = [
    {"name": "walk",            "direction": "FORWARD"},
    {"name": "slow-run",        "direction": "FORWARD"},
    {"name": "fast_run",        "direction": "FORWARD"},
    {"name": "dribble_walk_dx", "direction": "FORWARD"},
    {"name": "dribble_walk_sx", "direction": "FORWARD"},
    {"name": "dribble_run_dx",  "direction": "FORWARD"},
    {"name": "dribble_run_sx",  "direction": "FORWARD"},
    {"name": "run_catch_dx",    "direction": "FORWARD"},
    {"name": "run_catch_sx",    "direction": "FORWARD"} 
]

FPS = 120

# ==================== CALCULATION LOGIC ====================

def get_bone_speed(obj, action_name, bone_names, direction_mode="FORWARD"):
    """
    Calculates the average foot speed during the stance phase.
    """
    if action_name not in bpy.data.actions:
        print(f"WARNING: Action '{action_name}' not found in the .blend file. Skipping.")
        return 0.0
    
    action = bpy.data.actions[action_name]

    prev_action = obj.animation_data.action
    obj.animation_data.action = action
    
    speeds = []
    
    start_frame = int(action.frame_range[0])
    end_frame = int(action.frame_range[1])
    
    # If the animation is too short, avoid errors
    if end_frame - start_frame < 2:
        return 0.0

    print(f"--- Analysis: {action_name} ({direction_mode}) ---")
    
    for f in range(start_frame, end_frame):
        bpy.context.scene.frame_set(f)
        current_speeds_frame = []
        
        for b_name in bone_names:
            if b_name not in obj.pose.bones:
                continue
                
            pbone = obj.pose.bones[b_name]

            pos_curr = obj.matrix_world @ pbone.matrix.translation
            y_curr = pos_curr.y

            bpy.context.scene.frame_set(f - 1)
            pos_prev = obj.matrix_world @ pbone.matrix.translation
            y_prev = pos_prev.y

            bpy.context.scene.frame_set(f)
            

            delta_y = y_curr - y_prev
            
            valid_sample = False
            speed_sample = 0.0
            
            # FILTER: Consider only when the foot "pushes back" against the ground
            if direction_mode == "FORWARD":
                if delta_y < -0.005: # Foot moves backward (-Y)
                    valid_sample = True
                    speed_sample = abs(delta_y) * FPS
            
            elif direction_mode == "BACKWARD":
                if delta_y > 0.005: # Foot moves forward (+Y)
                    valid_sample = True
                    speed_sample = abs(delta_y) * FPS
            
            if valid_sample:
                current_speeds_frame.append(speed_sample)

        # If at least one foot was grounded, record the speed
        if current_speeds_frame:
            speeds.append(max(current_speeds_frame))

    # Restore original action
    if prev_action:
        obj.animation_data.action = prev_action
    else:
        obj.animation_data.action = None
    
    # Calculate Average
    if len(speeds) > 0:
        avg_speed = sum(speeds) / len(speeds)
        return avg_speed
    else:
        return 0.0

# ==================== MAIN ====================

def main():
    obj = bpy.data.objects.get(ARMATURE_NAME)
    if not obj:
        print(f"ERROR: Object '{ARMATURE_NAME}' not found.")
        return

    print("="*60)
    print("MULTIPLE SPEED CALIBRATION (M/S)")
    print("="*60)

    results = {}

    for item in ACTIONS_TO_ANALYZE:
        speed = get_bone_speed(
            obj, 
            item["name"], 
            [BONE_LEFT, BONE_RIGHT], 
            item["direction"]
        )
        
        if speed > 0:
            results[item["name"]] = speed
            print(f"-> '{item['name']}': \t{speed:.4f} m/s")
        else:
            print(f"Warning '{item['name']}': \t0.0000 m/s (Stopped, lateral, or not found)")


    for name, spd in results.items():
        clean_name = name.upper().replace(" ", "_").replace("-", "_") + "_SPEED"
        print(f"{clean_name} = {spd:.4f}")

if __name__ == "__main__":
    main()