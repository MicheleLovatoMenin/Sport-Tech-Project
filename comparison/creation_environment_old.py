import bpy
import os

BASE_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH"

COURT_FILE = "objects/basketball_court.glb"
PLAYER_FILE = "objects/base_mesh.glb"
BALL_FILE = "objects/ball.blend"
BALL_OBJECT_NAME_IN_BLEND = "bbc_ball_body"

# Correction values
COURT_SCALE = (3.355, 3.355, 3.355)
PLAYER_SCALE = (3.48, 3.48, 3.48)
BALL_SCALE = (3.3, 3.3, 3.3) 

COURT_LOCATION = (25, 47, 0)
COURT_ROTATION = (0, 0, 0)


# Scene Cleanup
if bpy.data.objects:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


# Asset Import

# Import Basketball Court
try:
    court_path = os.path.join(BASE_PATH, COURT_FILE)
    bpy.ops.import_scene.gltf(filepath=court_path)
    court_obj = bpy.context.active_object
    court_obj.name = "Court"
    print(f"Court '{COURT_FILE}' imported as 'Court'")
except Exception as e:
    print(f"ERROR importing court: {e}")


# Import Player Template
try:
    player_path = os.path.join(BASE_PATH, PLAYER_FILE)
    bpy.ops.import_scene.gltf(filepath=player_path)
    player_template_obj = bpy.context.active_object
    player_template_obj.name = "player_template"
    print(f"Player '{PLAYER_FILE}' imported as 'player_template'")
except Exception as e:
    print(f"ERROR importing player: {e}")


# Append the Ball from blend file
try:
    obj_name = BALL_OBJECT_NAME_IN_BLEND

    BALL_BLEND_PATH = os.path.join(BASE_PATH, BALL_FILE)

    with bpy.data.libraries.load(BALL_BLEND_PATH, link=False) as (data_from, data_to):
        if obj_name in data_from.objects:
            data_to.objects = [obj_name]
        else:
            print(f"ERROR: Object '{obj_name}' NOT FOUND in {BALL_BLEND_PATH}")

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
        bpy.context.collection.objects.link(ball_obj) # Ensure it is in the main collection
    
    print(f"Ball '{obj_name}' appended as 'ball'")
        
except Exception as e:
    print(f"ERROR appending ball: {e}")


# Standardization
print("Starting standardization...")

if "Court" in bpy.data.objects:
    court_obj = bpy.data.objects["Court"]
    court_obj.location = COURT_LOCATION
    court_obj.rotation_euler = COURT_ROTATION
    court_obj.scale = COURT_SCALE
    print("Court standardized.")
    

    print("Applying additional Z scale to backboards and rims...")
    

    prefixes_to_scale = [
        "Basketball_Backboard",
        "Basketball_Rim"
    ]


    for obj in bpy.data.objects:

        for prefix in prefixes_to_scale:
            if obj.name.startswith(prefix):
                obj.scale.z = obj.scale.z * 1.023
                break 
                
    print("Backboard and rim Z scale modified.")
else:
    print("Object 'Court' not found for standardization.")


if "player_template" in bpy.data.objects:
    player_template_obj = bpy.data.objects["player_template"]
    player_template_obj.location = (25, 2, 0) 
    player_template_obj.rotation_euler = (0, 0, 0)
    player_template_obj.scale = PLAYER_SCALE
    print("Player template standardized.")
else:
    print("Object 'player_template' not found for standardization.")


if "ball" in bpy.data.objects:
    ball_obj = bpy.data.objects["ball"]
    ball_obj.location = (0, 0, 0)
    ball_obj.rotation_euler = (0, 0, 0)
    ball_obj.scale = BALL_SCALE # Use placeholder scale
    print("Ball standardized (adjust scale if necessary).")
else:
    print("Object 'ball' not found for standardization.")


# Player Duplication (With Team Colors)

# Create team materials
print("Creating team materials...")

# Team A Color (Red)
try:
    team_a_mat = bpy.data.materials.new(name="Team_A_Material")
    team_a_mat.use_nodes = True
    team_a_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.0, 0.0, 1.0) # RGBA (Red)
    print("Created Team A material (Red).")
except Exception as e:
    print(f"Error creating Team A material: {e}")

# Team B Color (Blue)
try:
    team_b_mat = bpy.data.materials.new(name="Team_B_Material")
    team_b_mat.use_nodes = True
    team_b_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.0, 0.0, 0.8, 1.0) # RGBA (Blue)
    print("Created Team B material (Blue).")
except Exception as e:
    print(f"Error creating Team B material: {e}")


# Helper Function to find the mesh
def find_first_mesh(obj):
    """
    Recursively searches children of 'obj' 
    to find the first object of type 'MESH'.
    """
    if obj.type == 'MESH':
        return obj
    for child in obj.children:
        found = find_first_mesh(child)
        if found:
            return found
    return None


# Duplicate and assign materials
if "player_template" in bpy.data.objects:
    
   
    root_template_obj = bpy.data.objects["player_template"]
    
    # We use the helper function to find the REAL mesh inside it
    player_mesh_template = find_first_mesh(root_template_obj)
    
    if player_mesh_template is None:
        print("CRITICAL ERROR: No mesh (player) found inside 'player_template'.")
    else:
        print(f"Found mesh template: '{player_mesh_template.name}'")
        
        for i in range(10):
            
            new_player = player_mesh_template.copy()
            new_player.data = player_mesh_template.data.copy() 
            new_player.name = f"player_{i}"
            
            # Assign correct material
            if i < 5:
                new_player.data.materials.clear() 
                new_player.data.materials.append(team_a_mat)
            else:
                new_player.data.materials.clear() 
                new_player.data.materials.append(team_b_mat)
                
            # Link new player to scene
            bpy.context.collection.objects.link(new_player)

        # Hide the entire original template
        root_template_obj.hide_set(True) 
        print("Created 10 player clones and colored by team.")
        
else:
    print("Object 'player_template' (the container) not found, unable to duplicate.")


# Set Up Camera
bpy.ops.object.camera_add(
    location=(47, 25, 120),
    rotation=(0, 0, 0)
)
camera = bpy.context.active_object
camera.name = "TopDownCamera"
bpy.context.scene.camera = camera
print("Camera set.")

print("Scene Import Completed")