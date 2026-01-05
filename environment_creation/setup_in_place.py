import bpy
import os

# --- CONFIGURAZIONE ---
FBX_FOLDER_PATH = "C:/Users/Sport Tech Student/PYTHON_DIRECTORY/Sport-Tech-Project/animations" # <--- Rimetti il tuo percorso
TARGET_CHAR_NAME = "Armature" 
ROOT_BONE_NAME = "mixamorig:Hips"  # <--- Root bone Mixamo
# ----------------------

def make_animation_in_place(armature, root_bone_name):
    """
    Rimuove le traslazioni XYZ dal root bone per rendere l'animazione in place
    """
    if not armature.animation_data or not armature.animation_data.action:
        return
    
    action = armature.animation_data.action
    
    # Trova le curve di animazione del root bone
    for fcurve in action.fcurves:
        # Controlla se è una curva di location del root bone
        # Formato: pose.bones["NomeBone"].location
        if f'pose.bones["{root_bone_name}"].location' in fcurve.data_path:
            # Cancella keyframe X e Z (mantieni Y per altezza)
            if fcurve.array_index in [0, 2]:  # 0=X, 2=Z
                action.fcurves.remove(fcurve)
    
    print(f"  → Animazione convertita in place (rimosso movimento XZ da '{root_bone_name}')")


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
    
    # Assicurati che il target sia selezionato e attivo
    bpy.ops.object.select_all(action='DESELECT')
    target_armature.select_set(True)
    bpy.context.view_layer.objects.active = target_armature
    
    # Verifica che siamo in Object Mode
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
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

        # 3. CONVERTI IN PLACE (NUOVO!)
        make_animation_in_place(target_armature, ROOT_BONE_NAME)

        # 4. Salva, Copia e Sposta l'Animazione
        if target_armature.animation_data and target_armature.animation_data.action:
            
            raw_action = target_armature.animation_data.action
            
            # Crea copia unica
            final_action = raw_action.copy()
            final_action.name = action_name
            final_action.use_fake_user = True
            
            # Push Down (NLA)
            if not target_armature.animation_data.nla_tracks:
                 target_armature.animation_data.nla_tracks.new()
            
            track = target_armature.animation_data.nla_tracks.new()
            track.name = action_name
            
            start_frame = int(final_action.frame_range[0])
            track.strips.new(final_action.name, start_frame, final_action)
            track.mute = True

            # Pulizia
            target_armature.animation_data.action = None
            bpy.data.actions.remove(raw_action)

            print(f"  SUCCESSO: Azione '{action_name}' salvata e archiviata.")
            
        else:
            print("  ATTENZIONE: Retargeting finito ma nessuna azione trovata sul target.")

        # 5. Pulizia Source
        bpy.data.objects.remove(source_armature, do_unlink=True)
    
    # Riattiva tutte le tracce NLA alla fine
    if target_armature.animation_data:
        for track in target_armature.animation_data.nla_tracks:
            track.mute = False

    print("\n--- TUTTO COMPLETATO ---")

run_batch_retargeting()