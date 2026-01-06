import json
import os
from datasets import load_dataset

def load_sportvu_dataset():
    """
    Load the SportVU dataset from HuggingFace
    Dataset: dcayton/nba_tracking_data_15_16
    
    Returns:
    - dataset: loaded dataset object
    """
    print("Loading SportVU dataset from HuggingFace...")
    print("Dataset: dcayton/nba_tracking_data_15_16")
    
    try:
        # Load the dataset
        dataset = load_dataset("dcayton/nba_tracking_data_15_16", "tiny", split="train", trust_remote_code=True)
        print(f"Dataset loaded successfully: {len(dataset)} records available")
        
        # Display structure of first record
        print("\nFirst record keys:")
        print(dataset[0].keys())
        
        return dataset
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return None

def save_dataset_to_disk(dataset):
    """
    Save the dataset as JSONL format (one JSON object per line)
    
    Args:
    - dataset: the loaded dataset
    """
    if dataset is None:
        print("No dataset to save")
        return
    
    # Save as JSONL - one record per line
    json_path = "nba_tracking_data_tiny.json"
    print(f"\nSaving to JSON (one record per line): {json_path}")
    
    with open(json_path, 'w') as f:
        for i, record in enumerate(dataset):
            json.dump(dict(record), f)
            f.write('\n')
            
            if (i + 1) % 500 == 0:
                print(f"  Saved {i + 1} records...")
    
    print(f"✓ JSON saved successfully: {len(dataset)} records ({os.path.getsize(json_path) / 1024 / 1024:.2f} MB)")
    print(f"✓ Format: JSONL (one JSON object per line)")

# Load the dataset
dataset = load_sportvu_dataset()

# Save to disk
if dataset:
    save_dataset_to_disk(dataset)
    
    # Show sample of the data
    print("\n" + "="*50)
    print("First 3 records preview:")
    print("="*50)
    for i in range(min(3, len(dataset))):
        record_str = json.dumps(dict(dataset[i]))
        print(f"Record {i+1}: {record_str[:150]}...")