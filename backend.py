from flask import Flask, jsonify
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)

def normalize_coordinates(json_x, json_y):

    COURT_LENGTH = 94
    COURT_WIDTH = 50
    HALF_COURT = 47

    # 1. Length Handling (Y-Axis in the chart)
    if json_x > HALF_COURT:
        # If it's beyond half-court, flip the side
        norm_y = COURT_LENGTH - json_x
    else:
        # If it's already in the near half-court, keep it as is
        norm_y = json_x
        
    # 2. Width Handling (X-Axis in the chart)
    # If json_y is small (e.g., 3), the shot will be on the left.
    # If json_y is large (e.g., 47), the shot will be on the right.
    if json_x > HALF_COURT:
        # If it's beyond half-court, flip towards the near basket
        norm_x = json_y
    else:
        # If it's already in the near half-court, keep it as is
        norm_x = COURT_WIDTH - json_y

    
    return round(norm_x, 2), round(norm_y, 2)

def process_shot_data(raw_data):
    processed_shots = []
    
    # Sets to collect unique values for front-end filters
    players = set()
    teams = set()
    matches = set()

    for shot in raw_data:
        # Coordinate Normalization
        norm_x, norm_y = normalize_coordinates(
            shot['shot_location_x'], 
            shot['shot_location_y']
        )

        # Match name creation (E.g: MIA @ IND - 2015-12-11)
        match_name = f"{shot['teams']['visitor']['abbreviation']} @ {shot['teams']['home']['abbreviation']} - {shot['game_date']}"
        
        # Identification of the Shooting Team
        possession_id = int(shot['possession_team_id'])
        team_name = ""
        if possession_id == shot['teams']['home']['team_id']:
            team_name = shot['teams']['home']['name']
        else:
            team_name = shot['teams']['visitor']['name']

        # Creation of the new processed object
        clean_shot = {
            "matchId": shot['game_id'],
            "eventId": shot['event_id'],
            "player": shot['primary_player_name'],
            "team": team_name,
            "match": match_name,
            "x": norm_x,
            "y": norm_y,
            "made": shot['event_type'] == 1,
            "period": shot['period'],
            "clock": shot['game_clock']
        }

        processed_shots.append(clean_shot)
        
        # Populating sets for dropdown menus
        players.add(shot['primary_player_name'])
        teams.add(team_name)
        matches.add(match_name)

    # Final structured result
    output = {
        "filters": {
            "players": sorted(list(players)),
            "teams": sorted(list(teams)),
            "matches": sorted(list(matches))
        },
        "shots": processed_shots
    }
    
    return output

# API route
@app.route('/api/shots')
def get_shots():
    # Load the JSON file located in the folder
    with open('shots_data.json', 'r') as f:
        data = json.load(f)
    
    # Process data using your function
    result = process_shot_data(data)
    
    # Send the result to the browser
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)