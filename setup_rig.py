import bpy
import os

# ========================================
# CONFIGURAZIONE - MODIFICA QUESTI PATH
# ========================================

# Path dei file FBX scaricati da Mixamo
PLAYER_RIGGED_FBX = r"C:/Users/miklo/Desktop/Sport-Tech-Project/fbx/X Bot.fbx"
DRIBBLE_FBX = r"C:/Users/miklo/Desktop/Sport-Tech-Project/fbx/Dribble.fbx"
WALK_FBX = r"C:/Users/miklo/Desktop/Sport-Tech-Project/fbx/Walk.fbx"
RUN_FBX = r"C:/Users/miklo/Desktop/Sport-Tech-Project/fbx/Fast_Run_In_Place.fbx"
IDLE_FBX = r"C:/Users/miklo/Desktop/Sport-Tech-Project/fbx/Idle.fbx"

# Nome del template che verrà creato
TEMPLATE_NAME = "player_rigged_template"

# ========================================
# SCRIPT - NON MODIFICARE SOTTO
# ========================================

print("=" * 60)
print("INIZIO SETUP PERSONAGGIO RIGGATO")
print("=" * 60)

def delete_object_by_name(name):
    """Cancella un oggetto per nome se esiste"""
    if name in bpy.data.objects:
        obj = bpy.data.objects[name]
        bpy.data.objects.remove(obj, do_unlink=True)
        print(f"✓ Cancellato oggetto: {name}")

def delete_all_armatures_except(keep_name=None):
    """Cancella tutte le armature tranne quella specificata"""
    armatures_to_delete = []
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            if keep_name is None or obj.name != keep_name:
                armatures_to_delete.append(obj)
    
    for arm in armatures_to_delete:
        print(f"✓ Cancello armature temporanea: {arm.name}")
        bpy.data.objects.remove(arm, do_unlink=True)

def import_fbx_and_get_armature(filepath):
    """Importa FBX e restituisce l'armature importata"""
    if not os.path.exists(filepath):
        print(f"✗ ERRORE: File non trovato: {filepath}")
        return None
    
    # Conta armature prima dell'import
    armatures_before = set([obj.name for obj in bpy.data.objects if obj.type == 'ARMATURE'])
    
    # Import FBX
    bpy.ops.import_scene.fbx(filepath=filepath)
    print(f"✓ Importato: {os.path.basename(filepath)}")
    
    # Trova la nuova armature
    armatures_after = set([obj.name for obj in bpy.data.objects if obj.type == 'ARMATURE'])
    new_armatures = armatures_after - armatures_before
    
    if new_armatures:
        return bpy.data.objects[list(new_armatures)[0]]
    return None

def get_action_from_armature(armature):
    """Estrae l'action dall'armature"""
    if armature and armature.animation_data and armature.animation_data.action:
        return armature.animation_data.action
    return None

def protect_and_rename_action(action, new_name):
    """Protegge e rinomina un'action"""
    if action:
        action.use_fake_user = True
        old_name = action.name
        action.name = new_name
        print(f"✓ Action protetta e rinominata: {old_name} → {new_name}")
        return action  # Ritorna l'action invece di True
    return None

# ========================================
# FASE 1: IMPORT PERSONAGGIO BASE
# ========================================

print("\n--- FASE 1: Import Personaggio Base ---")

# Cancella eventuali template precedenti
delete_object_by_name(TEMPLATE_NAME)

# Import personaggio base
base_armature = import_fbx_and_get_armature(PLAYER_RIGGED_FBX)

if not base_armature:
    print("✗ ERRORE: Impossibile importare il personaggio base!")
    raise Exception("Import fallito")

# Rinomina armature
base_armature.name = TEMPLATE_NAME
print(f"✓ Personaggio base rinominato: {TEMPLATE_NAME}")

# Imposta rotazione Euler
base_armature.rotation_mode = 'XYZ'

# Scala il personaggio (adatta al campo da basket)
base_armature.scale = (0.1, 0.1, 0.1)

# Muovi fuori dal campo
base_armature.location = (-100, 0, 0)

print(f"✓ Template posizionato e scalato")

# ========================================
# FASE 2: IMPORT ANIMAZIONI
# ========================================

print("\n--- FASE 2: Import Animazioni ---")

animations = [
    (RUN_FBX, "run"),
    (WALK_FBX, "walk"),
    (DRIBBLE_FBX, "dribble"),
    (IDLE_FBX, "idle")
]

imported_actions = []

for fbx_path, action_name in animations:
    print(f"\nImport animazione: {action_name}...")
    
    # Import FBX con animazione
    temp_armature = import_fbx_and_get_armature(fbx_path)
    
    if not temp_armature:
        print(f"✗ ATTENZIONE: Impossibile importare {action_name}")
        continue
    
    # Estrai l'action
    action = get_action_from_armature(temp_armature)
    
    if action:
        # PRIMA proteggi e rinomina (prima di cancellare l'armature!)
        renamed_action = protect_and_rename_action(action, action_name)
        
        if renamed_action:
            imported_actions.append(action_name)
            print(f"✓ Animazione '{action_name}' salvata correttamente")
        
        # POI cancella l'armature temporanea
        bpy.data.objects.remove(temp_armature, do_unlink=True)
        print(f"✓ Armature temporanea cancellata")
    else:
        print(f"✗ ATTENZIONE: Nessuna animazione trovata in {action_name}")
        bpy.data.objects.remove(temp_armature, do_unlink=True)

# ========================================
# FASE 3: PULIZIA FINALE
# ========================================

print("\n--- FASE 3: Pulizia Finale ---")

# Cancella eventuali armature rimaste
delete_all_armatures_except(TEMPLATE_NAME)

# Cancella actions non utilizzate (quelle con nomi strani di Mixamo)
actions_to_keep = ["idle", "walk", "run"]
actions_to_remove = []

for action in bpy.data.actions:
    if action.name not in actions_to_keep and action.users == 0:
        actions_to_remove.append(action)

for action in actions_to_remove:
    action_name = action.name
    bpy.data.actions.remove(action)
    print(f"✓ Cancellata action inutilizzata: {action_name}")

# ========================================
# FASE 4: VERIFICA FINALE
# ========================================

print("\n" + "=" * 60)
print("VERIFICA FINALE")
print("=" * 60)

# Verifica template
if TEMPLATE_NAME in bpy.data.objects:
    template = bpy.data.objects[TEMPLATE_NAME]
    print(f"✓ Template trovato: {TEMPLATE_NAME}")
    print(f"  - Tipo: {template.type}")
    print(f"  - Posizione: {template.location}")
    print(f"  - Scala: {template.scale}")
else:
    print(f"✗ ERRORE: Template non trovato!")

# Verifica animazioni
print(f"\n✓ Animazioni importate: {len(imported_actions)}")
for action_name in imported_actions:
    if action_name in bpy.data.actions:
        action = bpy.data.actions[action_name]
        frame_range = action.frame_range
        num_frames = int(frame_range[1] - frame_range[0])
        print(f"  - {action_name}: {len(action.fcurves)} curve, {num_frames} frames")
    else:
        print(f"  ✗ {action_name}: NON TROVATA!")

# ========================================
# FASE 5: TEST ANIMAZIONE
# ========================================

print("\n--- TEST: Assegno 'walk' al template ---")

if TEMPLATE_NAME in bpy.data.objects and "run" in bpy.data.actions:
    template = bpy.data.objects[TEMPLATE_NAME]
    run_action = bpy.data.actions["run"]
    
    # Crea animation_data se non esiste
    if not template.animation_data:
        template.animation_data_create()
    
    # Assegna l'action
    template.animation_data.action = run_action
    print(f"✓ Action 'run' assegnata al template")
    print(f"  → Premi SPACE per vedere il personaggio camminare!")
else:
    print("✗ Impossibile assegnare run")

print("\n" + "=" * 60)
print("SETUP COMPLETATO!")
print("=" * 60)
print(f"\nProssimi step:")
print(f"1. Seleziona '{TEMPLATE_NAME}' nell'Outliner")
print(f"2. Vai nell'Action Editor (in basso)")
print(f"3. Prova a cambiare animazione: run")
print(f"4. Premi SPACEBAR per testare")
print("\nSe tutto funziona, possiamo modificare lo script di animazione!")