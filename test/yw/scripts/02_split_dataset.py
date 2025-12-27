# scripts/02_split_dataset.py
import os
import shutil
import random
from pathlib import Path
from tqdm import tqdm

# --- Configuration ---
# Define the split ratios for train, validation, and test sets.
# The sum should be 1.0.
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1

if TRAIN_RATIO + VAL_RATIO + TEST_RATIO != 1.0:
    raise ValueError("The sum of TRAIN, VAL, and TEST ratios must be 1.0.")

# --- Paths ---
# Assumes the script is run from the project root 'deeplearning-repo-1'
ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = ROOT_DIR / "test" / "yw" / "data" / "processed"
SOURCE_IMAGES_DIR = PROCESSED_DATA_DIR / "images"
SOURCE_LABELS_DIR = PROCESSED_DATA_DIR / "labels"

def split_dataset():
    """
    Main function to split the dataset into training, validation, and test sets.
    It takes the files from `processed/images` and `processed/labels` and distributes
    them into `train`, `val`, and `test` subdirectories within those folders.
    """
    print("Starting dataset splitting...")

    # --- 1. Get list of all images ---
    if not SOURCE_IMAGES_DIR.exists() or not SOURCE_LABELS_DIR.exists():
        print(f"Error: Source directories not found.")
        print(f"Please run the preprocessing script first to generate data in:")
        print(f"- {SOURCE_IMAGES_DIR}")
        print(f"- {SOURCE_LABELS_DIR}")
        return

    image_files = sorted([p for p in SOURCE_IMAGES_DIR.iterdir() if p.is_file()])
    if not image_files:
        print(f"Error: No images found in {SOURCE_IMAGES_DIR}. Cannot split dataset.")
        return
        
    print(f"Found {len(image_files)} total images to split.")

    # --- 2. Shuffle the dataset ---
    random.seed(42) # Use a fixed seed for reproducibility
    random.shuffle(image_files)

    # --- 3. Calculate split indices ---
    total_files = len(image_files)
    train_end = int(total_files * TRAIN_RATIO)
    val_end = int(total_files * (TRAIN_RATIO + VAL_RATIO))

    # --- 4. Create destination directories ---
    sets = {
        "train": image_files[:train_end],
        "val": image_files[train_end:val_end],
        "test": image_files[val_end:]
    }

    # Clean any existing split directories
    for set_name in sets.keys():
        for dir_type in ["images", "labels"]:
            dir_path = PROCESSED_DATA_DIR / dir_type / set_name
            if dir_path.exists():
                shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True)
    
    # --- 5. Copy files to destination ---
    for set_name, files in sets.items():
        print(f"\nProcessing '{set_name}' set ({len(files)} files)...")
        
        # Define destination paths
        dest_images_dir = PROCESSED_DATA_DIR / "images" / set_name
        dest_labels_dir = PROCESSED_DATA_DIR / "labels" / set_name

        for image_path in tqdm(files, desc=f"Copying {set_name} files"):
            label_filename = image_path.stem + ".txt"
            label_path = SOURCE_LABELS_DIR / label_filename

            # Copy image
            shutil.copy(image_path, dest_images_dir / image_path.name)
            
            # Copy corresponding label file, if it exists
            if label_path.exists():
                shutil.copy(label_path, dest_labels_dir / label_path.name)
            else:
                # If an image has no objects, it won't have a label file.
                # YOLO requires an empty .txt file for such cases.
                (dest_labels_dir / label_path.name).touch()
    
    # --- Cleanup: Remove the source files from the parent 'images' and 'labels' folders ---
    print("\nCleaning up source directories...")
    for image_path in image_files:
        label_path = SOURCE_LABELS_DIR / (image_path.stem + ".txt")
        if image_path.exists():
            os.remove(image_path)
        if label_path.exists():
            os.remove(label_path)


    print("-" * 30)
    print("Dataset splitting complete.")
    for set_name, files in sets.items():
        print(f"- {set_name.capitalize()} set: {len(files)} files")
    print(f"\nFiles organized in subdirectories under:")
    print(f"- {PROCESSED_DATA_DIR / 'images'}")
    print(f"- {PROCESSED_DATA_DIR / 'labels'}")
    print("-" * 30)


if __name__ == "__main__":
    split_dataset()
