import bpy

# --- CONFIGURAZIONE ---
CHAR_NAME = "Armature" 

ANIM_1 = "dribble_run_sx"
ANIM_2 = "change_hand_vanilla_sx_to_dx_to_sx"
ANIM_3 = "jumpshot_sx"

FRAME_DI_TAGLIO = 250  
SPOSTAMENTO_X_LATERALE = +4.4
SPOSTAMENTO_Y_LATERALE = +0.5

OVERLAP_FINALE = 10     
# ----------------------

def create_basketball_sequence():
    obj = bpy.data.objects.get(CHAR_NAME)
    if not obj or not obj.animation_data:
        print("Errore: Personaggio non trovato.")
        return

    # 1. Pulizia Totale
    if obj.animation_data.nla_tracks:
        for track in obj.animation_data.nla_tracks:
            obj.animation_data.nla_tracks.remove(track)
            
    if obj.animation_data.action:
        bpy.data.actions.remove(obj.animation_data.action)

    # 2. Creiamo i binari
    track1 = obj.animation_data.nla_tracks.new()
    track1.name = "Track_A"
    track2 = obj.animation_data.nla_tracks.new()
    track2.name = "Track_B"
    
    current_start_frame = 1 

    # --- STRIP 1 (Track A) ---
    if ANIM_1 in bpy.data.actions:
        act1 = bpy.data.actions[ANIM_1]
        strip1 = track1.strips.new(ANIM_1, start=int(current_start_frame), action=act1)
        
        # Taglio preciso
        strip1.action_frame_end = FRAME_DI_TAGLIO
        strip1.blend_out = 0 
        strip1.extrapolation = 'HOLD_FORWARD'

        # --- GESTIONE POSIZIONE "CHIRURGICA" ---
        
        # Frame 1: Posizione 0
        obj.location.x = 0
        obj.location.y = 0
        obj.keyframe_insert(data_path="location", frame=1)
        
        # Frame 250 (Ultimo frame della corsa): ANCORA A ZERO
        frame_end_anim1 = strip1.frame_end
        obj.keyframe_insert(data_path="location", frame=frame_end_anim1)
        
        # Frame 251 (Primo frame del palleggio): NUOVA POSIZIONE
        frame_start_anim2 = frame_end_anim1 + 1
        
        obj.location.x = SPOSTAMENTO_X_LATERALE
        obj.location.y = SPOSTAMENTO_Y_LATERALE
        obj.keyframe_insert(data_path="location", frame=frame_start_anim2)
        
        # Interpolazione CONSTANT
        # Significa: "Resta a 0 fino all'ultimo istante, poi scatta al 251"
        if obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                if fc.data_path == "location":
                    for kf in fc.keyframe_points:
                        kf.interpolation = 'CONSTANT'

        # Definiamo l'inizio della prossima animazione al 251
        next_start = frame_start_anim2
    else:
        print(f"Skip: {ANIM_1}")
        next_start = current_start_frame

    # --- STRIP 2 (Track B) ---
    if ANIM_2 in bpy.data.actions:
        act2 = bpy.data.actions[ANIM_2]
        strip2 = track2.strips.new(ANIM_2, start=int(next_start), action=act2)
        
        strip2.blend_in = 0  # Nessuna sfumatura in ingresso
        
        # Sfumatura in uscita (verso la 3)
        strip2.blend_out = OVERLAP_FINALE
        strip2.use_auto_blend = True 
        strip2.extrapolation = 'HOLD_FORWARD'
        
        next_start = strip2.frame_end - OVERLAP_FINALE
        last_end_frame = strip2.frame_end
    else:
        print(f"Skip: {ANIM_2}")

    # --- STRIP 3 (Track A) ---
    if ANIM_3 in bpy.data.actions:
        act3 = bpy.data.actions[ANIM_3]
        strip3 = track1.strips.new(ANIM_3, start=int(next_start), action=act3)
        
        strip3.blend_in = OVERLAP_FINALE
        strip3.use_auto_blend = True
        
        last_end_frame = strip3.frame_end

    bpy.context.scene.frame_end = int(last_end_frame)
    bpy.context.scene.frame_start = 1
    
    # Refresh forzato della scena
    bpy.context.view_layer.update()
    
    print(f"FATTO. Scatto posizione impostato ESATTAMENTE al frame {int(frame_start_anim2)}.")

create_basketball_sequence()