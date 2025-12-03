import json

input_file = "nba_tracking_data_tiny.json"
output_file = "dataset_3pt.json"

def filter_heavy_json():
    print(f"Inizio elaborazione stream di: {input_file}")
    
    count_saved = 0
    count_processed = 0
    
    # Apriamo il file di input in lettura e l'output in scrittura
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_file, 'w', encoding='utf-8') as f_out:
        
        # Iniziamo manualmente una lista JSON nel file di output
        f_out.write('[\n')
        first_entry = True

        # Iteriamo sul file una riga alla volta (non carica tutto in memoria)
        for line in f_in:
            line = line.strip()
            
            # Saltiamo righe vuote o parentesi quadre isolate (inizio/fine lista)
            if not line or line == '[' or line == ']':
                continue
            
            # Se la riga finisce con una virgola (tipico delle liste), la rimuoviamo per il parsing
            if line.endswith(','):
                line = line[:-1]

            try:
                # Parsing della singola riga (singolo evento)
                row = json.loads(line)
                count_processed += 1
                
                # --- LOGICA DI FILTRO ---
                event_info = row.get('event_info', {})
                desc_home = str(event_info.get('desc_home', ''))
                desc_away = str(event_info.get('desc_away', ''))

                if "3PT" in desc_home or "3PT" in desc_away:
                    # Gestione della virgola per il file di output
                    if not first_entry:
                        f_out.write(',\n')
                    
                    # Scriviamo direttamente nel file di uscita
                    json.dump(row, f_out)
                    first_entry = False
                    count_saved += 1
                # --- FINE LOGICA ---

            except json.JSONDecodeError:
                # Se una riga è corrotta, la saltiamo senza fermare tutto
                continue
            
            # (Opzionale) Feedback ogni 10.000 righe processate
            if count_processed % 10000 == 0:
                print(f"Processate {count_processed} righe... (Trovate {count_saved} triple)")

        # Chiudiamo la lista JSON nel file di output
        f_out.write('\n]')

    print("---")
    print(f"Completato.")
    print(f"Totale eventi processati: {count_processed}")
    print(f"Eventi 3PT salvati: {count_saved}")
    print(f"File salvato in: {output_file}")

if __name__ == "__main__":
    filter_heavy_json()