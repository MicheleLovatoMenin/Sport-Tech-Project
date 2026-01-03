# 🏀 3D Reconstruction in Basketball: A Realistic Virtualisation of Basketball 3-Point Shooting from Sparse Open-Source Data

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Blender](https://img.shields.io/badge/Blender-4.2-orange)
![Flask](https://img.shields.io/badge/Flask-2.x-lightgrey)
![Status](https://img.shields.io/badge/Status-Academic%20Prototype-success)

**Authors:** Tommaso Ballarini & Michele Lovato Menin

## Overview

This project presents a novel pipeline for the **realistic virtualization of basketball 3-point shooting** using *sparse* open-source data.

Commercial leaders in sports analytics (like Genius Sports or Beyond Sports) typically rely on expensive, hardware-intensive optical tracking systems to extract dense skeletal data. Our approach democratizes this technology by synthesizing realistic 3D actions from **single-point 2D tracking data** (X, Y coordinates of players and X, Y and Z of the ball) from the NBA 2015-2016 season.

By leveraging ball dynamics to logically infer missing player motion, we transform raw tracking data into coherent, smooth 3D animations without the need for proprietary datasets.

## Key Features

* **Sparse-to-Dense Reconstruction:** Generates complex 3D representations using only 2D positions and open-source datasets.
* **Motion Smoothing:** Implements a blend script to ensure fluid transitions between animation states.
* **Interactive Web Dashboard:** A Flask-based web application allowing users to filter shots (Player, Team, Game) and view results on a 2D tactical board.
* **Immersive 3D Viewer:** View any reconstructed shot from a 360° controllable camera angle directly in the browser.
* **Historical Reenactment:** Recreates specific actions from the 2015-16 NBA season using the SportVu dataset.

---

## Architecture & Pipeline

The system operates on a rule-based logic implementation that maps 2D coordinates to a library of MOCAP-style animations.

```mermaid
graph TD
    A[SportVu Dataset] -->|shot_frame.py| B(shot_metadata.json)
    B -->|rule_based_blend.py| C[Smooth Animation Sequence]
    C -->|export.py| D[Smooth Animation GLB]
    D --> E[Web Dashboard]
```

### 1. Data Extraction & Logic
We use the **SportVu** dataset (HuggingFace).

* **Standard Extraction (`shot_frame.py`):**
  This script iterates through game data to identify 3-point shot events. You have to choose "game_id" and "event_id". It extracts the "shot frame", the shooter's ID, and the XY coordinates of the player and XYZ coordinates of the ball. It assumes the shooter belongs to the team currently labeled with "possession".

* **Robust Fallback (`shot_frame_adj.py`):**
  We developed this adjusted script to handle data inconsistencies, such as timestamp misalignments (e.g., a shot labeled at event index 189 that actually occurs at 188). Unlike the standard script, this version scans **all 10 players** on the court—rather than just the offensive 5—to identify the true shooter based on proximity to the ball. This ensures the correct player is animated even if the possession label is flawed.

**Output:** Both scripts generate `shot_metadata.json` (for the current specific action) and append the entry to `shots_data.json` (the cumulative database used by the frontend).

### 2. Rule-Based Reconstruction (Blender)
The core virtualization takes place in **Blender** using the `rule_based.py` script.
* **Action Window:** The system generates a coherent 5-second sequence around the shot frame: **3 seconds pre-shot** and **2 seconds post-shot**.
* **Logic:** It maps the sparse 2D coordinates to a library of MOCAP-style animations using ball and speed constraints. Crucially, the script places these animation blocks onto the timeline using a 5-frame blend to create smooth transitions.

### 3. Export (DA SISTEMARE)
* **Result:** The system synthesizes fluid, physically realistic transitions between the pre-shot dribble, the jump shot, and the landing, creating a continuous 3D mesh. The final result is exported as a `.glb` file.

### 4. Web Visualization
* The final output is a `.glb` file.
* The web platform reads `shots_data.json`to populate the dashboard and renders the 3D files.

## Installation

### Prerequisites
* **Python 3.8+**
* **Blender 4.2** (This specific version is only needed if you wish to use GenMM)
* **Dependencies:**
    Install the required Python packages using pip:
    ```bash
    pip install -r requirements.txt
    ```

### Dataset Setup
1.  **Download Data:** Acquire the **NBA Tracking Data (2015-16)** from HuggingFace:
    [HuggingFace Dataset Link](https://huggingface.co/datasets/dcayton/nba_tracking_data_15_16?)
    For simplicity, you can install the tiny format (only 5 matches).
3.  **Placement:** Place the dataset in the root directory (or ensure the paths in `shot_frame.py` and `rule_based_blend.py` match your local folder structure).

---

## Usage

This project supports two modes: **User Mode** (for visualizing existing data) and **Developer Mode** (for generating new 3D animations).

### User Mode (Web Visualization)
To explore the interactive dashboard and view previously reconstructed shots:

1.  **Start the Backend:**
    ```bash
    python backend.py
    ```
2.  **Start the Frontend:**
    ```bash
    python frontend.py
    ```
3.  **Access the Dashboard:**
   
    Open your browser to `http://localhost:5000` (or the port specified in the terminal). You will see a 2D view of the court. Markers indicate shot locations: **X** (Missed) and **O** (Made). Use the dropdown menu to filter shots by Player, Team, or Game ID. Click on any marker to load the **360° interactive 3D viewer** for that specific action.



https://github.com/user-attachments/assets/e8ed39c1-40a9-4b9b-b524-6057dbe1bdd2



### Developer Mode
To reconstruct a new action from raw data, follow this pipeline:

#### Step A: Data Extraction
Run the extraction script on python to identify the shot frame and isolate tracking data.
```bash
python shot_frame.py
```

* **Robust Fallback (`shot_frame_adj.py`):**
    Use this script when the action data is misaligned (e.g., the "3pt shot" label appears at event index 189, but the actual data is at 188).
    * *Why should I use it?* Sometimes the dataset's possession label is incorrect for the specific frame.
    * *How it works:* Unlike the standard script which looks for the shooter among the 5 offensive players, this script scans **all 10 players** on the court. It identifies the shooter based on proximity to the ball, ensuring the correct player is selected even if the possession data is flawed.

**Output:** Both scripts update `shot_metadata.json` (current action data) and append the result to `shots_data.json` (historical database).

#### Step B: Blender Reconstruction
1.  **Open Blender:** Launch blender manually.
2.  **Load Environment:** Open the `basket_ambient.blend` file.
3.  **Run Script:** run `rule_based_blend.py`on blender (Blender → Workspace "Scripting" → Open script → Run).
    * *Process:* This script reads the `shot_metadata.json` file generated in Step A.
    * *Logic:* It constructs a **5-second animation window** (3 seconds before the shot, 2 seconds after). It places the animations on the timeline using rule-based logic and creates smooth transitions between animations.

#### Step C: Export (DA SISTEMARE)
Once the base animation is arranged in Blender, run the smoothing script:
```bash
python export.py
```

* **Final Output:** The script exports the finished animation as a `.glb` file into the web assets folder, ready for the dashboard.

---

## Additional materials

The repository includes three specialized directories that handle advanced synthesis, data validation, and environment setup:

### 1. `GenMM/` (Advanced Motion Synthesis)
This folder contains the tools and resources for the **Generative Motion Matching** pipeline, which replaces simple linear interpolation with neural motion synthesis.

* **Workflow Adjustment:** To use this pipeline, replace the standard blending script with **`rule_based_genMM.py`**.
* **The Logic:** Unlike the standard approach, `rule_based_genMM.py` constructs the timeline by placing animation blocks with intentional **10-frame gaps** between distinct movements (e.g., transition from dribble to shot).
* **Motion In-Betweening:** These gaps are then processed by the GenMM algorithms `genMM.py` which generate physically valid "in-between" frames. This eliminates the robotic feel of standard blending and ensures smooth transitions. Despite that, it's preferable to use the "normal" blending, since 10 frames are not enough for good motion in-betweening, but at the same time, if we increare the number of frames, some animations are excluded, creating gaps with different intervals that make it difficult to perform standardised motion-in-between.

### 2. `Comparison/` (Raw Data Visualization)
This directory contains tools to validate the raw SportVu data against our 3D reconstructions.

* **Script:** `visualize_raw_tracking.py` (run within Blender).
* **Function:** By selecting a `game_id` and `event_id`, users can visualize the exact tracking data from the source file.
* **Visual Output:** The scene renders **all 10 players and the ball** moving according to their raw X/Y coordinates. Note that in this mode, player meshes are **static** (no skeletal animation) and simply "slide" across the court. This serves as a baseline to demonstrate the value added by our reconstruction pipeline.

### 3. `environment_creation/`
These scripts were used to build the foundational Blender environment (`Basket_ambient.blend`) and can be used to regenerate or modify the scene.

* **`setup_in_place.py`:** Batch loads the MOCAP animation library into Blender, configuring them as "in-place" animations ready for the rule-based logic.
* **`environment_creation.py`:** Procedurally generates the 3D environment, including the basketball court geometry, ball object initialization, and global scaling factors.

---

## References

### Motion Synthesis
The smoothing algorithm utilizes **Generative Motion Matching** to ensure realistic human movement.

> **Li, W., Chen, X., Li, P., Sorkine-Hornung, O., & Chen, B. (2023).**
> *Example-based motion synthesis via generative motion matching.*
> ACM Transactions on Graphics (TOG), 42(4), 1-12.

---

## License
This is an open-source academic project.

