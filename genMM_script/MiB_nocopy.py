import bpy
import numpy as np
import torch
import torch.nn.functional as F
import sys
import os

# === CONFIGURAZIONE UTENTE ===
TOTAL_START_FRAME = 1      
GAP_START_FRAME = 340      
GAP_END_FRAME = 365        
TOTAL_END_FRAME = 703      
UP_AXIS = 'Y_UP'

# =================================================================================
# 🛠️ HOTFIX 1: Dataset (velo_mask)
# =================================================================================
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
except ImportError: pass

# =================================================================================
# 🛠️ HOTFIX 2: Core Logic (In-Painting Constraint)
# =================================================================================
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
                synthesized = synthesized * mask_res + gt_res * (1 - mask_res)
            losses.append(loss.item())
            pbar.step()
        return synthesized, losses

    genmm_module.GenMM.match_and_blend = constrained_match_and_blend
    print("✅ Sistema In-Between abilitato in memoria.")
except ImportError: pass

# =================================================================================
# 🎬 ESECUZIONE
# =================================================================================
try:
    from GenMM import GenMM
    from nearest_neighbor.losses import PatchCoherentLoss
    from dataset.blender_motion import BlenderMotion
    from GenMM_blender_addon import get_bvh_data, load 
except ImportError:
    try: from __init__ import get_bvh_data, load
    except: pass

def run_inbetween_simple():
    # 1. ACQUISIZIONE
    obj = bpy.context.object
    if not obj or obj.type != 'ARMATURE':
        print("❌ Seleziona un'armatura.")
        return

    print(f"Lettura frame {TOTAL_START_FRAME}-{TOTAL_END_FRAME}...")
    bvh_str = get_bvh_data(bpy.context, frame_start=TOTAL_START_FRAME, frame_end=TOTAL_END_FRAME)
    
    lines = bvh_str.split('\n')
    try:
        motion_idx = lines.index('MOTION') + 3
    except ValueError:
        print("❌ Errore parsing BVH.")
        return

    motion_data_vals = []
    for line in lines[motion_idx:]:
        if line.strip():
            try: motion_data_vals.append([float(x) for x in line.split()])
            except: pass
    
    motion_np_full = np.array(motion_data_vals, dtype=np.float32)
    total_frames = motion_np_full.shape[0]

    # CALCOLO INDICI RELATIVI
    idx_gap_start = max(0, GAP_START_FRAME - TOTAL_START_FRAME)
    idx_gap_end = min(total_frames, GAP_END_FRAME - TOTAL_START_FRAME)
    
    # 2. CONFIGURAZIONE DATASET (Strategia: Divide et Impera)
    
    # A) Dataset Full: Serve SOLO per i vincoli (Lock Start/End)
    dataset_full = BlenderMotion(motion_np_full, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False)
    
    # B) Targets Puliti: Serve per l'apprendimento (Nascondiamo il buco all'AI!)
    print(f"✂️ Taglio Target per evitare il buco ({GAP_START_FRAME}-{GAP_END_FRAME})...")
    
    motion_pre_gap = motion_np_full[:idx_gap_start]  # Clip A
    motion_post_gap = motion_np_full[idx_gap_end:]   # Clip B
    
    targets_list = []
    if len(motion_pre_gap) > 5:
        targets_list.append(BlenderMotion(motion_pre_gap, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False))
    if len(motion_post_gap) > 5:
        targets_list.append(BlenderMotion(motion_post_gap, repr='repr6d', use_velo=True, keep_up_pos=True, up_axis=UP_AXIS, padding_last=False))

    if not targets_list:
        print("❌ Errore: Clip troppo corte per generare movimento.")
        return

    # 3. MODELLO
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = GenMM(device=device, silent=False)
    criteria = PatchCoherentLoss(patch_size=11, alpha=0.05, loop=False, cache=True)

    # 4. VINCOLI
    print(f"🔧 Mask Config: Libero da {idx_gap_start} a {idx_gap_end}")

    gt_tensor = dataset_full.motion_data.data.to(device)
    mask_tensor = torch.zeros_like(gt_tensor)
    mask_tensor[..., idx_gap_start:idx_gap_end] = 1.0

    ext_constraints = {
        'fix_mask': mask_tensor,
        'fix_value': gt_tensor
    }

    # 5. SINTESI
    print("🚀 Calcolo In-Between...")
    try:
        syn_tensor = model.run(
            target=targets_list,  # USIAMO LA LISTA PULITA, NON 'dataset_full'
            criteria=criteria,
            num_frames=str(total_frames), 
            num_steps=10,
            noise_sigma=0.5,
            patch_size=11,
            coarse_ratio="0.2x_nframes",
            pyr_factor=0.75,
            ext=ext_constraints
        )
    except Exception as e:
        print(f"❌ Errore Run: {e}")
        return

    # 6. OUTPUT SEMPLIFICATO
    print("💾 Generazione risultato...")
    # Usiamo dataset_full per il parsing inverso perché ha le dimensioni giuste
    syn_parsed = dataset_full.parse(syn_tensor)
    
    header_str = "\n".join(lines[:motion_idx]) + "\n"
    data_str = ""
    for frame in syn_parsed:
        data_str += " ".join(map(str, frame)) + "\n"
    
    full_bvh_content = header_str + data_str
    bvh_lines = full_bvh_content.split('\n')
    
    # Rimuoviamo la selezione precedente per evidenziare il nuovo oggetto
    bpy.ops.object.select_all(action='DESELECT')
    
    # Carica la nuova armatura (Blender la chiamerà 'synsized' o simile)
    load(bpy.context, bvh_lines, target='ARMATURE', global_matrix=obj.matrix_world, report=print)
    
    # Rinomina per chiarezza se possibile
    if bpy.context.active_object:
        bpy.context.active_object.name = "Result_InBetween"
        print(f"✅ Fatto! Creato oggetto: {bpy.context.active_object.name}")
    else:
        print("✅ Fatto! Cerca il nuovo oggetto nella scena.")

# Eseguiamo
run_inbetween_simple()