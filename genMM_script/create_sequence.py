import bpy

# --- CONFIGURAZIONE ---
# Inserisci qui i nomi ESATTI delle animazioni che vuoi unire, nell'ordine desiderato.
# Esempio: ["Idle", "Walk", "Run", "Turn_Left", "Idle"]

LISTA_ANIMAZIONI = [
    "dribble_run_dx",          
    "change_hand_legs_dx_to_sx",
    "shot_dribble_sx",
    "celly_lebron"
]

NOME_OUTPUT = "Training_Sequence"

def trova_armatura_corretta(obj):
    """Cerca di trovare l'armatura anche se l'utente ha selezionato la mesh"""
    if not obj:
        return None
    
    # Caso 1: Hai selezionato direttamente l'armatura
    if obj.type == 'ARMATURE':
        return obj
    
    # Caso 2: Hai selezionato la mesh, controlliamo il genitore
    if obj.parent and obj.parent.type == 'ARMATURE':
        print(f"INFO: Hai selezionato la Mesh '{obj.name}', uso il genitore '{obj.parent.name}'")
        return obj.parent
        
    # Caso 3: Cerca il modificatore Armatura sulla mesh
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
             print(f"INFO: Trovata armatura '{mod.object.name}' tramite modificatore")
             return mod.object
             
    return None

def unisci_animazioni(obj_input, azioni_nomi):
    # Usa la funzione smart per trovare l'oggetto giusto
    obj = trova_armatura_corretta(obj_input)

    if not obj:
        print("ERRORE FATALE: Nessuna armatura trovata! Assicurati di selezionare il personaggio (scheletro o mesh).")
        # Tentativo disperato: cerca la prima armatura nella scena
        for o in bpy.context.scene.objects:
            if o.type == 'ARMATURE':
                print(f"SUGGERIMENTO: Forse intendevi '{o.name}'?")
        return

    # Rendiamo l'armatura l'oggetto attivo ufficialmente
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Assicurati che l'oggetto abbia dati di animazione
    if not obj.animation_data:
        obj.animation_data_create()
    
    anim_data = obj.animation_data
    
    # 1. Pulizia tracce NLA
    for track in anim_data.nla_tracks:
        anim_data.nla_tracks.remove(track)
        
    # 2. Creazione nuova traccia
    track = anim_data.nla_tracks.new()
    track.name = "Sequenza_GenMM"
    
    current_frame = 1
    frame_start = 1
    
    print(f"--- Inizio unione su Armatura: '{obj.name}' ---")

    # 3. Accodamento
    count_ok = 0
    for nome_azione in azioni_nomi:
        action = bpy.data.actions.get(nome_azione)
        
        if action:
            strip = track.strips.new(nome_azione, int(current_frame), action)
            current_frame = strip.frame_end
            count_ok += 1
            print(f"OK: {nome_azione}")
        else:
            print(f"ERRORE: Animazione '{nome_azione}' NON trovata nel file Blender!")

    if count_ok == 0:
        print("NESSUNA animazione valida trovata. Controlla i nomi nella lista!")
        return

    # 4. Imposta durata scena
    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = int(current_frame)
    
    # 5. Bake
    print("--- Inizio Bake (Attendere...) ---")
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    
    bpy.ops.nla.bake(
        frame_start=frame_start, 
        frame_end=int(current_frame), 
        only_selected=True, 
        visual_keying=True, 
        clear_constraints=False, 
        use_current_action=False, 
        bake_types={'POSE'}
    )
    
    if obj.animation_data.action:
        obj.animation_data.action.name = NOME_OUTPUT
        print(f"COMPLETATO! Nuova azione: '{NOME_OUTPUT}' pronta.")
    
    bpy.ops.object.mode_set(mode='OBJECT')

# --- ESECUZIONE ---
obj_attivo = bpy.context.view_layer.objects.active
unisci_animazioni(obj_attivo, LISTA_ANIMAZIONI)