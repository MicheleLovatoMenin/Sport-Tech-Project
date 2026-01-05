import bpy
import json
import os

# ==================== CONFIGURAZIONE ====================
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
WORK_DIR = os.path.join(BASE_PATH, "baby_step_optimized")

# Input
GAP_JSON_PATH = os.path.join(WORK_DIR, "gap_export.json") 

# Output
TEMP_LABS_DIR = os.path.join(WORK_DIR, "temp_labs")
METADATA_JSON_PATH = os.path.join(WORK_DIR, "lab_metadata.json") # <--- NUOVO FILE

# Parametri
OUTPUT_ACTION_NAME = "Gap_Scenario_To_Fill"
GAP_FRAMES = 10 
MIN_CONTEXT_FRAMES = 40 

# ==================== LOGICA BATCH ====================

def setup_dirs():
    if not os.path.exists(TEMP_LABS_DIR):
        os.makedirs(TEMP_LABS_DIR)

def load_gaps():
    if not os.path.exists(GAP_JSON_PATH):
        raise Exception(f"File JSON non trovato: {GAP_JSON_PATH}")
    with open(GAP_JSON_PATH, 'r') as f:
        return json.load(f)

def clean_scene(obj):
    if not obj.animation_data: return
    obj.animation_data.action = None
    while obj.animation_data.nla_tracks:
        obj.animation_data.nla_tracks.remove(obj.animation_data.nla_tracks[0])

def is_valid_gap(gap):
    """Sanity Check"""
    idx = gap['index']
    start_timeline = gap['frame_start_timeline']
    if start_timeline < 0:
        print(f"⚠️ SKIP Gap #{idx}: Inizia a frame negativo.")
        return False
    
    data_a = gap['clip_a']
    if data_a['cut_frame_end'] <= 0.01: 
        print(f"⚠️ SKIP Gap #{idx}: Durata nulla.")
        return False

    return True

def process_single_gap(gap_data, obj):
    """
    Ritorna un dizionario con i metadati del gap processato (start, end, file)
    """
    gap_idx = gap_data['index']
    clean_scene(obj)
    track = obj.animation_data.nla_tracks.new()
    track.name = f"Lab_Setup_Track_{gap_idx}"

    # === 1. CLIP A ===
    data_a = gap_data['clip_a']
    action_a = bpy.data.actions.get(data_a['action_name'])
    if not action_a: return None
        
    start_frame_timeline = 1
    strip_a = track.strips.new(data_a['name'], start=start_frame_timeline, action=action_a)
    strip_a.scale = 1.0
    strip_a.action_frame_end = data_a['cut_frame_end'] # Taglio esatto dal JSON
    
    # Durata sulla timeline (con scale 1.0)
    duration_a = strip_a.action_frame_end - strip_a.action_frame_start
    strip_a.frame_end = start_frame_timeline + duration_a
    strip_a.extrapolation = 'HOLD'

    # === 2. CLIP B ===
    data_b = gap_data['clip_b']
    action_b = bpy.data.actions.get(data_b['action_name'])
    if not action_b: return None

    # INIZIO GAP (Esattamente dove finisce A)
    gap_start_frame = int(strip_a.frame_end)
    
    # FINE GAP (Dopo 10 frame)
    gap_end_frame = gap_start_frame + GAP_FRAMES
    
    strip_b = track.strips.new(data_b['name'], start=gap_end_frame, action=action_b)
    strip_b.scale = 1.0
    strip_b.action_frame_start = data_b['cut_frame_start']
    strip_b.action_frame_end = action_b.frame_range[1]
    
    # === 3. BAKE & SETUP SCENA ===
    bpy.context.scene.frame_start = int(start_frame_timeline)
    
    duration_b = strip_b.action_frame_end - strip_b.action_frame_start
    safe_margin = min(60, duration_b) 
    total_end_frame = int(strip_b.frame_start + safe_margin)
    
    bpy.context.scene.frame_end = total_end_frame
    bpy.context.scene.render.fps = 120

    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    
    bpy.ops.nla.bake(
        frame_start=int(bpy.context.scene.frame_start),
        frame_end=int(bpy.context.scene.frame_end),
        only_selected=True,
        visual_keying=True,
        clear_constraints=False,
        use_current_action=False,
        bake_types={'POSE'}
    )
    
    if obj.animation_data.action:
        obj.animation_data.action.name = OUTPUT_ACTION_NAME
    
    bpy.ops.object.mode_set(mode='OBJECT')
    track.mute = True
    
    # RITORNA I DATI PREZIOSI PER IL JSON
    return {
        "gap_start": gap_start_frame,
        "gap_end": gap_end_frame,
        "total_start": int(start_frame_timeline),
        "total_end": total_end_frame
    }

def save_lab_file(gap_idx):
    filename = f"lab_gap_{gap_idx:03d}.blend"
    filepath = os.path.join(TEMP_LABS_DIR, filename)
    bpy.ops.wm.save_as_mainfile(filepath=filepath, copy=True, compress=True)
    print(f"💾 Generato: {filename}")
    return filename

def cleanup_after_save(obj):
    clean_scene(obj)
    if OUTPUT_ACTION_NAME in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[OUTPUT_ACTION_NAME])

# ==================== MAIN ====================

def main():
    print("="*50)
    print("🏭 LABORATORY BATCH V4 (METADATA GENERATOR)")
    print("="*50)
    setup_dirs()
    
    metadata_db = {} # Dizionario per raccogliere tutti i dati

    try:
        gaps = load_gaps()
        obj = bpy.data.objects.get("Armature")
        if not obj: return

        if bpy.context.object: bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        for gap in gaps:
            # Skip check
            if not is_valid_gap(gap):
                continue
            
            # Processa e ottieni i dati temporali
            timing_info = process_single_gap(gap, obj)
            
            if timing_info:
                # Salva file fisico
                filename = save_lab_file(gap['index'])
                
                # Registra i metadati associati al nome del file
                metadata_db[filename] = timing_info
                
            cleanup_after_save(obj)

        # SALVATAGGIO JSON METADATA
        with open(METADATA_JSON_PATH, 'w') as f:
            json.dump(metadata_db, f, indent=4)
            
        print("-" * 50)
        print(f"✅ METADATA SALVATI: {METADATA_JSON_PATH}")
        print(f"📂 LABORATORI PRONTI: {len(metadata_db)}")

    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()