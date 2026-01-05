import bpy
import numpy as np
import torch
import torch.nn.functional as F
import sys
import os
import json

# ==================== CONFIGURAZIONE ====================
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
WORK_DIR = os.path.join(BASE_PATH, "baby_step_optimized")
METADATA_JSON_PATH = os.path.join(WORK_DIR, "lab_metadata.json") # <--- Fonte della verità

# Opzioni
DELETE_GENMM_SKELETON = True

# ==================== IMPORT GENMM ====================
try:
    from GenMM import GenMM
    from nearest_neighbor.losses import PatchCoherentLoss
    from dataset.blender_motion import BlenderMotion
    from GenMM_blender_addon import get_bvh_data, load 
except ImportError:
    try: from __init__ import get_bvh_data, load
    except: pass

# ==================== HOTFIX GENMM ====================
try:
    def constrained_match_and_blend(synthesized, targets, criteria, n_steps, pbar, ext=None):
        losses = []
        for _i in range(n_steps):
            synthesized, loss = criteria(synthesized, targets, ext=ext, return_blended_results=True)
            if ext is not None and 'fix_mask' in ext and 'fix_value' in ext:
                current_len = synthesized.shape[-1]
                mask_res = F.interpolate(ext['fix_mask'], size=current_len, mode='nearest')
                gt_res = F.interpolate(ext['fix_value'], size=current_len, mode='linear')
                synthesized = synthesized * mask_res + gt_res * (1 - mask_res)
            losses.append(loss.item())
            pbar.step()
        return synthesized, losses

    GenMM.match_and_blend = staticmethod(constrained_match_and_blend)
    print("✅ HOTFIX GenMM applicato.")
except Exception as e:
    print(f"❌ ERRORE HOTFIX: {e}")

# ==================== LETTURA METADATI ====================

def get_frames_from_metadata():
    """
    Legge il file lab_metadata.json e restituisce i frame corretti
    per il file .blend attualmente aperto.
    """
    filepath = bpy.context.blend_data.filepath
    if not filepath:
        raise Exception("Il file deve essere salvato su disco per essere riconosciuto.")
    
    filename = os.path.basename(filepath)
    
    if not os.path.exists(METADATA_JSON_PATH):
        raise Exception(f"Metadata file non trovato: {METADATA_JSON_PATH}. Esegui prima lo Script 2!")
        
    with open(METADATA_JSON_PATH, 'r') as f:
        db = json.load(f)
        
    if filename not in db:
        raise Exception(f"Il file '{filename}' non è presente nel database dei metadati.")
        
    info = db[filename]
    print(f"📂 FILE RICONOSCIUTO: {filename}")
    print(f"   Gap: {info['gap_start']} -> {info['gap_end']}")
    print(f"   Total: {info['total_start']} -> {info['total_end']}")
    
    return info['gap_start'], info['gap_end'], info['total_start'], info['total_end']

# ==================== UTILS ====================

def get_hips_bone_name(armature_obj):
    for b in armature_obj.pose.bones:
        name_lower = b.name.lower()
        if "hips" in name_lower or "root" in name_lower or "pelvis" in name_lower:
            return b.name
    return "mixamorig:Hips"

def genera_mapping_dinamico(obj_source, obj_target):
    mapping = {}
    for bone_tgt in obj_target.pose.bones:
        tgt_name = bone_tgt.name
        core_name = tgt_name.split(':')[-1]
        for bone_src in obj_source.pose.bones:
            src_name = bone_src.name
            if src_name == tgt_name or src_name.lower().endswith(core_name.lower()) or src_name.lower().endswith(":" + core_name.lower()):
                mapping[src_name] = tgt_name
                break
    return mapping

def overwrite_hips_location_with_source(obj_target, bone_target_name, obj_source, bone_source_name, start_f, end_f):
    if not obj_target.animation_data or not obj_target.animation_data.action: return
    action = obj_target.animation_data.action
    path_loc = f'pose.bones["{bone_target_name}"].location'
    fc_x = action.fcurves.find(path_loc, index=0) or action.fcurves.new(path_loc, index=0)
    fc_y = action.fcurves.find(path_loc, index=1) or action.fcurves.new(path_loc, index=1)
    fc_z = action.fcurves.find(path_loc, index=2) or action.fcurves.new(path_loc, index=2)
    scene = bpy.context.scene
    range_frames = range(int(start_f), int(end_f) + 1)
    pbone_tgt = obj_target.pose.bones.get(bone_target_name)
    target_obj_inv = obj_target.matrix_world.inverted()
    bone_rest_inv = pbone_tgt.bone.matrix_local.inverted()
    
    for f in range_frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        pbone_src = obj_source.pose.bones.get(bone_source_name)
        if not pbone_src: continue
        src_world_pos = obj_source.matrix_world @ pbone_src.head
        pos_obj_space = target_obj_inv @ src_world_pos
        final_local_pos = bone_rest_inv @ pos_obj_space
        fc_x.keyframe_points.insert(f, final_local_pos.x, options={'FAST'})
        fc_y.keyframe_points.insert(f, final_local_pos.y, options={'FAST'})
        fc_z.keyframe_points.insert(f, final_local_pos.z, options={'FAST'})
    action.fcurves.update()

def get_3d_view_override(context):
    for window in context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return {'window': window, 'screen': screen, 'area': area, 'region': region, 'workspace': window.workspace, 'scene': context.scene, 'view_layer': context.view_layer, 'layer_collection': context.view_layer.layer_collection}
    return None

def esegui_retargeting_rokoko_avanzato(obj_source, obj_target):
    print(f"🔄 Avvio Retargeting: {obj_source.name} -> {obj_target.name}")
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.update()
    temp_map = genera_mapping_dinamico(obj_source, obj_target)
    scn = bpy.context.scene
    scn.rsl_retargeting_armature_source = obj_source
    scn.rsl_retargeting_armature_target = obj_target
    scn.rsl_retargeting_auto_scaling = True 
    scn.rsl_retargeting_use_pose = 'REST' 
    scn.rsl_retargeting_bone_list.clear()
    for src_bone, trg_bone in temp_map.items():
        item = scn.rsl_retargeting_bone_list.add()
        item.bone_name_source = src_bone
        item.bone_name_target = trg_bone
        item.is_custom = True
    bpy.context.view_layer.objects.active = obj_target
    try:
        bpy.ops.rsl.retarget_animation()
        return True
    except Exception as e:
        print(f"❌ Errore Rokoko: {e}")
        return False

# ==================== MAIN ====================

def run_processor():
    obj_originale = bpy.context.active_object
    if not obj_originale or obj_originale.type != 'ARMATURE':
        obj_originale = bpy.data.objects.get("Armature")
        if not obj_originale:
            print("❌ Nessuna armatura trovata.")
            return

    # --- 1. LETTURA FRAMES DA JSON ---
    try:
        GAP_START, GAP_END, TOTAL_START, TOTAL_END = get_frames_from_metadata()
    except Exception as e:
        print(f"❌ Errore Metadati: {e}")
        return

    nome_originale = obj_originale.name
    target_hip_name = get_hips_bone_name(obj_originale)
    ctx_override_dict = get_3d_view_override(bpy.context)
    if not ctx_override_dict: return

    # --- 2. PREPARAZIONE DATI ---
    print(f"📖 Lettura BVH ({TOTAL_START}-{TOTAL_END})...")
    bvh_str = get_bvh_data(bpy.context, frame_start=TOTAL_START, frame_end=TOTAL_END)
    lines = bvh_str.split('\n')
    try: motion_idx = lines.index('MOTION') + 3
    except ValueError: return
    motion_data_vals = []
    for line in lines[motion_idx:]:
        if line.strip():
            try: motion_data_vals.append([float(x) for x in line.split()])
            except: pass
    motion_np_full = np.array(motion_data_vals, dtype=np.float32)

    total_frames_data = motion_np_full.shape[0]
    
    # Indici relativi array numpy
    idx_gap_start = max(0, GAP_START - TOTAL_START)
    idx_gap_end = min(total_frames_data, GAP_END - TOTAL_START)
    
    print(f"📊 GenMM Gap Index: {idx_gap_start} -> {idx_gap_end} (su {total_frames_data} frames)")

    # GenMM Setup
    UP_AXIS = 'Y_UP'
    dataset_full = BlenderMotion(motion_np_full, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False)
    motion_pre_gap = motion_np_full[:idx_gap_start] 
    motion_post_gap = motion_np_full[idx_gap_end:]
    
    targets_list = []
    if len(motion_pre_gap) > 5: targets_list.append(BlenderMotion(motion_pre_gap, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False))
    if len(motion_post_gap) > 5: targets_list.append(BlenderMotion(motion_post_gap, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False))
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = GenMM(device=device, silent=False)
    
    # --- FIX CRITICO KERNEL SIZE ---
    # Usiamo patch_size=5 invece di 11 per accomodare clip corte nei livelli bassi della piramide
    criteria = PatchCoherentLoss(patch_size=5, alpha=0.05, loop=False, cache=True)
    
    gt_tensor = dataset_full.motion_data.data.to(device)
    mask_tensor = torch.zeros_like(gt_tensor)
    
    # Maschera
    mask_tensor[..., idx_gap_start:idx_gap_end] = 1.0
    ext_constraints = {'fix_mask': mask_tensor, 'fix_value': gt_tensor}
    
    # --- 3. RUN GENERATION ---
    print("🚀 Running GenMM...")
    try:
        syn_tensor = model.run(
            target=targets_list, 
            criteria=criteria, 
            num_frames=str(total_frames_data), 
            num_steps=10, 
            noise_sigma=0.5, 
            patch_size=5, # Anche qui 5 per coerenza
            coarse_ratio="0.2x_nframes", 
            pyr_factor=0.75, 
            ext=ext_constraints
        )
    except Exception as e: print(f"❌ Run GenMM Failed: {e}"); return

    # --- 4. IMPORT & RETARGET ---
    print("\n💾 Import Result...")
    syn_parsed = dataset_full.parse(syn_tensor)
    header_str = "\n".join(lines[:motion_idx]) + "\n"
    data_str = ""
    for frame in syn_parsed: data_str += " ".join(map(str, frame)) + "\n"
    full_bvh_content = header_str + data_str
    bvh_lines = full_bvh_content.split('\n')
    
    with bpy.context.temp_override(**ctx_override_dict):
        if bpy.ops.object.mode_set.poll(): bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        
        load(bpy.context, bvh_lines, target='ARMATURE', global_matrix=obj_originale.matrix_world, report=print) 
        
        obj_generato = bpy.context.active_object
        if not obj_generato:
            for obj in bpy.context.selected_objects:
                if obj.type == 'ARMATURE' and obj != obj_originale:
                    obj_generato = obj; break
        if not obj_generato: return
        obj_generato.name = "Result_InBetween_NEW"
        
        # Rokoko
        obj_originale_scene = bpy.data.objects.get(nome_originale)
        if obj_originale_scene:
            bpy.context.view_layer.objects.active = obj_originale_scene
            obj_originale_scene.select_set(True)
            obj_generato.select_set(False) 
            
            success = esegui_retargeting_rokoko_avanzato(obj_source=obj_generato, obj_target=obj_originale_scene)
            
            if success:
                print("🧵 Overwriting Hips Location...")
                source_hip_name = get_hips_bone_name(obj_generato)
                overwrite_hips_location_with_source(obj_target=obj_originale_scene, bone_target_name=target_hip_name, obj_source=obj_generato, bone_source_name=source_hip_name, start_f=TOTAL_START, end_f=TOTAL_END)
                print("✅ Done.")
                
                if DELETE_GENMM_SKELETON:
                    bpy.data.objects.remove(obj_generato, do_unlink=True)
            else:
                print("⚠️ Retargeting failed.")

    # --- 5. SAVE ---
    filepath = bpy.data.filepath
    if filepath:
        new_filepath = filepath.replace(".blend", "_filled.blend")
        bpy.ops.wm.save_as_mainfile(filepath=new_filepath, copy=True, compress=True)
        print(f"🎉 SAVED: {os.path.basename(new_filepath)}")

if __name__ == "__main__":
    run_processor()