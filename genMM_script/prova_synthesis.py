import bpy
import numpy as np
import torch
import sys
import os

# =================================================================================
# 🛠️ HOTFIX AUTOMATICO PER L'ERRORE 'velo_mask' (GIA' FUNZIONANTE)
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
        else:
            self.n_pad = 0

        if self.contact_id is not None: self.n_contact = len(contact_id)
        else: self.n_contact = 0

        # === FIX: Logica robusta per velo_mask ===
        if self.keep_up_pos:
            if self.up_axis == 'X_UP':
                self.velo_mask = [-2, -1]
            elif self.up_axis == 'Y_UP':
                self.velo_mask = [-3, -1]
            else: 
                # Fallback su Z_UP
                self.velo_mask = [-3, -2]
        else:
            self.velo_mask = [-3, -2, -1]
        # ==========================================

        if self.use_velo:
            self.data = self.to_velocity(self.data)

    motion_module.MotionData.__init__ = fixed_init
    print("✅ HOTFIX APPLICATO: Errore velo_mask corretto in memoria.")

except ImportError:
    pass # Ignora se non trova il modulo (fallback import successivi)
except Exception as e:
    print(f"❌ Errore durante l'hotfix: {e}")

# =================================================================================
# 🚀 SCRIPT DI SINTESI (Test 0 - CORRETTO)
# =================================================================================

# PARAMETRI UTENTE
TARGET_DURATION = 400        # Frame da generare (come nel tuo log)
UP_AXIS = 'Y_UP'             # Assicurati sia corretto per il tuo FBX

try:
    from GenMM import GenMM
    from nearest_neighbor.losses import PatchCoherentLoss
    from dataset.blender_motion import BlenderMotion
    from GenMM_blender_addon import get_bvh_data, load 
except ImportError:
    try:
        from __init__ import get_bvh_data, load
    except:
        pass

def run_test():
    # 1. ACQUISIZIONE DATI
    obj = bpy.context.object
    if not obj or obj.type != 'ARMATURE':
        print("ERRORE: Seleziona l'armatura FBX prima di avviare lo script.")
        return

    scene = bpy.context.scene
    print(f"Lettura dati dall'armatura: {obj.name}...")
    
    bvh_str = get_bvh_data(bpy.context, frame_start=scene.frame_start, frame_end=scene.frame_end)

    lines = bvh_str.split('\n')
    try:
        motion_idx = lines.index('MOTION') + 3
    except ValueError:
        print("Errore nel parsing dei dati BVH.")
        return

    motion_data_str = lines[motion_idx:]
    motion_data_vals = []
    for line in motion_data_str:
        if line.strip():
            try:
                vals = [float(x) for x in line.split()]
                motion_data_vals.append(vals)
            except: pass
    
    motion_np = np.array(motion_data_vals, dtype=np.float32)
    print(f"Dati letti: {motion_np.shape[0]} frame.")

    # 2. INIZIALIZZAZIONE GENMM
    print("Inizializzazione Modello...")
    
    dataset = BlenderMotion(motion_np, 
                            repr='repr6d', 
                            use_velo=True, 
                            keep_up_pos=True, 
                            up_axis=UP_AXIS,
                            padding_last=False)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = GenMM(device=device, silent=False)
    criteria = PatchCoherentLoss(patch_size=11, alpha=0.05, loop=False, cache=True)

    # 3. ESECUZIONE (CON CORREZIONE coarse_ratio)
    print(f"Generazione di {TARGET_DURATION} frame...")
    
    try:
        syn_tensor = model.run(
            target=[dataset], 
            criteria=criteria,
            num_frames=str(TARGET_DURATION), 
            num_steps=5,
            noise_sigma=0.5,
            patch_size=11,
            # --- MODIFICA CRUCIALE QUI SOTTO ---
            coarse_ratio="0.2x_nframes",  # Passiamo una stringa, non un float!
            # -----------------------------------
            pyr_factor=0.75
        )
    except Exception as e:
        print(f"Errore durante model.run: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. APPLICAZIONE
    print("Applicazione in Blender...")
    syn_parsed = dataset.parse(syn_tensor)
    
    # Ricostruzione BVH
    header_str = "\n".join(lines[:motion_idx]) + "\n"
    data_str = ""
    for frame in syn_parsed:
        data_str += " ".join(map(str, frame)) + "\n"
    
    full_bvh_content = header_str + data_str
    
    # --- CORREZIONE QUI SOTTO ---
    # La funzione load() vuole una LISTA di righe, non una stringa unica.
    bvh_lines = full_bvh_content.split('\n')
    
    load(bpy.context, bvh_lines, target='ARMATURE', global_matrix=obj.matrix_world, report=print)
    
    print("✅ Fatto! Controlla la nuova Action.")

run_test()