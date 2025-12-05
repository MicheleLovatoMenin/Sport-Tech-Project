import bpy
import sys
import os
import json
import math
import numpy as np
import torch
import torch.optim as optim
from tqdm import tqdm
import time
import re

# ==================== CONFIGURAZIONE UTENTE (MODIFICA I PERCORSI) ====================

BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
JSON_DATASET = os.path.join(BASE_PATH, "dataset_3pt.json")
JSON_METADATA = os.path.join(BASE_PATH, "shot_metadata.json")

ARMATURE_NAME = "Armature"
BALL_NAME = "ball"

# Sync
FPS_JSON = 25.0
FPS_ANIMATION = 60
FRAME_MULTIPLIER = FPS_ANIMATION / FPS_JSON 

# GenMM
GEN_PATCH_SIZE = 11
GEN_NUM_STEPS = 5
GEN_NOISE = 10.0

# IK
POSSESSION_DISTANCE = 3.5
MIN_HEIGHT_IK = 1.0
MAX_HEIGHT_IK = 2.5
IK_STEPS = 300
SCALE_JSON_TO_BVH = 1.0

# Rule-Based
JUMPSHOT_RELEASE_FRAME = 150 
SHOT_ANIMATION_TOTAL_FRAMES = 300
WALK_SPEED_THRESHOLD = 2.0
RUN_SPEED_THRESHOLD = 4.0

# ==================== 0. SETUP & IMPORTS ====================

def setup_and_import():
    print("\n🖥️  SETUP ADDON & IMPORTS")
    addon_path = None
    try:
        import GenMM_blender_addon
        addon_path = os.path.dirname(GenMM_blender_addon.__file__)
    except ImportError:
        addons_paths = bpy.utils.script_paths("addons")
        for p in addons_paths:
            cand = os.path.join(p, "GenMM_blender_addon")
            if os.path.exists(cand):
                if p not in sys.path: sys.path.append(p)
                addon_path = cand; break
        if not addon_path:
            curr = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
            if os.path.exists(os.path.join(curr, "GenMM_blender_addon")):
                if curr not in sys.path: sys.path.append(curr)
                addon_path = os.path.join(curr, "GenMM_blender_addon")

    if not addon_path: raise ImportError("❌ Addon GenMM non trovato!")
    
    try:
        global GenMM, PatchCoherentLoss, BlenderMotion, get_bvh_data
        global BVH_file, repr6d2quat, skeleton_confs, ForwardKinematicsJoint
        
        from GenMM_blender_addon.GenMM import GenMM
        from GenMM_blender_addon.nearest_neighbor.losses import PatchCoherentLoss
        from GenMM_blender_addon.dataset.blender_motion import BlenderMotion
        from GenMM_blender_addon import get_bvh_data 
        from GenMM_blender_addon.dataset.bvh.bvh_parser import BVH_file
        from GenMM_blender_addon.utils.transforms import repr6d2quat
        from GenMM_blender_addon.dataset.bvh_motion import skeleton_confs
        from GenMM_blender_addon.utils.kinematics import ForwardKinematicsJoint
        return addon_path
    except ImportError as e:
        print(f"❌ Errore Import: {e}")
        raise e

ADDON_PATH = setup_and_import()

# ==================== 1. SANITIZER (CRUCIAL FIX) ====================

def sanitize_bvh_data(bvh_str):
    """
    Pulisce il BVH generato da Blender rimuovendo i canali di posizione
    dalle ossa non-root (che causano il crash in GenMM).
    Restituisce: (Header Pulito, Dati Puliti Numpy)
    """
    print("🧹 Sanitizing BVH Data structure...")
    
    header_lines = []
    clean_header_str = ""
    original_channel_counts = []
    
    lines = bvh_str.split('\n')
    data_start_idx = 0
    joint_counter = 0
    
    # 1. PARSE & CLEAN HEADER
    for i, line in enumerate(lines):
        if line.strip().startswith("MOTION"):
            data_start_idx = i
            break
            
        if "CHANNELS" in line:
            parts = line.strip().split()
            count = int(parts[1])
            original_channel_counts.append(count)
            
            # Se è il Root (primo joint), mantieni tutto
            if joint_counter == 0:
                header_lines.append(line)
            else:
                # Per gli altri, forza 3 canali se erano 6
                if count == 6:
                    # Presumiamo formato: CHANNELS 6 Xpos Ypos Zpos Xrot Yrot Zrot
                    # Teniamo solo le ultime 3 (rotazioni)
                    new_line = line.replace("CHANNELS 6", "CHANNELS 3")
                    new_line = new_line.replace("Xposition Yposition Zposition ", "")
                    header_lines.append(new_line)
                else:
                    header_lines.append(line)
            joint_counter += 1
        else:
            header_lines.append(line)
            
    clean_header_str = "\n".join(header_lines) + "\n"
    
    # 2. CLEAN DATA
    motion_lines = lines[data_start_idx:]
    # Salta MOTION, Frames, Frame Time
    data_lines = [l for l in motion_lines if l.strip() and not l.strip().isalpha() and ":" not in l]
    
    raw_data = np.array([item.strip().split(' ') for item in data_lines], dtype=np.float32)
    rows, cols = raw_data.shape
    
    # Costruisci maschera colonne da tenere
    keep_indices = []
    cursor = 0
    
    for j_idx, ch_count in enumerate(original_channel_counts):
        if j_idx == 0:
            # Root: tieni tutto
            keep_indices.extend(range(cursor, cursor + ch_count))
        else:
            if ch_count == 6:
                # Scarta primi 3 (Pos), tieni ultimi 3 (Rot)
                keep_indices.extend(range(cursor + 3, cursor + 6))
            else:
                # Tieni tutto (dovrebbe essere 3)
                keep_indices.extend(range(cursor, cursor + ch_count))
        cursor += ch_count
        
    clean_data = raw_data[:, keep_indices]
    
    print(f"   Original Cols: {cols} -> Sanitized Cols: {clean_data.shape[1]}")
    return clean_header_str, clean_data, lines[data_start_idx+1], lines[data_start_idx+2]

# ==================== 2. DATA HELPERS ====================

def convert_coords(nba_x, nba_y, nba_z):
    return (float(nba_y), float(nba_x), float(nba_z))

def calculate_distance_2d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def calculate_distance_3d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

def load_data_from_json(json_dataset, json_metadata):
    print(f"📂 Caricamento Dati JSON...")
    with open(json_metadata, 'r') as f: meta = json.load(f)
    game_id, event_id = str(meta['game_id']), str(meta.get('event_info', {}).get('id', meta.get('event_id')))
    player_id = str(meta['player_id'])
    shot_frame = meta.get('shot_frame', 0)

    found_event = None
    with open(json_dataset, 'r', encoding='utf-8') as f:
        try:
            full = json.load(f)
            if isinstance(full, dict): full = [full]
            for ev in full:
                if str(ev.get('gameid')) == game_id and str(ev.get('event_info', {}).get('id', ev.get('eventid'))) == event_id:
                    found_event = ev; break
        except:
            f.seek(0)
            for line in f:
                try:
                    ev = json.loads(line.strip().rstrip(','))
                    if str(ev.get('gameid')) == game_id and str(ev.get('event_info', {}).get('id', ev.get('eventid'))) == event_id:
                        found_event = ev; break
                except: continue
    
    if not found_event: raise ValueError("Evento non trovato!")
    moments = found_event['moments']
    p_traj, b_traj = [], []
    for m in moments:
        b = m['ball_coordinates']
        b_traj.append(convert_coords(b['x'], b['y'], b['z']))
        p_coords = next((convert_coords(p['x'], p['y'], p['z']) for p in m['player_coordinates'] if str(p['playerid']) == player_id), None)
        p_traj.append(p_coords if p_coords else (p_traj[-1] if p_traj else (0,0,0)))
    return np.array(p_traj), np.array(b_traj), shot_frame

# ==================== 3. RULE BASED LOGIC ====================

def calculate_speeds(traj):
    speeds = [0.0]
    for i in range(1, len(traj)): speeds.append(calculate_distance_2d(traj[i-1], traj[i]))
    return speeds

def determine_side(player_pos, ball_pos):
    return "dx" if ball_pos[1] >= player_pos[1] else "sx"

def analyze_possession(p_traj, b_traj):
    for i, (p, b) in enumerate(zip(p_traj, b_traj)):
        if calculate_distance_3d(p, b) < POSSESSION_DISTANCE: return i
    return 0

def determine_state_sequence(p_traj, b_traj, speeds, poss_start, shot_offset, shot_blender_start, shot_blender_end):
    states = []
    for i in range(len(p_traj)):
        frame = int(i * FRAME_MULTIPLIER)
        if frame > shot_blender_end or i < poss_start: states.append("celly_ice_vein"); continue
        speed = speeds[i]
        side = determine_side(p_traj[i], b_traj[i])
        if (i - poss_start) < 15: states.append(f"static_catch_{side}" if speed < WALK_SPEED_THRESHOLD else f"run_catch_{side}")
        else:
            if speed < WALK_SPEED_THRESHOLD: states.append(f"dribble_walk_{side}")
            elif speed < RUN_SPEED_THRESHOLD: states.append(f"dribble_walk_{side}")
            else: states.append(f"dribble_run_{side}")
    return states

def setup_nla_tracks(armature, unique_anims, shot_anim_name, shot_blender_start_frame):
    if not armature.animation_data: armature.animation_data_create()
    for track in armature.animation_data.nla_tracks: armature.animation_data.nla_tracks.remove(track)
    strips_dict = {}
    for anim_name in unique_anims:
        if anim_name == shot_anim_name or anim_name not in bpy.data.actions: continue
        track = armature.animation_data.nla_tracks.new(); track.name = f"Track_{anim_name}"
        act = bpy.data.actions[anim_name]
        strip = track.strips.new(anim_name, start=1, action=act)
        strip.repeat = 500; strip.blend_type = 'REPLACE'; strip.use_auto_blend = True; strip.influence = 0.0
        strips_dict[anim_name] = strip
    if shot_anim_name in bpy.data.actions:
        track = armature.animation_data.nla_tracks.new(); track.name = "Track_Shot"
        act = bpy.data.actions[shot_anim_name]
        strip = track.strips.new(shot_anim_name, start=int(shot_blender_start_frame), action=act)
        strip.blend_type = 'REPLACE'; strip.influence = 0.0; strip.blend_in = 20; strip.blend_out = 20
        strips_dict['SHOT'] = strip
    bpy.context.view_layer.update()
    return strips_dict

def apply_animation_logic(strips, state_sequence, shot_blender_start, shot_blender_end, start_frame=1):
    current_base = None; is_shooting = False
    for i, state in enumerate(state_sequence):
        frame = start_frame + int(i * FRAME_MULTIPLIER)
        should_shoot = (shot_blender_start <= frame <= shot_blender_end)
        if 'SHOT' in strips:
            strip = strips['SHOT']
            if should_shoot != is_shooting:
                strip.influence = 1.0 if should_shoot else 0.0
                try: strip.keyframe_insert("influence", frame=frame)
                except: pass
                is_shooting = should_shoot
        if is_shooting:
            if current_base:
                for n, s in strips.items():
                    if n!='SHOT': s.influence=0.0; 
                    try: s.keyframe_insert("influence", frame=frame); except: pass
                current_base = None
        else:
            if state != current_base:
                for n, s in strips.items():
                    if n!='SHOT':
                        s.influence = 1.0 if n==state else 0.0
                        try: s.keyframe_insert("influence", frame=frame); except: pass
                current_base = state

def apply_transforms(obj, trajectory, b_traj, start_frame=1):
    is_ball = (obj.name == BALL_NAME)
    for i, pos in enumerate(trajectory):
        frame = start_frame + int(i * FRAME_MULTIPLIER)
        obj.location = pos
        obj.keyframe_insert("location", frame=frame)
        if not is_ball:
            pb=pos; bb=b_traj[i]
            obj.rotation_euler.z = math.atan2(bb[1]-pb[1], bb[0]-pb[0])
            obj.keyframe_insert("rotation_euler", frame=frame)

# ==================== 4. BAKE & GENMM ====================

def bake_nla_to_action(obj, end_frame):
    print("🔥 Baking Animazione NLA...")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.nla.bake(frame_start=1, frame_end=end_frame, only_selected=False, visual_keying=True, 
                     clear_constraints=False, use_current_action=False, bake_types={'POSE'})
    if obj.animation_data.action:
        obj.animation_data.action.name = "Baked_For_GenMM"
        for track in obj.animation_data.nla_tracks: track.mute = True
    else: raise RuntimeError("Bake fallito!")

def run_genmm_direct(context, total_frames, output_path):
    print(f"🚀 Running GenMM (Direct Call)... Target: {output_path}")
    bvh_str = get_bvh_data(context, frame_start=1, frame_end=total_frames)
    
    # --- SANITIZE DATA ---
    header_clean, motion_data_np, frames_line, time_line = sanitize_bvh_data(bvh_str)
    
    # GenMM Pipeline
    motion_wrapper = [BlenderMotion(motion_data_np, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis='Y_UP', padding_last=False)]
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = GenMM(device=device, silent=False) 
    criteria = PatchCoherentLoss(patch_size=GEN_PATCH_SIZE, alpha=0.01, loop=False, cache=True)
    
    syn_tensor = model.run(
        target=motion_wrapper, criteria=criteria, num_frames=str(total_frames), 
        num_steps=GEN_NUM_STEPS, noise_sigma=GEN_NOISE, patch_size=GEN_PATCH_SIZE,
        coarse_ratio=f"0.2x_nframes", pyr_factor=0.75
    )
    
    result_np = motion_wrapper[0].parse(syn_tensor)
    
    print(f"💾 Salvataggio BVH intermedio...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(header_clean)
        f.write("MOTION\n")
        f.write(f"Frames: {result_np.shape[0]}\n")
        f.write(time_line + "\n")
        for frame_row in result_np:
            line = " ".join(f"{x:.6f}" for x in frame_row)
            f.write(line + "\n")
    return output_path

# ==================== 5. IK POST-PROCESSING ====================

class InverseKinematicsJoint2_Masked:
    def __init__(self, rotations, positions, offset, parents, target_positions, target_ids, constr_mask, lambda_rec_rot=1., lambda_rec_pos=1., use_velo=False):
        self.use_velo = use_velo
        self.rotations_ori = rotations.detach().clone(); self.rotations = rotations.detach().clone(); self.rotations.requires_grad_(True)
        self.position_ori = positions.detach().clone(); self.position = positions.detach().clone()
        if self.use_velo: self.position[1:] = self.position[1:] - self.position[:-1]
        self.position.requires_grad_(True)
        self.parents = parents; self.offset = offset
        self.target_positions = target_positions.detach().clone(); self.constr_mask = constr_mask.detach().clone(); self.cid = target_ids
        self.lambda_rec_rot = lambda_rec_rot; self.lambda_rec_pos = lambda_rec_pos
        self.optimizer = optim.Adam([self.position, self.rotations], lr=1e-3, betas=(0.9, 0.999))
        self.fk = ForwardKinematicsJoint(parents, offset); self.glb = None

    def step(self):
        self.optimizer.zero_grad()
        curr_position = torch.cumsum(self.position, dim=0) if self.use_velo else self.position
        glb = self.fk.forward(self.rotations, curr_position)
        glb_targets = glb[:, self.cid]
        diff_sq = (glb_targets - self.target_positions) ** 2
        weighted_diff = diff_sq * self.constr_mask
        constrain_loss = weighted_diff.sum() / (self.constr_mask.sum() + 1e-6)
        rec_loss_rot = torch.nn.functional.mse_loss(self.rotations, self.rotations_ori)
        rec_loss_pos = torch.nn.functional.mse_loss(self.position, self.position_ori)
        loss = constrain_loss + rec_loss_rot * self.lambda_rec_rot + rec_loss_pos * self.lambda_rec_pos
        loss.backward(); self.optimizer.step(); self.glb = glb
        return loss.item()

    def get_position(self):
        return torch.cumsum(self.position.detach(), dim=0) if self.use_velo else self.position.detach()

def sync_and_build_constraints(bvh_file, p_traj_25, b_traj_25, device):
    T_BVH = bvh_file.anim.rotations.shape[0]
    bvh_fps = 1.0 / bvh_file.frametime
    x_src = np.arange(len(p_traj_25)); x_tgt = np.arange(T_BVH) / (bvh_fps / 25.0); x_tgt = np.clip(x_tgt, 0, len(p_traj_25)-1)
    p_sync = np.zeros((T_BVH, 3)); b_sync = np.zeros((T_BVH, 3))
    for i in range(3):
        p_sync[:, i] = np.interp(x_tgt, x_src, np.array(p_traj_25)[:, i])
        b_sync[:, i] = np.interp(x_tgt, x_src, np.array(b_traj_25)[:, i])
    p_sync *= SCALE_JSON_TO_BVH; b_sync *= SCALE_JSON_TO_BVH
    names = bvh_file.skeleton.names
    try: idx_hand = names.index("RightHand"); idx_hips = names.index("Hips")
    except: idx_hips = 0; idx_hand = [i for i, n in enumerate(names) if 'RightHand' in n or 'Hand.R' in n][0]
    target_ids = [idx_hips, idx_hand]
    targets = torch.zeros((T_BVH, 2, 3), device=device)
    mask = torch.zeros((T_BVH, 2, 3), device=device)
    cnt = 0
    for t in range(T_BVH):
        if (calculate_distance_3d(p_sync[t], b_sync[t]) < POSSESSION_DISTANCE) and (MIN_HEIGHT_IK <= b_sync[t][2] <= MAX_HEIGHT_IK):
            cnt += 1
            targets[t, 1] = torch.tensor(b_sync[t], device=device)
            mask[t, 1] = 1.0
            targets[t, 0, :2] = torch.tensor(p_sync[t][:2], device=device)
            mask[t, 0, 0] = 1.0; mask[t, 0, 1] = 1.0
    print(f"🔗 Vincoli IK applicati su {cnt}/{T_BVH} frame.")
    return targets, target_ids, mask

# ==================== MAIN ====================
def main():
    print("\n🏀 STARTING FULL PIPELINE V8 (Sanitized) 🏀")
    armature = bpy.data.objects.get(ARMATURE_NAME)
    ball = bpy.data.objects.get(BALL_NAME)
    if not armature or not ball: return print("❌ Error Objects")
    bpy.context.view_layer.objects.active = armature; armature.select_set(True)
    
    p_traj, b_traj, shot_frame_25 = load_data_from_json(JSON_DATASET, JSON_METADATA)
    speeds = calculate_speeds(p_traj); poss_start = analyze_possession(p_traj, b_traj)
    shot_idx = min(shot_frame_25, len(p_traj)-1)
    shot_side = determine_side(p_traj[shot_idx], b_traj[shot_idx])
    shot_anim_name = f"jumpshot_{shot_side}" if speeds[shot_idx] > WALK_SPEED_THRESHOLD else f"stationary_shot_{shot_side}"
    blender_shot_peak = shot_frame_25 * FRAME_MULTIPLIER
    shot_blender_start = blender_shot_peak - JUMPSHOT_RELEASE_FRAME
    shot_blender_end = shot_blender_start + SHOT_ANIMATION_TOTAL_FRAMES
    
    states = determine_state_sequence(p_traj, b_traj, speeds, poss_start, shot_frame_25, shot_blender_start, shot_blender_end)
    unique_base = list(set(states))
    
    print("🏗️  Rule-Based NLA Setup...")
    strips = setup_nla_tracks(armature, unique_base, shot_anim_name, shot_blender_start)
    apply_animation_logic(strips, states, shot_blender_start, shot_blender_end)
    apply_transforms(armature, p_traj, b_traj)
    apply_transforms(ball, b_traj, [convert_coords(*p) for p in b_traj])
    
    total_frames = int(len(p_traj) * FRAME_MULTIPLIER)
    bpy.context.scene.frame_start = 1; bpy.context.scene.frame_end = total_frames; bpy.context.scene.render.fps = 60
    
    bake_nla_to_action(armature, total_frames)
    
    out_dir = os.path.join(ADDON_PATH, "output")
    syn_bvh_path = os.path.join(out_dir, "pipeline_syn.bvh")
    
    run_genmm_direct(bpy.context, total_frames, syn_bvh_path)
    
    print("🔧 Running IK Constraint...")
    bvh = BVH_file(syn_bvh_path, skeleton_confs['mixamo'], auto_scale=False, requires_contact=False)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    targets, t_ids, mask = sync_and_build_constraints(bvh, p_traj, b_traj, device)
    rot = bvh.get_rotation(repr='repr6d').to(device); pos = bvh.get_position().to(device)
    offsets = bvh.skeleton.offsets.to(device); parents = bvh.skeleton.parent
    ik = InverseKinematicsJoint2_Masked(rot, pos, offsets, parents, targets, t_ids, mask, lambda_rec_rot=0.05, lambda_rec_pos=0.01, use_velo=True)
    
    for _ in tqdm(range(IK_STEPS)): ik.step()
    
    out_path_final = syn_bvh_path.replace(".bvh", "_final.bvh")
    bvh.writer.write(out_path_final, repr6d2quat(ik.rotations.detach()), ik.get_position(), names=bvh.skeleton.names, repr='quat')
    
    print("📥 Importazione Finale...")
    armature.hide_viewport = True
    bpy.ops.import_anim.bvh(filepath=out_path_final, axis_up='Y', axis_forward='-Z')
    print("✨ ALL DONE ✨")

if __name__ == "__main__":
    main()