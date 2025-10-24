import xml.etree.ElementTree as ET
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import numpy as np
import re  # For more robust tag parsing if needed

# Updated categories based on xLights [T:...] types, plus 'ignore' and 'singing'
CATEGORIES = [
    'arch', 'candycane', 'cross', 'cube', 'flood', 'icicles', 'line',
    'matrix', 'matrix_horizontal', 'matrix_column', 'matrix_pole',
    'snowflake', 'sphere', 'spinner', 'star', 'tuneto', 'tree', 'windowframe', 'other', 'ignore', 'singing'
]

SIZES = ['mini', 'mega', 'default', 'unknown']

# For testing: Limit to first N non-skipped models (0 = unlimited)
MAX_MODELS = 0


def load_labeled_data(filename='labeled_data.json'):
    """Load labeled data from JSON file (now with category and size)."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            # Convert old format if needed (simple dict -> nested)
            for key in list(data.keys()):
                if isinstance(data[key], str):  # Old: {feat: 'cat'}
                    data[key] = {"category": data[key], "size": 'default'}  # Updated fallback
            return data
    return {}  # Empty dict: {feature_text: {"category": ..., "size": ...}}


def save_labeled_data(data, filename='labeled_data.json'):
    """Save labeled data to JSON."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)


def extract_size(description):
    """Extract size from description using [S:...] tags. Case-insensitive match."""
    desc_upper = description.upper()
    if '[S:MINI]' in desc_upper:
        return 'mini'
    elif '[S:MEGA]' in desc_upper:
        return 'mega'
    elif '[S:DEFAULT]' in desc_upper:
        return 'default'
    else:
        return 'default'  # Updated fallback


def extract_features(model_elem):
    """Extract text features from a <model> XML element, including Description for [T:...] tags."""
    name = model_elem.get('name', '').lower()
    layout = model_elem.get('Layout', '').lower()
    display_as = model_elem.get('DisplayAs', '').lower()
    string_type = model_elem.get('StringType', '').lower()
    model_type = model_elem.get('Type', '').lower()  # For explicit Type if present
    description = model_elem.get('Description', '').lower()  # Include Description for tags like "T:Arch"
    # Concat all into a single feature string
    features = f"{name} {layout} {display_as} {string_type} {model_type} {description}"
    return features.strip()


def train_model(labeled_data):
    """Train a simple classifier pipeline (uses categories only)."""
    if len(labeled_data) < 2:  # Need at least 2 examples
        return None
    X = list(labeled_data.keys())
    y = [labeled_data[x]["category"] for x in X]
    # Pipeline: TF-IDF + Naive Bayes
    model = make_pipeline(TfidfVectorizer(), MultinomialNB())
    model.fit(X, y)
    return model


def predict_with_confidence(labeled_data, model, feature_text):
    """Predict category: Exact match first, then ML. Returns pred_cat, confidence, stored_size."""
    # Exact match fallback for previously seen features
    if feature_text in labeled_data:
        stored = labeled_data[feature_text]
        return stored["category"], 1.0, stored["size"]  # 100% confidence + stored size

    # Otherwise, use ML for category; size will be detected/user-provided
    if model is None:
        return 'other', 0.0, None
    probs = model.predict_proba([feature_text])[0]
    pred_idx = np.argmax(probs)
    pred_cat = model.classes_[pred_idx]
    confidence = probs[pred_idx]
    return pred_cat, confidence, None


def classify_xml(xml_file, labeled_data, interactive=True):
    """Main function: Parse XML, classify models interactively or non-interactively."""
    tree = ET.parse(xml_file)
    root = tree.getroot()
    models_section = root.find('.//models')  # Adjust XPath if needed
    if models_section is None:
        print("No <models> section found in XML!")
        return

    model = train_model(labeled_data)
    classified = []  # List to store results
    skipped = 0  # Counter for skipped images
    processed = 0  # Counter for processed models

    for model_elem in models_section.findall('model'):
        display_as = model_elem.get('DisplayAs', '')
        if display_as == 'Image':  # Skip image models
            skipped += 1
            continue

        # Limit check for testing
        if MAX_MODELS > 0 and processed >= MAX_MODELS:
            if interactive:
                print(f"\n*** Testing limit reached: Processed {MAX_MODELS} models. Stopping. ***")
            break

        feature_text = extract_features(model_elem)
        model_name = model_elem.get('name', 'Unknown')
        description = model_elem.get('Description', '')
        detected_size = extract_size(description)

        pred_cat, conf, stored_size = predict_with_confidence(labeled_data, model, feature_text)
        is_exact = feature_text in labeled_data

        if interactive:
            print(f"\nModel: {model_name}")
            print(f"Features: {feature_text}")
            print(f"Detected Size: {detected_size} (from: {description})")

            if is_exact:
                # Auto-accept for exact matches: Display and skip prompts
                correct_cat = pred_cat
                correct_size = stored_size
                print(f"Exact match: {correct_cat} ({correct_size})")
            else:
                if pred_cat is None:
                    pred_cat = 'unknown'
                    print("No model trained yet. Please categorize:")
                else:
                    source = " (ML prediction)"
                    print(f"Predicted Category: {pred_cat} (confidence: {conf:.2f}){source}")

                # Interactive feedback for category
                user_input_cat = input("Is category correct? (y/n/c for custom): ").lower().strip()
                if user_input_cat == 'y':
                    correct_cat = pred_cat
                elif user_input_cat == 'n':
                    print(f"Available categories: {', '.join(CATEGORIES)}")
                    correct_cat = input("Enter correct category: ").strip().lower()
                    if correct_cat not in CATEGORIES:
                        correct_cat = 'other'
                else:  # Custom or default
                    print(f"Available categories: {', '.join(CATEGORIES)}")
                    correct_cat = input("Enter category: ").strip().lower()
                    if correct_cat not in CATEGORIES:
                        correct_cat = 'other'

                # Interactive feedback for size (pre-filled if stored; otherwise detected/user)
                if stored_size and stored_size != 'unknown':
                    print(f"Stored Size: {stored_size}")
                    user_input_size = input(f"Is stored size '{stored_size}' correct? (y/n): ").lower().strip()
                    if user_input_size == 'n':
                        print(f"Available sizes: {', '.join(SIZES[:-1])}")
                        correct_size = input("Enter correct size (or 'unknown'): ").strip().lower()
                    else:
                        correct_size = stored_size
                elif detected_size != 'unknown':
                    user_input_size = input(f"Is detected size '{detected_size}' correct? (y/n): ").lower().strip()
                    if user_input_size == 'n':
                        print(f"Available sizes: {', '.join(SIZES[:-1])}")
                        correct_size = input("Enter correct size (or 'unknown'): ").strip().lower()
                    else:
                        correct_size = detected_size
                else:
                    print(f"Available sizes: {', '.join(SIZES[:-1])}")
                    correct_size = input("Enter size (or 'unknown'): ").strip().lower()

                if correct_size not in SIZES:
                    correct_size = 'default'  # Updated fallback

            # Update labeled data with both category and size (only if not exact or changed)
            if not is_exact or (correct_cat != pred_cat or correct_size != stored_size):
                labeled_data[feature_text] = {"category": correct_cat, "size": correct_size}
                save_labeled_data(labeled_data)

            # Retrain model (for category)
            model = train_model(labeled_data)

            print(f"Updated: {model_name} -> {correct_cat} ({correct_size})")
        else:
            # Non-interactive: Use predictions/detections/fallbacks, no saving/retraining
            if is_exact:
                correct_cat = pred_cat
                correct_size = stored_size
            else:
                correct_cat = pred_cat if pred_cat else 'other'
                if stored_size:
                    correct_size = stored_size
                elif detected_size != 'default':  # Use detected if not fallback
                    correct_size = detected_size
                else:
                    correct_size = 'default'

            print(f"Model: {model_name} -> {correct_cat} ({correct_size}) (predicted)")

        classified.append({
            'name': model_name,
            'features': feature_text,
            'category': correct_cat,
            'size': correct_size
        })

        processed += 1

    if skipped > 0:
        print(f"\nSkipped {skipped} image models.")

    # Summary (sorted by category then name)
    sorted_classified = sorted(classified, key=lambda x: (x['category'].lower(), x['name'].lower()))
    print(f"\n=== Classified Models (Processed {len(classified)} / Limit {MAX_MODELS}) ===")
    for item in sorted_classified:
        print(f"{item['name']}: {item['category']} ({item['size']})")


if __name__ == "__main__":
    default_file = r"F:\ShowFolderQA\xlights_rgbeffects.xml"
    user_input = input(f"Enter path to xlights_rgbeffects.xml (default: {default_file}): ").strip()
    xml_file = user_input if user_input else default_file
    if not os.path.exists(xml_file):
        print("File not found!")
    else:
        interactive_input = input("Interactive mode? (y/n, default y): ").strip().lower()
        interactive = interactive_input != 'n'
        labeled_data = load_labeled_data()  # Always load for predictions
        print(
            f"Loaded {len(labeled_data)} labeled examples." if interactive else f"Non-interactive mode: Loaded {len(labeled_data)} labeled examples for predictions.")
        classify_xml(xml_file, labeled_data, interactive)