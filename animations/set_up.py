import bpy
import os

# --- CONFIGURAZIONE ---
FBX_FOLDER_PATH = "C:/Percorso/Delle/Tue/Animazioni/" # <--- Rimetti il tuo percorso
TARGET_CHAR_NAME = "michele_ST_Root" 
# ----------------------

def run_batch_retargeting():
    # Verifica Target
    if TARGET_CHAR_NAME not in bpy.data.objects:
        print(f"ERRORE CRITICO: Non trovo l'oggetto target '{TARGET_CHAR_NAME}'")
        return

    target_armature = bpy.data.objects[TARGET_CHAR_NAME]
    
    # Lista file
    try:
        files = [f for f in os.listdir(FBX_FOLDER_PATH) if f.lower().endswith(".fbx")]
    except FileNotFoundError:
        print("ERRORE: La cartella specificata non esiste.")
        return

    if not files:
        print("Nessun file FBX trovato!")
        return

    print(f"Inizio elaborazione di {len(files)} animazioni...")
    bpy.ops.object.mode_set(mode='OBJECT')

    for file_name in files:
        filepath = os.path.join(FBX_FOLDER_PATH, file_name)
        action_name = file_name.replace(".fbx", "")
        
        print(f"\n--- Elaborazione: {action_name} ---")

        # 1. Importa FBX
        bpy.ops.import_scene.fbx(filepath=filepath, force_connect_children=True, automatic_bone_orientation=True)
        
        source_armature = None
        for obj in bpy.context.selected_objects:
            if obj.type == 'ARMATURE':
                source_armature = obj
                break
        
        if not source_armature:
            print("  ERRORE: Nessuna armatura trovata nel file importato.")
            continue

        source_armature.name = "Source_Temp_Armature"

        # 2. Setup Rokoko
        try:
            bpy.context.scene.rsl_retargeting_armature_target = target_armature
            bpy.context.scene.rsl_retargeting_armature_source = source_armature
            
            print("  Costruzione Bone List...")
            bpy.ops.rsl.build_bone_list()
            
            print("  Esecuzione Retargeting...")
            bpy.ops.rsl.retarget_animation()
            
        except Exception as e:
            print(f"  ERRORE durante operazione Rokoko: {e}")
            bpy.data.objects.remove(source_armature, do_unlink=True)
            continue

        # --- MODIFICA FONDAMENTALE QUI SOTTO ---

        # 3. Salva, Copia e Sposta l'Animazione
        if target_armature.animation_data and target_armature.animation_data.action:
            
            # Prendiamo l'azione "grezza" appena creata da Rokoko
            raw_action = target_armature.animation_data.action
            
            # A. CREIAMO UNA COPIA UNICA
            # Questo è il segreto: creiamo un nuovo blocco di dati separato
            final_action = raw_action.copy()
            final_action.name = action_name # Rinominiamo la copia
            
            # B. Fake User sulla copia
            final_action.use_fake_user = True
            
            # C. Push Down (NLA) usando la COPIA
            if not target_armature.animation_data.nla_tracks:
                 target_armature.animation_data.nla_tracks.new()
            
            track = target_armature.animation_data.nla_tracks.new()
            track.name = action_name # Diamo un nome alla traccia per ordine
            
            start_frame = int(final_action.frame_range[0])
            track.strips.new(final_action.name, start_frame, final_action)
            
            # D. IMPORTANTE: MUTARE LA TRACCIA
            # Dobbiamo spegnere questa animazione, altrimenti quando importi 
            # la successiva, questa influenzerà la posa del personaggio!
            track.mute = True

            # E. Pulizia slot attivo
            # Sganciamo l'azione dalla timeline attiva
            target_armature.animation_data.action = None
            
            # Opzionale: Cancelliamo l'azione "raw" originale di Rokoko per pulizia
            # (Tanto abbiamo salvato la copia "final_action")
            bpy.data.actions.remove(raw_action)

            print(f"  SUCCESSO: Azione '{action_name}' salvata e archiviata.")
            
        else:
            print("  ATTENZIONE: Retargeting finito ma nessuna azione trovata sul target.")

        # 4. Pulizia Source
        bpy.data.objects.remove(source_armature, do_unlink=True)
    
    # Riattiva tutte le tracce NLA alla fine (opzionale, se vuoi vederle)
    if target_armature.animation_data:
        for track in target_armature.animation_data.nla_tracks:
            track.mute = False

    print("\n--- TUTTO COMPLETATO ---")

run_batch_retargeting()