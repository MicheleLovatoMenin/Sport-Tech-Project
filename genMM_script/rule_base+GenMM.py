import bpy
import json
import math
import numpy as np
import torch
import torch.nn.functional as F
import os
import sys

# ==================== CONFIGURAZIONE UTENTE ====================
# Se il file è salvato, usa il percorso relativo
if bpy.data.is_saved:
    # Ottieni la cartella dove si trova il file .blend (es. .../ambient_idle)
    blend_dir = os.path.dirname(bpy.data.filepath)
    # SALIAMO DI UN LIVELLO per andare alla cartella principale del progetto
    BASE_PATH = os.path.dirname(blend_dir) 
else:
    # PERCORSO DI FALLBACK (Modifica se necessario)
    BASE_PATH = r"C:\Users\DISI\Documents\SportTech Students\Basket_Virtualisation\Sport-Tech-Project"

print(f"📂 Percorso base rilevato: {BASE_PATH}")

METADATA_JSON = os.path.join(BASE_PATH, "shot_metadata.json")
DATASET_JSON = os.path.join(BASE_PATH, "dataset_3pt.json")

# Nomi Oggetti Blender
ARMATURE_NAME = "Armature"
BALL_NAME = "ball"

# Parametri Temporali
FPS_JSON = 25
# FPS_BLENDER sarà calcolato dinamicamente dalla scena
GAP_WINDOW_JSON = 5        # +/- 5 frame JSON (Totale 10 frame di transizione)
GENMM_FPS_SIM = 30         # FPS simulati per la generazione (standard GenMM)
UP_AXIS = 'Y_UP'           # Assicurati corrisponda al tuo rig

# Soglie per la Logica Rule-Based (per decidere gli stati)
POSSESSION_DISTANCE = 2.5  
WALK_SPEED_THRESHOLD = 2.0 
RUN_SPEED_THRESHOLD = 4.0  

# =================================================================================
# 🛠️ SISTEMA DI IMPORT E HOTFIX GENMM
# =================================================================================

try:
    from GenMM import GenMM
    from nearest_neighbor.losses import PatchCoherentLoss
    from dataset.blender_motion import BlenderMotion
except ImportError:
    print("⚠️ ERRORE: Librerie GenMM non trovate. Assicurati che l'addon sia nel sys.path.")

# --- HOTFIX 1: MotionData Init ---
try:
    import GenMM_blender_addon.dataset.motion as motion_module
    def fixed_init(self, data, repr='quat', use_velo=True, keep_up_pos=True, up_axis='Y', padding_last=False, contact_id=None):
        self.data = data 
        self.repr = repr
        self.use_velo = use_velo
        self.keep_up_pos = keep_up_pos
        self.up_axis = up_axis
        self.padding_last = padding_last
        self.contact_id = contact_id
        self.begin_pos = None
        if self.repr == 'quat': self.n_rot = 4
        elif self.repr == 'repr6d': self.n_rot = 6
        elif self.repr == 'euler': self.n_rot = 3
        
        if self.padding_last:
            self.n_pad = self.data.shape[1] - 3 
            paddings = torch.zeros_like(self.data[:, :self.n_pad])
            self.data = torch.cat((self.data, paddings), dim=1)
        else: self.n_pad = 0
        
        if self.contact_id is not None: self.n_contact = len(contact_id)
        else: self.n_contact = 0
        
        if self.keep_up_pos:
            if self.up_axis == 'X_UP': self.velo_mask = [-2, -1]
            elif self.up_axis == 'Y_UP': self.velo_mask = [-3, -1]
            else: self.velo_mask = [-3, -2]
        else: self.velo_mask = [-3, -2, -1]
        
        if self.use_velo: self.data = self.to_velocity(self.data)

    motion_module.MotionData.__init__ = fixed_init
    print("✅ Hotfix MotionData applicato.")
except Exception as e:
    print(f"⚠️ Impossibile applicare Hotfix MotionData: {e}")

# --- HOTFIX 2: Constraints Logic ---
try:
    import GenMM_blender_addon.GenMM as genmm_module

    @staticmethod
    @torch.no_grad()
    def constrained_match_and_blend(synthesized, targets, criteria, n_steps, pbar, ext=None):
        losses = []
        for _i in range(n_steps):
            synthesized, loss = criteria(synthesized, targets, ext=ext, return_blended_results=True)
            if ext is not None and 'fix_mask' in ext and 'fix_value' in ext:
                current_len = synthesized.shape[-1]
                mask_res = F.interpolate(ext['fix_mask'], size=current_len, mode='nearest')
                gt_res = F.interpolate(ext['fix_value'], size=current_len, mode='linear')
                synthesized = synthesized * (1 - mask_res) + gt_res * mask_res
            losses.append(loss.item())
            pbar.step()
        return synthesized, losses

    genmm_module.GenMM.match_and_blend = constrained_match_and_blend
    print("✅ Hotfix Constraints applicato.")
except Exception as e:
    print(f"⚠️ Impossibile applicare Hotfix Constraints: {e}")

# ==================== FUNZIONI LOGICA RULE-BASED (PORTING) ====================

def convert_coords_nba_to_blender(nba_x, nba_y):
    # NBA: X=width, Y=length. Blender: X=width, Y=depth.
    return (nba_y, nba_x, 0.0)

def calculate_distance_3d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

def calculate_distance_2d(pos1, pos2):
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def load_json_data():
    """Carica Metadata e Finestra dell'evento dal Dataset"""
    print(f"📂 Caricamento JSON...")
    
    # 1. Metadata
    with open(METADATA_JSON, 'r') as f:
        metadata = json.load(f)
    
    # 2. Dataset Big
    event = None
    with open(DATASET_JSON, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            if isinstance(data, dict): data = [data]
            for ev in data:
                if str(ev.get('gameid')) == str(metadata['game_id']) and str(ev.get('event_info', {}).get('id')) == str(metadata['event_id']):
                    event = ev
                    break
        except:
            f.seek(0)
            for line in f:
                try:
                    ev = json.loads(line.strip().rstrip(','))
                    if str(ev.get('gameid')) == str(metadata['game_id']) and str(ev.get('event_info', {}).get('id')) == str(metadata['event_id']):
                        event = ev
                        break
                except: continue
    
    if not event: raise Exception("Evento non trovato nel dataset.")

    # 3. Estrazione Traiettorie
    moments = event['moments']
    shot_frame = metadata['shot_frame']
    
    # Finestra di sicurezza attorno al tiro
    start_idx = max(0, shot_frame - 100) # Prendiamo abbastanza contesto prima
    end_idx = min(len(moments), shot_frame + 50)
    
    window_moments = moments[start_idx:end_idx]
    
    p_traj, b_traj = [], []
    for m in window_moments:
        b = m['ball_coordinates']
        # Convertiamo subito in coordinate Blender per coerenza
        b_traj.append(convert_coords_nba_to_blender(b['x'], b['y'])) 
        
        found = False
        for p in m['player_coordinates']:
            if str(p['playerid']) == str(metadata['player_id']):
                p_traj.append(convert_coords_nba_to_blender(p['x'], p['y']))
                found = True
                break
        if not found:
            p_traj.append(p_traj[-1] if p_traj else (0,0,0))
            
    return p_traj, b_traj, (shot_frame - start_idx)

def determine_states_from_data(p_traj, b_traj, shot_idx_relative, frame_mult):
    """Calcola la sequenza di stati (Idle, Dribble, ecc.) analizzando le traiettorie"""
    print("🧠 Analisi Rule-Based degli stati...")
    
    states = []
    first_poss = None
    
    # Calcolo velocità
    speeds = [0.0]
    for i in range(1, len(p_traj)):
        dist = calculate_distance_2d(p_traj[i-1], p_traj[i])
        speeds.append(dist)
        
    # Analisi possesso (semplificata 2D per robustezza)
    for i in range(len(p_traj)):
        dist_ball = calculate_distance_2d(p_traj[i], b_traj[i])
        if dist_ball < POSSESSION_DISTANCE:
            if first_poss is None: first_poss = i
    
    # Generazione stati frame per frame
    for i in range(len(p_traj)):
        
        # Dopo il tiro -> Idle (o follow through, ma per ora idle)
        if i > shot_idx_relative:
            states.append("idle")
            continue
            
        # Prima del possesso -> Idle
        if first_poss is None or i < first_poss:
            states.append("idle")
            continue
            
        # Durante il possesso
        speed = speeds[i]
        
        # Lato palla (destra o sinistra del corpo) - In Blender X è laterale
        # Se palla.x > player.x è a destra (o viceversa a seconda dell'orientamento, verificalo)
        side = "dx" if b_traj[i][0] >= p_traj[i][0] else "sx"
        
        frames_since_poss = i - first_poss
        
        if frames_since_poss < 15: # Catch
            state = f"static_catch_{side}" if speed < WALK_SPEED_THRESHOLD else f"run_catch_{side}"
        else: # Dribble
            if speed < WALK_SPEED_THRESHOLD: state = f"dribble_walk_{side}" # O idle dribble
            elif speed < RUN_SPEED_THRESHOLD: state = f"dribble_walk_{side}"
            else: state = f"dribble_run_{side}"
        
        states.append(state)
        
    return states

# ==================== FUNZIONI GENMM UTILITIES ====================

def get_full_motion_data(obj, start_frame, end_frame):
    try:
        from GenMM_blender_addon import get_bvh_data
        bvh_str = get_bvh_data(bpy.context, frame_start=start_frame, frame_end=end_frame, root_transform_only=False)
        lines = bvh_str.split('\n')
        motion_idx = lines.index('MOTION') + 3
        motion_vals = []
        for line in lines[motion_idx:]:
            if line.strip():
                try: motion_vals.append([float(x) for x in line.split()])
                except: pass
        return np.array(motion_vals, dtype=np.float32)
    except Exception as e:
        print(f"❌ Errore estrazione dati motion: {e}")
        return None

def get_style_targets(full_motion, gap_start_idx, gap_end_idx, window=60):
    start_a = max(0, gap_start_idx - window)
    clip_a_data = full_motion[start_a:gap_start_idx]
    end_b = min(len(full_motion), gap_end_idx + window)
    clip_b_data = full_motion[gap_end_idx:end_b]
    
    targets = []
    if len(clip_a_data) > 5:
        targets.append(BlenderMotion(clip_a_data, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False))
    if len(clip_b_data) > 5:
        targets.append(BlenderMotion(clip_b_data, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False))
    return targets

def build_constraints(dataset_ref, full_motion, gap_start_idx, gap_end_idx, p_traj_segment, device):
    slice_data = full_motion[max(0, gap_start_idx-1):min(len(full_motion), gap_end_idx+2)]
    temp_dataset = BlenderMotion(slice_data, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False)
    target_tensor = temp_dataset.motion_data.data.to(device)
    seq_len = target_tensor.shape[-1]
    mask_tensor = torch.zeros_like(target_tensor)
    
    # Hard constraints su start/end
    mask_tensor[..., 0] = 1.0
    mask_tensor[..., -1] = 1.0
    
    # Soft constraints traiettoria (JSON)
    # Convertiamo la traiettoria p_traj_segment (coordinate 3d) in velocità relative root
    # Nota: Questa è una semplificazione. Per precisione assoluta serve il mapping esatto canali root.
    # GenMM root channels per Y_UP solitamente sono X e Z (profondità).
    
    root_channels = temp_dataset.motion_data.velo_mask # Canali velocità root
    
    if len(p_traj_segment) > 1:
        # Converti lista python in numpy
        traj_np = np.array(p_traj_segment) # Già in formato blender (x, y, z)
        
        # Calcolo velocità dai punti traiettoria
        velocities = traj_np[1:] - traj_np[:-1]
        
        # Interpolazione per matchare i frame GenMM
        if len(velocities) != seq_len:
            v_tensor = torch.tensor(velocities, dtype=torch.float32).permute(1,0).unsqueeze(0) # [1, 3, T]
            v_resized = F.interpolate(v_tensor, size=seq_len, mode='linear')
            velocities_match = v_resized[0].permute(1,0).cpu().numpy()
        else:
            velocities_match = velocities
            
        # Applica constraint
        # root_channels[0] -> X, root_channels[1] -> Z (Y è up)
        for t in range(1, seq_len - 1):
            # Velocity X
            target_tensor[0, root_channels[0], t] = float(velocities_match[t, 0]) 
            # Velocity Z (depth) -> in blender coords era la Y del JSON
            target_tensor[0, root_channels[-1], t] = float(velocities_match[t, 1])
            
            mask_tensor[0, root_channels[0], t] = 0.5 # Soft influence
            mask_tensor[0, root_channels[-1], t] = 0.5

    return {'fix_mask': mask_tensor, 'fix_value': target_tensor}

# ==================== MAIN ====================

def run_smart_gap_filling():
    print("="*60)
    print("🚀 AVVIO SMART GAP FILLING IBRIDO (JSON RULE-BASED + GENMM)")
    print("="*60)
    
    # 1. Setup Armatura
    obj = bpy.data.objects.get(ARMATURE_NAME)
    if not obj:
        print(f"❌ Oggetto {ARMATURE_NAME} non trovato.")
        return
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # 2. Parametri Scena
    scene = bpy.context.scene
    fps_blender = scene.render.fps / scene.render.fps_base
    frame_mult = fps_blender / FPS_JSON
    print(f"⚙️ Parametri: Blender {fps_blender:.2f}fps | JSON {FPS_JSON}fps | Mult {frame_mult:.2f}x")

    # 3. Caricamento Dati JSON e Calcolo Stati
    try:
        p_traj, b_traj, shot_offset = load_json_data()
        print(f"📊 Traiettorie caricate: {len(p_traj)} punti.")
        
        # CALCOLO STATI (La parte Rule Based)
        states = determine_states_from_data(p_traj, b_traj, shot_offset, frame_mult)
        
        # Identificazione Switch
        switch_points_json = []
        for i in range(1, len(states)):
            if states[i] != states[i-1]:
                switch_points_json.append(i)
                print(f"   📍 Switch {states[i-1]} -> {states[i]} al frame JSON {i}")
                
        if not switch_points_json:
            print("⚠️ Nessun cambio di stato rilevato. Esco.")
            return

    except Exception as e:
        print(f"❌ Errore elaborazione dati JSON: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. Lettura Motion da Blender
    full_motion_np = get_full_motion_data(obj, scene.frame_start, scene.frame_end)
    if full_motion_np is None: return

    # 5. Setup GenMM
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = GenMM(device=device, silent=True)
    criteria = PatchCoherentLoss(patch_size=11, alpha=0.05, loop=False, cache=True)
    
    if not obj.animation_data: obj.animation_data_create()
    track_name = "GenMM_Transitions"
    for track in obj.animation_data.nla_tracks:
        if track.name == track_name: obj.animation_data.nla_tracks.remove(track)
    trans_track = obj.animation_data.nla_tracks.new()
    trans_track.name = track_name

    # 6. Generazione Gap
    for switch_idx in switch_points_json:
        gap_start_json = switch_idx - GAP_WINDOW_JSON
        gap_end_json = switch_idx + GAP_WINDOW_JSON
        
        idx_start_data = int(gap_start_json * frame_mult)
        idx_end_data = int(gap_end_json * frame_mult)
        
        if idx_start_data < 0 or idx_end_data >= len(full_motion_np):
            print(f"⚠️ Gap {switch_idx} fuori range dati Blender ({idx_end_data}/{len(full_motion_np)}). Salto.")
            continue
            
        print(f"🔄 Generazione Gap @ JSON {switch_idx} (Blender {idx_start_data}-{idx_end_data})...")
        
        stride = int(fps_blender / GENMM_FPS_SIM)
        if stride < 1: stride = 1
        
        motion_strided = full_motion_np[::stride]
        idx_start_strided = idx_start_data // stride
        idx_end_strided = idx_end_data // stride
        
        targets = get_style_targets(motion_strided, idx_start_strided, idx_end_strided)
        if not targets:
            print("   ⏩ Dati insufficienti per target. Salto.")
            continue
            
        # Estrai pezzo traiettoria JSON per il constraint
        traj_segment = p_traj[gap_start_json:gap_end_json]
        
        ext_constraints = build_constraints(
            targets[0], motion_strided, idx_start_strided, idx_end_strided, traj_segment, device
        )
        
        try:
            num_gen_frames = idx_end_strided - idx_start_strided
            if num_gen_frames <= 0: continue
            
            syn_tensor = model.run(
                target=targets,
                criteria=criteria,
                num_frames=str(num_gen_frames),
                num_steps=10,
                noise_sigma=0.5,
                patch_size=11,
                coarse_ratio="0.2x_nframes",
                pyr_factor=0.75,
                ext=ext_constraints
            )
            
            syn_parsed = targets[0].parse(syn_tensor)
            
            # Creazione Azione Blender
            action_name = f"Trans_{switch_idx}"
            ac = bpy.data.actions.new(name=action_name)
            
            # Salvataggio temporaneo BVH per reimportare correttamente sulle ossa
            temp_bvh_path = os.path.join(BASE_PATH, "temp_gap.bvh")
            targets[0].write(temp_bvh_path, syn_tensor)
            
            bpy.ops.import_anim.bvh(filepath=temp_bvh_path, target='ARMATURE', update_scene_fps=False, update_scene_duration=False)
            
            # Gestione import
            imported_obj = bpy.context.selected_objects[0] # L'import seleziona il nuovo oggetto/armatura
            if imported_obj.animation_data and imported_obj.animation_data.action:
                imported_action = imported_obj.animation_data.action
                imported_action.name = action_name
                
                strip = trans_track.strips.new(name=action_name, start=int(idx_start_data), action=imported_action)
                strip.blend_type = 'REPLACE'
                strip.blend_in = 5
                strip.blend_out = 5
                strip.scale = (idx_end_data - idx_start_data) / imported_action.frame_range[1]
            
            bpy.ops.object.delete() # Rimuovi oggetto temp
            if os.path.exists(temp_bvh_path): os.remove(temp_bvh_path)
            
            # Ripristina selezione originale
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            
        except Exception as e:
            print(f"   ❌ Errore generazione: {e}")
            import traceback
            traceback.print_exc()

    print("✅ Processo completato.")

if __name__ == "__main__":
    run_smart_gap_filling()