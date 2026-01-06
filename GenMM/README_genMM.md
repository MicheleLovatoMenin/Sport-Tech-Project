# GenMM: Generative Motion Matching Pipeline

This directory contains the advanced pipeline for **Neural Motion In-Betweening**. Unlike the standard linear blending, this module uses a deep learning model (GenMM) to synthesize physically valid transitions between animation statesand robotic movements.

---

## Installation & Dependency Setup

Before running the pipeline, you must ensure that Blender's internal Python environment has the necessary deep learning libraries installed.

### 1. Get the Source Code
First, download the latest source code `.zip` from the official GenMM page (*https://github.com/wyysf-98/GenMM/releases*) and install the addon in Blender.

### 2. Configure `requirements.txt`
The provided `requirements.txt` file in this directory is configured for modern NVIDIA GPUs using **CUDA 12.1**.

> **Note:** If you are using older hardware or drivers (e.g., CUDA 11.8), simply open the text file and replace all instances of `cu121` with `cu118`.

### 3. Install Dependencies
Blender’s embedded Python environment does not have a native console interface. To install the libraries correctly, you must run the installation from your system's terminal (Command Prompt or PowerShell) pointing specifically to Blender's Python executable.

Run the following command (adjusting the path to your specific Blender version/installation):

```bash
# Windows Example
"C:\Program Files\Blender Foundation\Blender 4.2\4.2\python\bin\python.exe" -m pip install -r requirements.txt
```
## The Pipeline (Step-by-Step)

The synthesis process is broken down into 6 distinct batch scripts to ensure stability and modularity. Follow strictly in order:

### 0️⃣ Setup & Gap Creation
**Script:** `0_rule_based_genMM.py`
* **Function:** Generates the base scene using sparse tracking data.
* **Logic:** Instead of blending animations immediately, it leaves intentional **10-frame gaps** between distinct actions (e.g., *Dribble* → *Shot*).
* **Output:** A Blender scene with "holes" in the timeline.

### 1️⃣ Data Extraction
**Script:** `1_extract_gap_data.py`
* **Function:** Analyzes the NLA tracks and identifies every gap.
* **Output:** Generates `gap_export.json`, containing the start/end frames and animation metadata for each gap.

### 2️⃣ Laboratory Isolation
**Script:** `2_laboratory_batch.py`
* **Function:** Creates a separate, isolated `.blend` file (a "Laboratory") for each detected gap.
* **Logic:** It sets up the "Pre" and "Post" animation clips with the correct spacing, preparing the environment for the AI.
* **Output:** A folder `temp_labs/` filled with `lab_gap_XXX.blend` files.

### 3️⃣ Neural Synthesis (The Core)
**Script:** `3_genmm_processor.py`
* **Function:** Iterates through every laboratory file and runs the **GenMM** model.
* **Logic:** The AI looks at the *Pre* and *Post* frames and synthesizes the missing motion in the middle. It then uses **Rokoko** to retarget the generated skeleton back onto the original armature.
* **Output:** Saves the processed files as `_filled.blend`.

### 4️⃣ Harvesting Results
**Script:** `4_export_gap_batch.py`
* **Function:** Opens the filled laboratory files and extracts *only* the synthesized 10-frame action strips.
* **Output:** Saves these clean clips into `gap_libraries/`.

### 5️⃣ Final Injection
**Before running this:** Re-run `0_rule_based_genMM.py` to ensure a clean target scene.

**Script:** `5_inject_batch.py`
* **Function:** Reads the generated clips from the library and injects them precisely into the gaps of the main timeline.
* **Logic:** Applies Y-axis warping to align the root height of the AI motion with the original tracking data.
---

## Directory Structure created

* `temp_labs/`: Temporary work files for each gap. Can be deleted after processing.
* `gap_libraries/`: Contains the final, clean `.blend` libraries of the synthesized movements.
* `gap_export.json`: The "map" used to coordinate all scripts.
