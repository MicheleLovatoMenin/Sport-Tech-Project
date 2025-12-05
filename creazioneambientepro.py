import bpy
import os

# ===== CONFIGURAZIONE PERCORSI =====
BASE_PATH = r"C:\Users\miklo\Desktop\Sport-Tech-Project"

COURT_FILE = "basketball_court.glb"
BALL_BLEND_PATH = r"C:\Users\miklo\Desktop\Sport-Tech-Project\basketballball_v31_cycles\basketballball_v3.1_Cycles.blend"
BALL_OBJECT_NAME_IN_BLEND = "bbc_ball_body"

# ===== VALORI DI SCALA E POSIZIONE =====
COURT_SCALE = (3.355, 3.355, 3.355)
BALL_SCALE = (3.3, 3.3, 3.3)

# Character: da 1.65m a 6.5 piedi
# 6.5 feet / 1.65 meters = 3.939
PLAYER_SCALE = (3.75, 3.75, 3.75)

# Posizione del campo (centrato per dati CSV 0-94 piedi)
COURT_LOCATION = (25, 47, 0)
COURT_ROTATION = (0, 0, 0)


print("=== INIZIO IMPORTAZIONE CAMPO E PALLA ===")

# --- 1. Importa il Campo da Basket (.glb) ---
try:
    court_path = os.path.join(BASE_PATH, COURT_FILE)
    bpy.ops.import_scene.gltf(filepath=court_path)
    court_obj = bpy.context.active_object
    court_obj.name = "Court"
    print(f"✓ Campo '{COURT_FILE}' importato come 'Court'")
except Exception as e:
    print(f"✗ ERRORE importazione campo: {e}")


# --- 2. "Appendi" la Palla dal file .blend ---
try:
    obj_name = BALL_OBJECT_NAME_IN_BLEND
    
    with bpy.data.libraries.load(BALL_BLEND_PATH, link=False) as (data_from, data_to):
        if obj_name in data_from.objects:
            data_to.objects = [obj_name]
        else:
            print(f"✗ ERRORE: Oggetto '{obj_name}' NON TROVATO in {BALL_BLEND_PATH}")
    
    # Istanzia l'oggetto palla nella scena
    if obj_name in bpy.data.objects:
        ball_obj = bpy.data.objects[obj_name]
    elif f"{obj_name}.001" in bpy.data.objects:
        ball_obj = bpy.data.objects[f"{obj_name}.001"]
    else:
        # Cerca tra tutti gli oggetti
        found = False
        for obj in bpy.context.scene.objects:
            if obj.name.startswith(obj_name):
                ball_obj = obj
                found = True
                break
        if not found:
            raise Exception(f"Impossibile trovare l'oggetto palla {obj_name} dopo l'append.")
    
    ball_obj.name = "ball"
    
    # Assicura che sia nella collezione principale
    if ball_obj.name not in bpy.context.collection.objects:
        bpy.context.collection.objects.link(ball_obj)
    
    print(f"✓ Palla '{obj_name}' importata come 'ball'")
        
except Exception as e:
    print(f"✗ ERRORE append palla: {e}")


# --- 3. Standardizzazione Campo ---
print("\n=== STANDARDIZZAZIONE ASSET ===")

if "Court" in bpy.data.objects:
    court_obj = bpy.data.objects["Court"]
    court_obj.location = COURT_LOCATION
    court_obj.rotation_euler = COURT_ROTATION
    court_obj.scale = COURT_SCALE
    print("✓ Campo standardizzato.")
    
    # Scala Z aggiuntiva per tabelloni e canestri
    print("  → Applicazione scala Z a tabelloni e canestri...")
    prefixes_to_scale = [
        "Basketball_Backboard",
        "Basketball_Rim"
    ]
    
    for obj in bpy.data.objects:
        for prefix in prefixes_to_scale:
            if obj.name.startswith(prefix):
                obj.scale.z = obj.scale.z * 1.023
                break
    
    print("  ✓ Scala Z di tabelloni e canestri modificata.")
else:
    print("✗ Oggetto 'Court' non trovato.")


# --- 4. Standardizzazione Palla ---
if "ball" in bpy.data.objects:
    ball_obj = bpy.data.objects["ball"]
    ball_obj.location = (25, 25, 1.5)  # Posizione iniziale (centro campo, leggermente sollevata)
    ball_obj.rotation_euler = (0, 0, 0)
    ball_obj.scale = BALL_SCALE
    print("✓ Palla standardizzata.")
else:
    print("✗ Oggetto 'ball' non trovato.")


# --- 5. Standardizzazione Character ---
if "Armature" in bpy.data.objects:
    armature_obj = bpy.data.objects["Armature"]
    armature_obj.scale = PLAYER_SCALE
    print(f"✓ Character 'Armature' scalato a {PLAYER_SCALE[0]:.3f} (da 1.65m a ~6.5 piedi)")
else:
    print("✗ Oggetto 'Armature' non trovato.")


# --- 6. Imposta Telecamera Top-Down ---
bpy.ops.object.camera_add(
    location=(47, 25, 120),
    rotation=(0, 0, 0)
)
camera = bpy.context.active_object
camera.name = "TopDownCamera"
bpy.context.scene.camera = camera
print("✓ Telecamera top-down impostata.")


print("\n=== IMPORTAZIONE COMPLETATA ===")
print(f"✓ Character 'Armature' scalato correttamente (~6.5 piedi)")
print(f"✓ Campo posizionato in: {COURT_LOCATION}")
print(f"✓ Palla posizionata in: (25, 25, 1.5)")
print(f"\n📏 Sistema di unità: 1 unità Blender = 1 piede")
print("   Campo: 94 x 50 piedi")
print("   Canestro: 10 piedi")
print("   Giocatore: ~6.5 piedi")
print("\nPronto per l'animazione! 🏀")