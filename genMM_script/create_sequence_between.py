import bpy

# --- CONFIGURAZIONE SCENARIO "GAP" ---
# Definisci qui i due attori della scena
CLIP_A_NAME = "change_hand_legs_dx_to_sx"   # L'azione prima del buco (Palleggio)
CLIP_B_NAME = "shot_dribble_sx" # L'azione dopo il buco (Tiro)

GAP_LENGTH = 20                  # Numero di frame di "buco" desiderati

NOME_OUTPUT = "Training_Gap_FullLength"

def trova_armatura_corretta(obj):
    if not obj: return None
    if obj.type == 'ARMATURE': return obj
    if obj.parent and obj.parent.type == 'ARMATURE': return obj.parent
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object: return mod.object
    return None

def crea_scenario_gap_dinamico(obj_input):
    obj = trova_armatura_corretta(obj_input)
    if not obj:
        print("ERRORE: Seleziona un'armatura!")
        return

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    if not obj.animation_data:
        obj.animation_data_create()
    
    anim_data = obj.animation_data
    
    # Recupera le Azioni
    action_a = bpy.data.actions.get(CLIP_A_NAME)
    action_b = bpy.data.actions.get(CLIP_B_NAME)

    if not action_a or not action_b:
        print(f"ERRORE: Controlla i nomi '{CLIP_A_NAME}' e '{CLIP_B_NAME}'")
        return

    # Pulisci NLA
    for track in anim_data.nla_tracks:
        anim_data.nla_tracks.remove(track)
        
    track = anim_data.nla_tracks.new()
    track.name = "Gap_Setup_Track"
    
    print(f"--- Costruzione Dinamica su '{obj.name}' ---")

    # --- 1. POSIZIONA CLIP A (Intera) ---
    # Inizia al frame 0 (o 1, modificabile se preferisci)
    start_a = 0
    strip_a = track.strips.new(CLIP_A_NAME, start_a, action_a)
    
    # Imposta estrapolazione su HOLD (mantiene l'ultima posa durante il buco prima del bake)
    strip_a.extrapolation = 'HOLD' 
    
    end_a = strip_a.frame_end
    print(f"[CLIP A]: {int(start_a)} -> {int(end_a)} (Totale: {int(end_a - start_a)} frames)")

    # --- 2. CALCOLA IL GAP ---
    gap_start = end_a
    gap_end = gap_start + GAP_LENGTH
    print(f"[GAP]:    {int(gap_start)} -> {int(gap_end)} (Durata: {GAP_LENGTH} frames)")

    # --- 3. POSIZIONA CLIP B (Intera) ---
    strip_b = track.strips.new(CLIP_B_NAME, int(gap_end), action_b)
    end_b = strip_b.frame_end
    print(f"[CLIP B]: {int(gap_end)} -> {int(end_b)} (Totale: {int(end_b - gap_end)} frames)")
    
    # --- SETUP SCENA ---
    bpy.context.scene.frame_start = int(start_a)
    bpy.context.scene.frame_end = int(end_b)
    
    # --- BAKE (Cruciale per creare l'interpolazione nel buco) ---
    print("--- Inizio Bake ---")
    
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    
    bpy.ops.nla.bake(
        frame_start=int(start_a),
        frame_end=int(end_b),
        only_selected=True,
        visual_keying=True,
        clear_constraints=False,
        use_current_action=False,
        bake_types={'POSE'}
    )
    
    if obj.animation_data.action:
        obj.animation_data.action.name = NOME_OUTPUT
        print(f"Fatto! Output: '{NOME_OUTPUT}'.")
        print(f"La 'Zona Morta' da analizzare/riempire va dal frame {int(gap_start)} al {int(gap_end)}.")

    bpy.ops.object.mode_set(mode='OBJECT')

# ESEGUI
obj_attivo = bpy.context.view_layer.objects.active
crea_scenario_gap_dinamico(obj_attivo)