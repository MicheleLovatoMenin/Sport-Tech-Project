import bpy
import os

# --- CONFIGURATION ---
BASE_PATH = r"C:\Users\miklo\Desktop\Sport-Tech-Project"
FBX_FOLDER_PATH = os.path.join(BASE_PATH, "animations/animations2")
TARGET_CHAR_NAME = "Armature" 
ROOT_BONE_NAME = "mixamorig:Hips"

def make_animation_in_place(armature, root_bone_name):
    """
    Removes XYZ translations from the root bone to make the animation in-place
    """
    if not armature.animation_data or not armature.animation_data.action:
        return

    action = armature.animation_data.action

    # Find root bone animation curves
    for fcurve in action.fcurves:
        if f'pose.bones["{root_bone_name}"].location' in fcurve.data_path:
            if fcurve.array_index in [0, 2]:  # 0=X, 2=Z
                action.fcurves.remove(fcurve)

    print(f"  -> Animation converted to in-place (removed XZ movement from '{root_bone_name}')")

def run_batch_retargeting():
    if TARGET_CHAR_NAME not in bpy.data.objects:
        print(f"CRITICAL ERROR: Target object '{TARGET_CHAR_NAME}' not found")
        return
    target_armature = bpy.data.objects[TARGET_CHAR_NAME]

    try:
        files = [f for f in os.listdir(FBX_FOLDER_PATH) if f.lower().endswith(".fbx")]
    except FileNotFoundError:
        print("ERROR: The specified folder does not exist.")
        return

    if not files:
        print("No FBX files found!")
        return

    print(f"Starting processing of {len(files)} animations...")

    # Ensure target is selected and active
    bpy.ops.object.select_all(action='DESELECT')
    target_armature.select_set(True)
    bpy.context.view_layer.objects.active = target_armature

    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    for file_name in files:
        filepath = os.path.join(FBX_FOLDER_PATH, file_name)
        action_name = file_name.replace(".fbx", "")

        print(f"\n--- Processing: {action_name} ---")

        # Import FBX
        bpy.ops.import_scene.fbx(filepath=filepath, force_connect_children=True, automatic_bone_orientation=True)

        source_armature = None
        for obj in bpy.context.selected_objects:
            if obj.type == 'ARMATURE':
                source_armature = obj
                break

        if not source_armature:
            print("  ERROR: No armature found in the imported file.")
            continue

        source_armature.name = "Source_Temp_Armature"

        # Rokoko Setup
        try:
            bpy.context.scene.rsl_retargeting_armature_target = target_armature
            bpy.context.scene.rsl_retargeting_armature_source = source_armature

            print("  Building Bone List...")
            bpy.ops.rsl.build_bone_list()

            print("  Executing Retargeting...")
            bpy.ops.rsl.retarget_animation()

        except Exception as e:
            print(f"  ERROR during Rokoko operation: {e}")
            bpy.data.objects.remove(source_armature, do_unlink=True)
            continue

        # Convert to in-place animation
        make_animation_in_place(target_armature, ROOT_BONE_NAME)

        # Save, Copy, and Move Animation
        if target_armature.animation_data and target_armature.animation_data.action:

            raw_action = target_armature.animation_data.action

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

            # Cleanup
            target_armature.animation_data.action = None
            bpy.data.actions.remove(raw_action)

            print(f"  SUCCESS: Action '{action_name}' saved and archived.")

        else:
            print("  WARNING: Retargeting finished but no action found on target.")

        # Cleanup Source
        bpy.data.objects.remove(source_armature, do_unlink=True)

    # Re-enable all NLA tracks at the end
    if target_armature.animation_data:
        for track in target_armature.animation_data.nla_tracks:
            track.mute = False

    print("\n--- ALL COMPLETED ---")

run_batch_retargeting()