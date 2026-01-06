import bpy
import os

# ===== PATH CONFIGURATION =====
BASE_PATH = r"C:\Users\Sport Tech Student\PYTHON_DIRECTORY\Sport-Tech-Project"

COURT_FILE = "objects/basketball_court.glb"
BALL_BLEND_PATH = "objects/ball.blend"
BALL_OBJECT_NAME_IN_BLEND = "bbc_ball_body"

# ===== SCALE AND LOCATION VALUES ====
COURT_SCALE = (3.355, 3.355, 3.355)
BALL_SCALE = (3.3, 3.3, 3.3)

# Character: from 1.65m to 6.5 feet
PLAYER_SCALE = (3.75, 3.75, 3.75)

# Court position and rotation
COURT_LOCATION = (25, 47, 0)
COURT_ROTATION = (0, 0, 0)


print("=== START IMPORTING COURT AND BALL ===")

# Import Basketball Court
try:
    court_path = os.path.join(BASE_PATH, COURT_FILE)
    bpy.ops.import_scene.gltf(filepath=court_path)
    court_obj = bpy.context.active_object
    court_obj.name = "Court"
    print(f"Court '{COURT_FILE}' imported as 'Court'")
except Exception as e:
    print(f"ERROR importing court: {e}")


# Append the ball from blend file
try:
    obj_name = BALL_OBJECT_NAME_IN_BLEND
    BALL_PATH = os.path.join(BASE_PATH, BALL_BLEND_PATH)

    with bpy.data.libraries.load(BALL_PATH, link=False) as (data_from, data_to):
        if obj_name in data_from.objects:
            data_to.objects = [obj_name]
        else:
            print(f"ERROR: Object '{obj_name}' NOT FOUND in {BALL_BLEND_PATH}")
    
    # Instantiate the ball object in the scene
    if obj_name in bpy.data.objects:
        ball_obj = bpy.data.objects[obj_name]
    elif f"{obj_name}.001" in bpy.data.objects:
        ball_obj = bpy.data.objects[f"{obj_name}.001"]
    else:
        found = False
        for obj in bpy.context.scene.objects:
            if obj.name.startswith(obj_name):
                ball_obj = obj
                found = True
                break
        if not found:
            raise Exception(f"Unable to find ball object {obj_name} after append.")
    
    ball_obj.name = "ball"

    if ball_obj.name not in bpy.context.collection.objects:
        bpy.context.collection.objects.link(ball_obj)
    
    print(f"Ball '{obj_name}' imported as 'ball'")
        
except Exception as e:
    print(f"ERROR appending ball: {e}")


# Court Standardization
print("\n=== ASSET STANDARDIZATION ===")

if "Court" in bpy.data.objects:
    court_obj = bpy.data.objects["Court"]
    court_obj.location = COURT_LOCATION
    court_obj.rotation_euler = COURT_ROTATION
    court_obj.scale = COURT_SCALE
    print("Court standardized.")
    
    # Additional Z scale for backboards and rims
    print("  -> Applying Z scale to backboards and rims...")
    prefixes_to_scale = [
        "Basketball_Backboard",
        "Basketball_Rim"
    ]
    
    for obj in bpy.data.objects:
        for prefix in prefixes_to_scale:
            if obj.name.startswith(prefix):
                obj.scale.z = obj.scale.z * 1.023
                break
    
    print("  Backboard and rim Z scale modified.")
else:
    print("Object 'Court' not found.")


# Ball Standardization
if "ball" in bpy.data.objects:
    ball_obj = bpy.data.objects["ball"]
    ball_obj.location = (25, 25, 1.5)
    ball_obj.rotation_euler = (0, 0, 0)
    ball_obj.scale = BALL_SCALE
    print("Ball standardized.")
else:
    print("Object 'ball' not found.")


# Character Standardization
if "Armature" in bpy.data.objects:
    armature_obj = bpy.data.objects["Armature"]
    armature_obj.scale = PLAYER_SCALE
    print(f"Character 'Armature' scaled to {PLAYER_SCALE[0]:.3f} (from 1.65m to ~6.5 feet)")
else:
    print("Object 'Armature' not found.")


# Set Up Top-Down Camera
bpy.ops.object.camera_add(
    location=(47, 25, 120),
    rotation=(0, 0, 0)
)
camera = bpy.context.active_object
camera.name = "TopDownCamera"
bpy.context.scene.camera = camera
print("Top-down camera set.")


print("\n=== IMPORT COMPLETED ===")
print(f"Character 'Armature' scaled correctly (~6.5 feet)")
print(f"Court positioned at: {COURT_LOCATION}")
print(f"Ball positioned at: (25, 25, 1.5)")
print(f"\nUnit system: 1 Blender unit = 1 foot")
print("   Court: 94 x 50 feet")
print("   Rim: 10 feet")
print("   Player: ~6.5 feet")
print("\nReady for animation!")