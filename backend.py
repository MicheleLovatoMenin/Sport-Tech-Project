from flask import Flask, jsonify
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)

def normalize_coordinates(json_x, json_y):
    """
    LOGICA CORRETTA:
    json_x (0-94) è la lunghezza del campo.
    json_y (0-50) è la larghezza del campo.
    
    Se json_x > 47, il tiro è nella metà campo 'lontana'.
    Per portarlo nella metà campo 'vicina' (0-47):
    - La nostra Y diventa: 94 - json_x
    - La nostra X diventa: json_y (così 3 resta a sinistra e 47 va a destra)
    """
    COURT_LENGTH = 94
    HALF_COURT = 47

    # 1. Gestione Lunghezza (Asse Y nel grafico)
    if json_x > HALF_COURT:
        # Se è oltre metà campo, ribaltiamo verso il canestro vicino
        norm_y = COURT_LENGTH - json_x
    else:
        # Se è già nella metà campo vicina, lo teniamo così
        norm_y = json_x
        
    # 2. Gestione Larghezza (Asse X nel grafico)
    # Usiamo json_y direttamente. 
    # Se json_y è piccolo (es. 3), il tiro sarà a sinistra.
    # Se json_y è grande (es. 47), il tiro sarà a destra.
    norm_x = json_y
    
    return round(norm_x, 2), round(norm_y, 2)

def process_shot_data(raw_data):
    processed_shots = []
    
    # Set per raccogliere i valori univoci per i filtri del front-end
    players = set()
    teams = set()
    matches = set()

    for shot in raw_data:
        # 1. Normalizzazione Coordinate
        norm_x, norm_y = normalize_coordinates(
            shot['shot_location_x'], 
            shot['shot_location_y']
        )

        # 2. Creazione nome partita (Es: MIA @ IND - 2015-12-11)
        match_name = f"{shot['teams']['visitor']['abbreviation']} @ {shot['teams']['home']['abbreviation']} - {shot['game_date']}"
        
        # 3. Identificazione Squadra che ha tirato
        # Confrontiamo possession_team_id con i due team_id nel dizionario 'teams'
        possession_id = int(shot['possession_team_id'])
        team_name = ""
        if possession_id == shot['teams']['home']['team_id']:
            team_name = shot['teams']['home']['name']
        else:
            team_name = shot['teams']['visitor']['name']

        # Creazione del nuovo oggetto processato
        clean_shot = {
            "player": shot['primary_player_name'],
            "team": team_name,
            "match": match_name,
            "x": norm_x,
            "y": norm_y,
            "made": shot['event_type'] == 1, # True se segnato (Cerchio), False se sbagliato (X)
            "period": shot['period'],
            "clock": shot['game_clock']
        }

        processed_shots.append(clean_shot)
        
        # Popolamento set per i menù a tendina
        players.add(shot['primary_player_name'])
        teams.add(team_name)
        matches.add(match_name)

    # Risultato finale strutturato
    output = {
        "filters": {
            "players": sorted(list(players)),
            "teams": sorted(list(teams)),
            "matches": sorted(list(matches))
        },
        "shots": processed_shots
    }
    
    return output

# --- IL PONTE (La rotta API) ---
@app.route('/api/shots')
def get_shots():
    # Carica il file JSON che hai nella cartella
    with open('shots_data.json', 'r') as f:
        data = json.load(f)
    
    # Elabora i dati usando la tua funzione
    result = process_shot_data(data)
    
    # Invia il risultato al browser
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)