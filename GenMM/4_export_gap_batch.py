import bpy
import os
import json

# ==================== CONFIGURAZIONE ====================
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"
WORK_DIR = os.path.join(BASE_PATH, "baby_step_optimized")
LABS_DIR = os.path.join(WORK_DIR, "temp_labs")
LIBRARY_DIR = os.path.join(WORK_DIR, "gap_libraries")
METADATA_PATH = os.path.join(WORK_DIR, "lab_metadata.json")

# Nome dell'oggetto Armatura nel file (di solito è "Armature")
RIG_OBJECT_NAME = "Armature"

# ==================== UTILS ====================

def setup_dirs():
    if not os.path.exists(LIBRARY_DIR):
        os.makedirs(LIBRARY_DIR)
        print(f"📁 Creata cartella librerie: {LIBRARY_DIR}")

def load_metadata():
    if not os.path.exists(METADATA_PATH):
        raise Exception("Metadata non trovato. Esegui Script 2.")
    with open(METADATA_PATH, 'r') as f:
        return json.load(f)

def clean_scene():
    """Rimuove tutto per lavorare puliti"""
    bpy.ops.wm.read_homefile(use_empty=True)

def process_single_gap(gap_key, metadata):
    # 1. Costruzione Percorsi
    filled_filename = gap_key.replace(".blend", "_filled.blend")
    filled_path = os.path.join(LABS_DIR, filled_filename)
    
    if not os.path.exists(filled_path):
        print(f"⚠️ File Filled mancante: {filled_filename} (Skip)")
        return False

    gap_id = gap_key.replace("lab_", "").replace(".blend", "")
    output_filename = f"{gap_id}_filled.blend"
    output_path = os.path.join(LIBRARY_DIR, output_filename)

    print(f"\n📦 PROCESSING: {gap_id}")
    print(f"   Input: {filled_filename}")
    
    # 2. CARICAMENTO INTELLIGENTE (OBJECT-BASED)
    # Invece di caricare l'azione per nome, carichiamo l'Armatura
    # per vedere quale azione ha assegnata "addosso".
    
    target_action = None
    temp_obj = None

    with bpy.data.libraries.load(filled_path, link=False) as (data_from, data_to):
        if RIG_OBJECT_NAME in data_from.objects:
            data_to.objects = [RIG_OBJECT_NAME]
        else:
            print(f"   ❌ Oggetto '{RIG_OBJECT_NAME}' non trovato nel file.")
            return False
            
    # Ora abbiamo l'oggetto caricato in bpy.data.objects, ma non in scena
    if data_to.objects:
        temp_obj = data_to.objects[0]
        if temp_obj.animation_data and temp_obj.animation_data.action:
            target_action = temp_obj.animation_data.action
            print(f"   🎯 Azione Rilevata sull'Armatura: '{target_action.name}'")
        else:
            print("   ❌ L'Armatura nel file non ha un'azione attiva!")
            # Fallback disperato: proviamo a cercare 'synsized Retarget' o simili se vuoi
            return False
    
    if not target_action:
        return False

    # Rinomina per pulizia
    target_action.name = f"Action_{gap_id}"
    
    # ====================================================
    # 3. APPLICAZIONE LOGICA IBRIDA
    # ====================================================
    
    GAP_START_FRAME = metadata['gap_start']
    GAP_END_FRAME = metadata['gap_end']
    
    print(f"   🔧 Processing Frames: {GAP_START_FRAME} -> {GAP_END_FRAME}")

    # --- A. Normalizzazione Selettiva (Height Lock) ---
    root_curves = [fc for fc in target_action.fcurves 
                   if ('Hips' in fc.data_path or 'root' in fc.data_path) and 'location' in fc.data_path]
    
    for fc in root_curves:
        axis_index = fc.array_index 
        
        # Y (Altezza) -> KEEP
        if axis_index == 1: 
            pass
        # X, Z (Piano) -> RESET a 0 (In Place)
        else:
            start_val = fc.evaluate(GAP_START_FRAME)
            # Rimuoviamo l'offset iniziale per centrare l'azione
            if abs(start_val) > 0.0001:
                for kp in fc.keyframe_points:
                    kp.co.y -= start_val

    # --- B. Crop (Taglio Frame) ---
    # Usiamo una tolleranza minima per evitare errori di float
    for fcurve in target_action.fcurves:
        for i in range(len(fcurve.keyframe_points) - 1, -1, -1):
            kp = fcurve.keyframe_points[i]
            frame = kp.co.x
            # Taglio secco fuori dal range
            if frame < (GAP_START_FRAME - 0.1) or frame > (GAP_END_FRAME + 0.1):
                fcurve.keyframe_points.remove(kp)
    
    # --- C. Spostamento Temporale (Start @ 0) ---
    offset_frame = GAP_START_FRAME
    for fc in target_action.fcurves:
        for kp in fc.keyframe_points:
            kp.co.x -= offset_frame
    
    # 4. SALVATAGGIO LIBRERIA
    try:
        # Scriviamo solo l'azione elaborata
        bpy.data.libraries.write(output_path, {target_action})
        print(f"   ✅ SALVATO: {output_filename}")
        
        # Pulizia RAM
        bpy.data.actions.remove(target_action)
        bpy.data.objects.remove(temp_obj)
        return True
        
    except Exception as e:
        print(f"   ❌ Errore salvataggio: {e}")
        return False

# ==================== MAIN ====================

def main():
    print("="*50)
    print("📦 BATCH EXPORTER (AUTO-DETECT ACTION)")
    print("="*50)
    
    setup_dirs()
    # clean_scene() # Opzionale, se lanciato da CLI puro
    
    try:
        metadata = load_metadata()
        count = 0
        for gap_key, info in metadata.items():
            # Eseguiamo il clean parziale dentro il loop per sicurezza
            if process_single_gap(gap_key, info):
                count += 1
                
        print("-" * 50)
        print(f"✅ COMPLETATO. Librerie create: {count}/{len(metadata)}")
        
    except Exception as e:
        print(f"❌ ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()