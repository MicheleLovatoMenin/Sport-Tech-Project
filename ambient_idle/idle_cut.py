import bpy

# --- CONFIGURAZIONE ---
TARGET_CHAR_NAME = "Armature"
SOURCE_ACTION_NAME = "stationary_shot_sx_2"
NEW_ACTION_NAME = "idle"
CUT_END_FRAME = 140  # L'ultimo frame valido
# ----------------------

def create_idle_cut_animation():
    print(f"\n=== CREAZIONE ANIMAZIONE '{NEW_ACTION_NAME}' DA TAGLIO (METODO ROBUSTO) ===")

    # 1. Verifica esistenza Armature
    if TARGET_CHAR_NAME not in bpy.data.objects:
        print(f"ERRORE: Oggetto '{TARGET_CHAR_NAME}' non trovato.")
        return
    
    armature = bpy.data.objects[TARGET_CHAR_NAME]
    
    # 2. Verifica esistenza Azione Sorgente
    if SOURCE_ACTION_NAME not in bpy.data.actions:
        print(f"ERRORE: L'azione '{SOURCE_ACTION_NAME}' non esiste in memoria.")
        return

    source_action = bpy.data.actions[SOURCE_ACTION_NAME]
    
    # 3. Crea la copia (Idle)
    new_action = source_action.copy()
    new_action.name = NEW_ACTION_NAME
    new_action.use_fake_user = True
    print(f"✓ Creata copia dell'azione: '{new_action.name}'")

    # 4. Taglio dei Keyframe (Iterazione Inversa)
    print(f"  → Rimozione keyframe oltre il frame {CUT_END_FRAME}...")
    deleted_count = 0
    
    for fcurve in new_action.fcurves:
        # Ottieni i punti chiave
        kps = fcurve.keyframe_points
        
        # Iteriamo ALL'INDIETRO (dall'ultimo al primo)
        # range(start, stop, step) -> partiamo dalla fine, arriviamo a -1 (escluso), passo -1
        for i in range(len(kps) - 1, -1, -1):
            kp = kps[i]
            # kp.co[0] è il numero del frame
            if kp.co[0] > CUT_END_FRAME:
                kps.remove(kp)
                deleted_count += 1
                
    # Aggiorna il range manuale dell'azione
    new_action.frame_start = 0
    new_action.frame_end = CUT_END_FRAME
    
    print(f"✓ Taglio completato. Rimossi {deleted_count} keyframe.")

    # 5. Inserimento nel sistema NLA
    if not armature.animation_data:
        armature.animation_data_create()
        
    track = armature.animation_data.nla_tracks.new()
    track.name = NEW_ACTION_NAME
    
    strip = track.strips.new(new_action.name, 0, new_action)
    track.mute = True
    
    # Pulizia azione attiva
    armature.animation_data.action = None

    print(f"✓ Traccia NLA '{track.name}' creata e impostata su MUTE.")
    print("=== OPERAZIONE COMPLETATA CON SUCCESSO ===")

# Esegui la funzione
create_idle_cut_animation()