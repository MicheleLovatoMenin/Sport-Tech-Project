import json
import os

# --- IMPOSTAZIONI OBBLIGATORIE ---

# Modifica questo percorso per puntare al tuo file .json scaricato
JSON_FILE_PATH = r"D:\VS CODE DIRECTORY\PYTHON\SPORT_TECH\nba_tracking_data_tiny.json" 

# 1. Esegui lo script una prima volta. Ti mostrerà tutti i Game ID.
# 2. Scegli un Game ID dalla lista e inseriscilo qui.
TARGET_GAME_ID = "0021500333" # <-- ESEMPIO, CAMBIA QUESTO VALORE

"""
- 0021500115 philadelphia vs toronto
- 0021500230 new york vs miami
- 0021500292 chicago vs charlotte
- 0021500333 indiana vs miami
- 0021500648 new york vs clippers 
  """

# 3. Inserisci qui l'ID dell'evento che vuoi cercare IN QUELLA PARTITA
TARGET_EVENT_ID = "367" # <-- ESEMPIO, CAMBIA QUESTO VALORE

# --- FINE IMPOSTAZIONI ---


def find_unique_game_ids(file_path):
    """
    Legge il file JSONL riga per riga e restituisce una lista 
    ordinata di tutti i 'gameid' unici trovati.
    """
    if not os.path.exists(file_path):
        print(f"ERRORE (find_unique_game_ids): File non trovato: {file_path}")
        return []
    
    unique_games = set()
    print(f"Scansione del file per i Game ID unici in: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                try:
                    event = json.loads(line)
                    # Aggiunge il gameid al set (i duplicati vengono ignorati)
                    if 'gameid' in event:
                        unique_games.add(event['gameid'])
                except json.JSONDecodeError:
                    # Ignora righe malformate
                    print(f"Attenzione: riga {i+1} saltata (JSON non valido).")
                    pass
    except Exception as e:
        print(f"Errore imprevisto durante la lettura dei gameid: {e}")
        return []
    
    return sorted(list(unique_games))


def find_event_details(file_path, target_game_id, target_event_id):
    """
    Legge un file JSONL riga per riga e cerca una combinazione specifica
    di 'gameid' E 'event_id'.
    
    Restituisce un dizionario completo se trova la corrispondenza.
    """
    print(f"\nApertura del file per la ricerca: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"ERRORE: File non trovato al percorso: {file_path}")
        return None

    # Convertiamo gli ID target in stringhe per un confronto sicuro
    target_game_id_str = str(target_game_id)
    target_event_id_str = str(target_event_id)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                try:
                    event = json.loads(line)
                    
                    # --- FILTRO AGGIUNTIVO ---
                    # 1. Controlla se 'gameid' esiste
                    if 'gameid' not in event:
                        continue # Riga non valida, salta
                    
                    # 2. Confronta il gameid (molto più veloce)
                    current_game_id = str(event['gameid'])
                    if current_game_id != target_game_id_str:
                        continue # Non è la partita che cerchiamo, salta alla prossima riga
                    
                    # --- FINE FILTRO ---

                    # Se siamo qui, il GAME_ID corrisponde.
                    # Ora facciamo i controlli sull'evento, come prima.
                    
                    if 'event_info' in event and isinstance(event['event_info'], dict) and \
                       'visitor' in event and isinstance(event['visitor'], dict) and \
                       'home' in event and isinstance(event['home'], dict) and \
                       'gamedate' in event and \
                       'id' in event['event_info'] and \
                       'desc_home' in event['event_info'] and \
                       'desc_away' in event['event_info'] and \
                       'possession_team_id' in event['event_info'] and \
                       'name' in event['visitor'] and \
                       'teamid' in event['visitor'] and \
                       'name' in event['home'] and \
                       'teamid' in event['home']:
                        
                        # Estrai l'ID evento corrente
                        current_event_id = str(event['event_info']['id'])
                        
                        # 3. Confronta l'ID evento
                        if current_event_id == target_event_id_str:
                            # Trovato! Estrai tutte le informazioni
                            
                            desc_home = event['event_info']['desc_home']
                            desc_away = event['event_info']['desc_away']
                            poss_team_id = event['event_info']['possession_team_id']
                            game_id = event['gameid']
                            game_date = event['gamedate']
                            visitor_name = event['visitor']['name']
                            visitor_id = event['visitor']['teamid']
                            home_name = event['home']['name']
                            home_id = event['home']['teamid']

                            return {
                                "event_desc": {
                                    "home": desc_home,
                                    "away": desc_away
                                },
                                "game_info": {
                                    "gameid": game_id,
                                    "gamedate": game_date,
                                    "home_team_name": home_name,
                                    "home_team_id": home_id,
                                    "visitor_team_name": visitor_name,
                                    "visitor_team_id": visitor_id
                                },
                                "event_specific": {
                                    "possession_team_id": poss_team_id
                                }
                            }
                            
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Ignora righe malformate o che non hanno la struttura attesa
                    pass
    
    except Exception as e:
        print(f"Si è verificato un errore imprevisto durante la lettura del file: {e}")
        return None

    # Se il ciclo finisce senza aver trovato nulla
    return None

# --- Esecuzione dello script ---
if __name__ == "__main__":
    
    # --- NUOVA PARTE: Trova tutti i Game ID ---
    # print("--- Ricerca Game ID unici nel file... ---")
    # game_ids = find_unique_game_ids(JSON_FILE_PATH)
    # if game_ids:
    #     print("✅ Game ID trovati in questo file:")
    #     for gid in game_ids:
    #         print(f"  - {gid}")
    # else:
    #     print("❌ Nessun Game ID trovato o file non accessibile.")
    #     print("Assicurati che JSON_FILE_PATH sia corretto.")
    # print("------------------------------------------")

    # Controlla se le impostazioni sono state modificate
    if TARGET_GAME_ID == "INSERISCI_GAME_ID_QUI" or TARGET_EVENT_ID == "INSERISCI_ID_QUI":
        print("\n--- 🛑 ATTENZIONE ---")
        print("Per favore, apri lo script e modifica le variabili:")
        print("1. 'TARGET_GAME_ID' (scegli un ID dalla lista qui sopra)")
        print("2. 'TARGET_EVENT_ID' (l'ID evento che cerchi per quella partita)")
    else:
        print(f"\n--- Avvio ricerca per Game ID: {TARGET_GAME_ID} E Event ID: {TARGET_EVENT_ID} ---")
        
        # 'dettagli' contiene ora il dizionario annidato
        dettagli = find_event_details(JSON_FILE_PATH, TARGET_GAME_ID, TARGET_EVENT_ID)
        
        print("\n--- Risultato ---")
        if dettagli:
            print(f"✅ Evento {TARGET_EVENT_ID} (Partita {TARGET_GAME_ID}) trovato!")
            print("---------------------------------")
            
            # Stampa le info della partita
            print("INFORMAZIONI SULLA PARTITA:")
            print(f"  Game ID: {dettagli['game_info']['gameid']}")
            print(f"  Data: {dettagli['game_info']['gamedate']}")
            print(f"  Home: {dettagli['game_info']['home_team_name']} (ID: {dettagli['game_info']['home_team_id']})")
            print(f"  Visitor: {dettagli['game_info']['visitor_team_name']} (ID: {dettagli['game_info']['visitor_team_id']})")
            
            # Stampa i dettagli dell'evento
            print("\nDETTAGLI EVENTO:")
            print(f"  Descrizione HOME: {dettagli['event_desc']['home']}")
            print(f"  Descrizione AWAY: {dettagli['event_desc']['away']}")
            print(f"  Possession Team ID: {dettagli['event_specific']['possession_team_id']}")
            
            print("---------------------------------")
        else:
            print(f"❌ ERRORE: Evento con ID {TARGET_EVENT_ID} non trovato per la partita {TARGET_GAME_ID}.")
            print("Controlla che entrambi gli ID siano corretti e presenti nel file.")