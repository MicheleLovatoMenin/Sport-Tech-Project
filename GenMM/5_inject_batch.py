import bpy
import json
import os
import mathutils

# ==================== CONFIGURAZIONE ====================
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
WORK_DIR = os.path.join(BASE_PATH, "baby_step_optimized")

LIBRARY_FOLDER = os.path.join(WORK_DIR, "gap_libraries")
GAP_JSON_PATH = os.path.join(WORK_DIR, "gap_export.json")

ARMATURE_NAME = "Armature"

# ==================== UTILS DATI ====================

def load_all_gaps():
    if not os.path.exists(GAP_JSON_PATH):
        raise Exception(f"JSON mancante: {GAP_JSON_PATH}")
    with open(GAP_JSON_PATH, 'r') as f:
        return json.load(f)

def load_gap_action(gap_idx):
    gap_id = f"gap_{gap_idx:03d}"
    filename = f"{gap_id}_filled.blend"
    blend_path = os.path.join(LIBRARY_FOLDER, filename)
    
    if not os.path.exists(blend_path):
        print(f"   ⚠️ File libreria mancante: {filename} (Skip)")
        return None
    
    expected_action_name = f"Action_{gap_id}"
    
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if expected_action_name in data_from.actions:
            data_to.actions = [expected_action_name]
        else:
            if data_from.actions:
                data_to.actions = [data_from.actions[0]]
    
    if not data_to.actions:
        print(f"   ❌ Nessuna azione nel file {filename}")
        return None
    
    loaded_action = data_to.actions[0]
    action_copy = loaded_action.copy()
    action_copy.name = f"INJECTED_{gap_id}"
    bpy.data.actions.remove(loaded_action)
    
    return action_copy

# ==================== NLA & CORREZIONI ====================

def ensure_trajectory_in_nla(armature):
    """Sposta il movimento originale (tracking) nell'NLA"""
    print("📦 SETUP NLA BASE...")
    if not armature.animation_data: armature.animation_data_create()
    
    active_action = armature.animation_data.action
    if active_action:
        traj_track = None
        for t in armature.animation_data.nla_tracks:
            if "Trajectory" in t.name:
                traj_track = t
                break
        
        if not traj_track:
            traj_track = armature.animation_data.nla_tracks.new()
            traj_track.name = "Trajectory_Track"

        if not traj_track.strips:
            strip = traj_track.strips.new(
                name="JSON_Movement_Base",
                start=int(active_action.frame_range[0]),
                action=active_action
            )
            strip.blend_type = 'COMBINE' 
            print("   ✅ Azione base spostata in NLA Strip.")
        
        armature.animation_data.action = None

def create_correction_layer(armature):
    """Crea UNA VOLTA SOLA il layer che corregge l'offset della Rest Pose."""
    print("🔧 SETUP CORREZIONE OFFSET...")
    pbone = armature.pose.bones.get("mixamorig:Hips") or armature.pose.bones.get("Hips")
    if not pbone: 
        print("   ❌ Bone Hips non trovato.")
        return mathutils.Vector((0,0,0))

    rest_local = pbone.bone.matrix_local.translation
    correction_vec = mathutils.Vector((-rest_local.x, 0.0, -rest_local.z))
    
    corr_track = None
    for t in armature.animation_data.nla_tracks:
        if "Correction" in t.name:
            corr_track = t
            break
            
    if not corr_track:
        action_name = "Global_Offset_Correction"
        if action_name in bpy.data.actions: bpy.data.actions.remove(bpy.data.actions[action_name])
        
        corr_action = bpy.data.actions.new(name=action_name)
        data_path = pbone.path_from_id("location")
        corr_action.fcurves.new(data_path, index=0).keyframe_points.insert(0, correction_vec.x) # X
        corr_action.fcurves.new(data_path, index=2).keyframe_points.insert(0, correction_vec.z) # Z
        
        corr_track = armature.animation_data.nla_tracks.new()
        corr_track.name = "Correction_Layer"
        
        strip = corr_track.strips.new(name="Rest_Pose_Fix", start=1, action=corr_action)
        strip.blend_type = 'COMBINE'
        strip.extrapolation = 'HOLD'
        strip.frame_end = 50000 
        
        print(f"   ✅ Layer Correzione Creato: {correction_vec}")
    else:
        print(f"   ℹ️ Layer Correzione esistente. Vector: {correction_vec}")
        
    return correction_vec

# ==================== CALCOLO & INIEZIONE (WARPING) ====================

def align_and_blend_height(armature, action, gap_start, gap_end, correction_vec):
    pbone = armature.pose.bones.get("mixamorig:Hips") or armature.pose.bones.get("Hips")
    if not pbone: return action
    
    # --- 1. ANCORA INIZIALE (PASSATO) ---
    # Leggiamo dove si trova il bacino al frame PRIMA del gap
    bpy.context.scene.frame_set(gap_start - 1)
    bpy.context.view_layer.update()
    anchor_start_loc = pbone.location.copy()
    
    # --- 2. ANCORA FINALE (FUTURO) ---
    # Leggiamo dove si trova il bacino al frame DOPO il gap
    # Nota: Poiché stiamo lavorando in NLA, frame_set leggerà la traccia sottostante (Trajectory)
    # che contiene il movimento originale (es. T-Pose o posa successiva)
    bpy.context.scene.frame_set(gap_end + 1) # +1 per sicurezza, o gap_end
    bpy.context.view_layer.update()
    anchor_end_loc = pbone.location.copy()

    # --- 3. DATI AZIONE AI ---
    # Valutiamo l'altezza interna dell'azione AI all'inizio e alla fine
    # (Attenzione: action frame 0 è l'inizio, action frame max è la fine)
    ai_duration = action.frame_range[1] - action.frame_range[0]
    
    ai_start_vals = [0.0, 0.0, 0.0]
    ai_end_vals = [0.0, 0.0, 0.0]

    for fc in action.fcurves:
        if "location" in fc.data_path and ("Hips" in fc.data_path or "root" in fc.data_path):
            ai_start_vals[fc.array_index] = fc.evaluate(0)
            ai_end_vals[fc.array_index] = fc.evaluate(ai_duration)

    # --- 4. CALCOLO OFFSET NECESSARI ---
    # X e Z: Usiamo solo l'ancora iniziale (Logica classica "In-Place")
    # Y: Usiamo il BLENDING tra Start ed End
    
    delta_x_start = (anchor_start_loc.x - ai_start_vals[0]) - correction_vec.x
    delta_z_start = (anchor_start_loc.z - ai_start_vals[2]) - correction_vec.z
    
    # Offset Y INIZIALE (Quanto devo correggere per matchare il passato?)
    offset_y_start = anchor_start_loc.y - ai_start_vals[1]
    
    # Offset Y FINALE (Quanto devo correggere per matchare il futuro?)
    offset_y_end = anchor_end_loc.y - ai_end_vals[1]
    
    # DEBUG
    print(f"      🔗 Blending Y: Start Offset={offset_y_start:.3f} -> End Offset={offset_y_end:.3f}")

    # --- 5. APPLICAZIONE (WARPING) ---
    for fc in action.fcurves:
        if "location" in fc.data_path and ("Hips" in fc.data_path or "root" in fc.data_path):
            idx = fc.array_index
            
            if idx == 0: # X - Costante su Start
                for kp in fc.keyframe_points: kp.co.y += delta_x_start
            
            elif idx == 2: # Z - Costante su Start
                for kp in fc.keyframe_points: kp.co.y += delta_z_start
            
            elif idx == 1: # Y - WARPING LINEARE
                for kp in fc.keyframe_points:
                    # Calcolo fattore di blend (t) da 0.0 a 1.0 basato sul tempo
                    current_frame = kp.co.x
                    t = current_frame / ai_duration if ai_duration > 0 else 0
                    t = max(0.0, min(1.0, t)) # Clamp tra 0 e 1
                    
                    # Interpolazione Lineare (Lerp) tra offset iniziale e finale
                    current_offset = ((1 - t) * offset_y_start) + (t * offset_y_end)
                    
                    # Applico l'offset variabile
                    kp.co.y += current_offset
                
    return action

def inject_single_gap(armature, main_track, gap_data, correction_vec):
    idx = gap_data['index']
    action = load_gap_action(idx)
    if not action: return False 
    
    gap_start = int(gap_data['frame_start_timeline'])
    gap_end = int(gap_data['frame_end_timeline'])
    
    # USIAMO LA NUOVA FUNZIONE DI BLENDING
    fixed_action = align_and_blend_height(armature, action, gap_start, gap_end, correction_vec)
    
    try:
        strip = main_track.strips.new(
            name=f"GAP_FILL_{idx:03d}",
            start=gap_start,
            action=fixed_action
        )
        strip.blend_type = 'REPLACE'
        strip.use_auto_blend = False
        strip.extrapolation = 'HOLD' 
        
        strip.action_frame_start = 0
        strip.action_frame_end = fixed_action.frame_range[1]
        strip.frame_end = gap_end
        
        print(f"   ✅ Inserito Gap #{idx} [{gap_start}-{gap_end}]")
        return True
        
    except Exception as e:
        print(f"   ❌ Errore inserimento strip Gap #{idx}: {e}")
        return False

# ==================== MAIN ====================

def main():
    print("="*60)
    print("🚀 ASSEMBLER BATCH V5 (Y-MOTION WARPING)")
    print("="*60)
    
    try:
        armature = bpy.data.objects.get(ARMATURE_NAME)
        if not armature: raise Exception("Armatura non trovata.")
        if bpy.context.object: bpy.ops.object.mode_set(mode='OBJECT')
        
        ensure_trajectory_in_nla(armature)
        corr_vec = create_correction_layer(armature)
        
        main_track = None
        for t in armature.animation_data.nla_tracks:
            if "Main_Animation_Track" in t.name or "Main" in t.name:
                main_track = t
                break
        
        if not main_track:
            main_track = armature.animation_data.nla_tracks.new()
            main_track.name = "Main_Animation_Track"
        
        gaps = load_all_gaps()
        gaps.sort(key=lambda x: x['frame_start_timeline'])
        
        success_count = 0
        for gap in gaps:
            if gap['frame_start_timeline'] < 0: continue
            
            ok = inject_single_gap(armature, main_track, gap, corr_vec)
            if ok:
                success_count += 1
                
            bpy.context.view_layer.update()
            
        print("-" * 60)
        print(f"🎉 COMPLETATO. Gaps Iniettati: {success_count} / {len(gaps)}")
        armature.animation_data.action = None
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()