import bpy
import pandas as pd
import time # Per misurare il tempo

# --- 0. Impostazioni Animazione ---

# Il percorso al tuo file CSV
CSV_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\Sport-Tech-Project\sportvu_tracking_complete.csv"

# L'ID dell'evento che vogliamo isolare e animare
EVENT_ID_TO_ANIMATE = 2

# Flag per performance: disabilita l'undo durante l'inserimento
# Rende l'inserimento di migliaia di keyframe MOLTO più veloce
# (Lo riattiveremo alla fine)
bpy.context.preferences.edit.use_global_undo = False

print("--- INIZIO FASE 3: Animazione ---")
start_time = time.time()

try:
    # --- 1. Caricamento e Filtro Dati ---
    print(f"Caricamento dati da {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"ERRORE CRITICO: File non trovato. Controlla il percorso: {CSV_PATH}")
        raise
        
    print(f"Dati caricati. Filtro per event_id == {EVENT_ID_TO_ANIMATE}...")
    
    # Filtra il segmento di dati che ci interessa
    segment_df = df[df['event_id'] == EVENT_ID_TO_ANIMATE].copy()
    
    if segment_df.empty:
        print(f"ERRORE CRITICO: Nessun dato trovato per event_id == {EVENT_ID_TO_ANIMATE}.")
        raise ValueError("Segmento dati vuoto.")
        
    # Ottieni il numero di fotogrammi (righe) in questo evento
    num_frames = len(segment_df)
    print(f"Segmento trovato: {num_frames} fotogrammi (righe) da animare.")

    # Converti in un formato più veloce per il loop (lista di dizionari)
    segment_data = segment_df.to_dict('records')

    # --- 2. Preparazione Scena Blender ---
    
    # Imposta la durata dell'animazione nella timeline di Blender
    # (i frame iniziano da 0)
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = num_frames - 1

    # Ottieni i riferimenti agli oggetti che dobbiamo animare
    print("Recupero oggetti dalla scena (palla e giocatori)...")
    
    ball_obj = bpy.data.objects.get("ball")
    if not ball_obj:
        print("ERRORE: Oggetto 'ball' non trovato. Hai eseguito la Fase 2?")
        raise ReferenceError("Oggetto 'ball' non trovato.")
        
    player_objs = []
    for i in range(10):
        player = bpy.data.objects.get(f"player_{i}")
        if not player:
            print(f"ERRORE: Oggetto 'player_{i}' non trovato. Hai eseguito la Fase 2?")
            raise ReferenceError(f"Oggetto 'player_{i}' non trovato.")
        player_objs.append(player)

    print("Oggetti trovati. Inizio inserimento keyframe...")

    # --- 3. Il Ciclo di Animazione ---
    # Questo è il cuore del processo.
    
    for frame_index, row_data in enumerate(segment_data):
        
        # Stampa un aggiornamento ogni 50 frame
        if frame_index % 50 == 0:
            print(f"Elaborazione frame {frame_index} / {num_frames}...")

        # 1. Anima la Palla
        ball_x = row_data['ball_x'] # Lunghezza 0-94
        ball_y = row_data['ball_y'] # Larghezza 0-50
        ball_z = row_data['ball_z']

        # INVERTI X e Y qui!
        # Metti la larghezza (ball_y) sull'asse X di Blender
        # Metti la lunghezza (ball_x) sull'asse Y di Blender
        ball_obj.location = (ball_y, ball_x, ball_z) # <-- MODIFICATO
        ball_obj.keyframe_insert(data_path="location", frame=frame_index)

        # 2. Anima i 10 Giocatori
        for i in range(10):
            player_obj = player_objs[i]
            
            player_x = row_data[f'player_{i}_x'] # Lunghezza 0-94
            player_y = row_data[f'player_{i}_y'] # Larghezza 0-50
            player_z = row_data[f'player_{i}_z'] 
            
            # INVERTI X e Y anche qui!
            player_obj.location = (player_y, player_x, player_z) # <-- MODIFICATO
            player_obj.keyframe_insert(data_path="location", frame=frame_index)

    # --- 4. Conclusione ---
    end_time = time.time()
    print("\n--- ANIMAZIONE COMPLETATA! ---")
    print(f"Inseriti keyframe per {num_frames} fotogrammi per 11 oggetti.")
    print(f"Tempo totale: {end_time - start_time:.2f} secondi.")
    
    # Riporta la timeline all'inizio
    bpy.context.scene.frame_set(0)

except Exception as e:
    print(f"\n--- ERRORE DURANTE L'ANIMAZIONE ---")
    print(f"Dettagli: {e}")

finally:
    # RI-ABILITA l'undo, indipendentemente da successo o fallimento
    bpy.context.preferences.edit.use_global_undo = True
    print("Global Undo riabilitato.")