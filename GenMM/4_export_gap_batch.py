import bpy
import os
import json

# ==================== CONFIGURATION ====================
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
WORK_DIR = os.path.join(BASE_PATH, "GenMM")
LABS_DIR = os.path.join(WORK_DIR, "temp_labs")
LIBRARY_DIR = os.path.join(WORK_DIR, "gap_libraries")
METADATA_PATH = os.path.join(WORK_DIR, "lab_metadata.json")

RIG_OBJECT_NAME = "Armature"

# ==================== UTILS ====================

def setup_dirs():
    if not os.path.exists(LIBRARY_DIR):
        os.makedirs(LIBRARY_DIR)
        print(f"Library folder created: {LIBRARY_DIR}")

def load_metadata():
    if not os.path.exists(METADATA_PATH):
        raise Exception("Metadata not found. Run Script 2.")
    with open(METADATA_PATH, 'r') as f:
        return json.load(f)

def clean_scene():
    """Removes everything to work clean"""
    bpy.ops.wm.read_homefile(use_empty=True)

def process_single_gap(gap_key, metadata):
    filled_filename = gap_key.replace(".blend", "_filled.blend")
    filled_path = os.path.join(LABS_DIR, filled_filename)
    
    if not os.path.exists(filled_path):
        print(f"Filled File missing: {filled_filename} (Skip)")
        return False

    gap_id = gap_key.replace("lab_", "").replace(".blend", "")
    output_filename = f"{gap_id}_filled.blend"
    output_path = os.path.join(LIBRARY_DIR, output_filename)

    print(f"\nPROCESSING: {gap_id}")
    print(f"   Input: {filled_filename}")

    
    target_action = None
    temp_obj = None

    with bpy.data.libraries.load(filled_path, link=False) as (data_from, data_to):
        if RIG_OBJECT_NAME in data_from.objects:
            data_to.objects = [RIG_OBJECT_NAME]
        else:
            print(f"   Object '{RIG_OBJECT_NAME}' not found in file.")
            return False
            
    # we have the object loaded in bpy.data.objects, but not in the scene
    if data_to.objects:
        temp_obj = data_to.objects[0]
        if temp_obj.animation_data and temp_obj.animation_data.action:
            target_action = temp_obj.animation_data.action
            print(f"   Action Detected on Armature: '{target_action.name}'")
        else:
            print("   The Armature in the file has no active action!")
            # fallback: try searching for 'synsized Retarget' or similar if you want
            return False
    
    if not target_action:
        return False

    # Rename for cleanup
    target_action.name = f"Action_{gap_id}"
    
    # Hybrid Logic application
    GAP_START_FRAME = metadata['gap_start']
    GAP_END_FRAME = metadata['gap_end']
    
    print(f"   Processing Frames: {GAP_START_FRAME} -> {GAP_END_FRAME}")

    # Selective Normalization
    root_curves = [fc for fc in target_action.fcurves 
                   if ('Hips' in fc.data_path or 'root' in fc.data_path) and 'location' in fc.data_path]
    
    for fc in root_curves:
        axis_index = fc.array_index 
        
        if axis_index == 1: 
            pass
        else:
            start_val = fc.evaluate(GAP_START_FRAME)
            # Remove initial offset to center the action
            if abs(start_val) > 0.0001:
                for kp in fc.keyframe_points:
                    kp.co.y -= start_val

    # Crop (Frame Cut)

    for fcurve in target_action.fcurves:
        for i in range(len(fcurve.keyframe_points) - 1, -1, -1):
            kp = fcurve.keyframe_points[i]
            frame = kp.co.x
            if frame < (GAP_START_FRAME - 0.1) or frame > (GAP_END_FRAME + 0.1):
                fcurve.keyframe_points.remove(kp)
    
    # Time Shift
    offset_frame = GAP_START_FRAME
    for fc in target_action.fcurves:
        for kp in fc.keyframe_points:
            kp.co.x -= offset_frame
    
    # library save
    try:
        bpy.data.libraries.write(output_path, {target_action})
        print(f"   SAVED: {output_filename}")
        
        bpy.data.actions.remove(target_action)
        bpy.data.objects.remove(temp_obj)
        return True
        
    except Exception as e:
        print(f"   Save error: {e}")
        return False

# ==================== MAIN ====================

def main():
    print("="*50)
    print("BATCH EXPORTER (AUTO-DETECT ACTION)")
    print("="*50)
    
    setup_dirs()
    # clean_scene() # Optional, if launched from pure CLI
    
    try:
        metadata = load_metadata()
        count = 0
        for gap_key, info in metadata.items():
            # Running partial clean inside loop for safety
            if process_single_gap(gap_key, info):
                count += 1
                
        print("-" * 50)
        print(f"COMPLETED. Libraries created: {count}/{len(metadata)}")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()