import bpy
import os

BASE_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH"

COURT_FILE = "basketball_court.glb"

PLAYER_FILE = "low_poly_male_base_mesh.glb"



# Il file .blend è in una sottocartella, quindi ho specificato il percorso completo

BALL_BLEND_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\basketballball_v31_cycles\basketballball_v3.1_Cycles.blend"



# Nome oggetto palla 

BALL_OBJECT_NAME_IN_BLEND = "bbc_ball_body"



# Valori di correzione 

COURT_SCALE = (3.355, 3.355, 3.355)

PLAYER_SCALE = (3.48, 3.48, 3.48)

BALL_SCALE = (3.3, 3.3, 3.3) 



# ** NOTA IMPORTANTE SULLA POSIZIONE **

# I dati CSV (0-94 piedi) non partono da 0 al centro, ma da un angolo.

# Per far combaciare i dati, il campo (che ora è 94x50) 

# deve essere centrato a (47, 25, 0).

COURT_LOCATION = (25, 47, 0)

COURT_ROTATION = (0, 0, 0)





# --- 1. Pulizia della Scena ---

if bpy.data.objects:

    bpy.ops.object.select_all(action='SELECT')

    bpy.ops.object.delete()



# --- 2. Importazione Asset ---



# --- A. Importa il Campo da Basket (.glb) ---

try:

    court_path = os.path.join(BASE_PATH, COURT_FILE)

    bpy.ops.import_scene.gltf(filepath=court_path)

    court_obj = bpy.context.active_object

    court_obj.name = "Court"

    print(f"Campo '{COURT_FILE}' importato come 'Court'")

except Exception as e:

    print(f"ERRORE importazione campo: {e}")



# --- B. Importa il Giocatore Template (.glb) ---

try:

    player_path = os.path.join(BASE_PATH, PLAYER_FILE)

    bpy.ops.import_scene.gltf(filepath=player_path)

    player_template_obj = bpy.context.active_object

    player_template_obj.name = "player_template"

    print(f"Giocatore '{PLAYER_FILE}' importato come 'player_template'")

except Exception as e:

    print(f"ERRORE importazione giocatore: {e}")



# --- C. "Appendi" la Palla dal file (.blend) ---

try:

    obj_name = BALL_OBJECT_NAME_IN_BLEND

    

    with bpy.data.libraries.load(BALL_BLEND_PATH, link=False) as (data_from, data_to):

        # Cerca l'oggetto palla nella sezione 'objects' del file .blend

        if obj_name in data_from.objects:

            data_to.objects = [obj_name]

        else:

            print(f"ERRORE: Oggetto '{obj_name}' NON TROVATO in {BALL_BLEND_PATH}")



    # Ora "istanzia" l'oggetto palla nella scena

    # (A volte Blender aggiunge .001 se il nome esiste già)

    if obj_name in bpy.data.objects:

        ball_obj = bpy.data.objects[obj_name]

    elif f"{obj_name}.001" in bpy.data.objects:

        ball_obj = bpy.data.objects[f"{obj_name}.001"]

    else:

        # Se non lo trova, potrebbe essere già nella scena ma non selezionato

        # Come ultima risorsa, lo cerchiamo

        found = False

        for obj in bpy.context.scene.objects:

            if obj.name.startswith(obj_name):

                ball_obj = obj

                found = True

                break

        if not found:

             raise Exception(f"Impossibile trovare l'oggetto palla {obj_name} dopo l'append.")



    ball_obj.name = "ball" # Rinomina standard

    bpy.context.collection.objects.link(ball_obj) # Assicura sia nella collezione principale

    print(f"Palla '{obj_name}' appesa come 'ball'")

        

except Exception as e:

    print(f"ERRORE append palla: {e}")





# --- 3. Standardizzazione (CON I TUOI VALORI) ---

print("Inizio standardizzazione...")



if "Court" in bpy.data.objects:

    court_obj = bpy.data.objects["Court"]

    court_obj.location = COURT_LOCATION

    court_obj.rotation_euler = COURT_ROTATION

    court_obj.scale = COURT_SCALE

    print("Campo standardizzato.")

    

    # --- Modifica aggiuntiva per Tabelloni e Canestri ---

    print("Applico scala Z aggiuntiva a tabelloni e canestri...")

    

    # Lista dei prefissi dei nomi degli oggetti da modificare

    prefixes_to_scale = [

        "Basketball_Backboard",

        "Basketball_Rim"

    ]



    # Itera su TUTTI gli oggetti presenti nella scena

    for obj in bpy.data.objects:

        # Controlla se il nome dell'oggetto inizia con uno dei prefissi

        for prefix in prefixes_to_scale:

            if obj.name.startswith(prefix):

                # Trovato! Applica la scala Z *moltiplicandola* a quella esistente

                # Questo è fondamentale: moltiplichi 3.355 * 1.05

                obj.scale.z = obj.scale.z * 1.023

                # Passa all'oggetto successivo

                break 

                

    print("Scala Z di tabelloni e canestri modificata.")

else:

    print("Oggetto 'Court' non trovato per la standardizzazione.")



    





if "player_template" in bpy.data.objects:

    player_template_obj = bpy.data.objects["player_template"]

    player_template_obj.location = (25, 2, 0) 

    player_template_obj.rotation_euler = (0, 0, 0)

    player_template_obj.scale = PLAYER_SCALE

    print("Template giocatore standardizzato.")

else:

    print("Oggetto 'player_template' non trovato per la standardizzazione.")



if "ball" in bpy.data.objects:

    ball_obj = bpy.data.objects["ball"]

    ball_obj.location = (0, 0, 0)

    ball_obj.rotation_euler = (0, 0, 0)

    ball_obj.scale = BALL_SCALE # Usa la scala segnaposto

    print("Palla standardizzata (aggiusta la scala se necessario).")

else:

    print("Oggetto 'ball' non trovato per la standardizzazione.")





# --- 4. Duplicazione Giocatori (Con Colori Squadra E FIX) ---



# --- A. Crea i materiali per le squadre ---

print("Creazione materiali squadre...")



# Colore Squadra A (Rosso)

try:

    team_a_mat = bpy.data.materials.new(name="Team_A_Material")

    team_a_mat.use_nodes = True

    team_a_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.0, 0.0, 1.0) # RGBA (Rosso)

    print("Creato materiale Team A (Rosso).")

except Exception as e:

    print(f"Errore creazione materiale Team A: {e}")



# Colore Squadra B (Blu)

try:

    team_b_mat = bpy.data.materials.new(name="Team_B_Material")

    team_b_mat.use_nodes = True

    team_b_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.0, 0.0, 0.8, 1.0) # RGBA (Blu)

    print("Creato materiale Team B (Blu).")

except Exception as e:

    print(f"Errore creazione materiale Team B: {e}")



# --- Funzione Helper per trovare la mesh ---

def find_first_mesh(obj):

    """

    Cerca ricorsivamente nei figli di 'obj' 

    per trovare il primo oggetto di tipo 'MESH'.

    """

    if obj.type == 'MESH':

        return obj

    for child in obj.children:

        found = find_first_mesh(child)

        if found:

            return found

    return None



# --- B. Duplica e assegna i materiali ---

if "player_template" in bpy.data.objects:

    

    # Questo è il contenitore "Empty" (es. 'player_template')

    root_template_obj = bpy.data.objects["player_template"]

    

    # Usiamo la funzione helper per trovare la VERA mesh al suo interno

    player_mesh_template = find_first_mesh(root_template_obj)

    

    if player_mesh_template is None:

        print("ERRORE CRITICO: Non è stata trovata nessuna mesh (giocatore) all'interno di 'player_template'.")

    else:

        print(f"Trovata mesh template: '{player_mesh_template.name}'")

        

        for i in range(10):

            # Copiamo l'oggetto mesh, NON l'empty

            new_player = player_mesh_template.copy()

            

            # Copiamo i dati della mesh (fondamentale per materiali unici)

            new_player.data = player_mesh_template.data.copy() 

            new_player.name = f"player_{i}"

            

            # Assegna il materiale corretto

            if i < 5:

                # Squadra A (Giocatori 0-4)

                new_player.data.materials.clear() 

                new_player.data.materials.append(team_a_mat)

            else:

                # Squadra B (Giocatori 5-9)

                new_player.data.materials.clear() 

                new_player.data.materials.append(team_b_mat)

                

            # Collega il nuovo giocatore alla scena

            bpy.context.collection.objects.link(new_player)



        # Nascondi l'intero template originale (l'Empty e tutti i suoi figli)

        root_template_obj.hide_set(True) 

        print("Creati 10 cloni di giocatori e colorati per squadra.")

        

else:

    print("Oggetto 'player_template' (il contenitore) non trovato, impossibile duplicare.")



# --- 5. Imposta la Telecamera ---

bpy.ops.object.camera_add(

    location=(47, 25, 120), # Centrata sul campo (94/2, 50/2) e 120 in alto

    rotation=(0, 0, 0) # Guarda dritto in basso

)

camera = bpy.context.active_object

camera.name = "TopDownCamera"

bpy.context.scene.camera = camera

print("Telecamera impostata.")



print("--- Fase 2 (Importazione Scena) COMPLETATA ---")