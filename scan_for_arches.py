import os
import xml.etree.ElementTree as ET
import json
from collections import defaultdict
import re


def parse_xml_file(filepath):
    """Parse an XML file and return root."""
    try:
        tree = ET.parse(filepath)
        return tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def identify_arch_models(rgb_effects_file):
    """Identify arch models from xlights_rgbeffects.xml."""
    arch_models = set()
    root = parse_xml_file(rgb_effects_file)
    if root is None:
        return arch_models
    for model in root.findall(".//model"):
        name = model.get("name", "").lower().strip()  # Keep dashes, lowercase
        description = model.get("Description", "").lower()
        display_as = model.get("DisplayAs", "").lower()
        if "t:arch" in description or "arches" in display_as:
            arch_models.add(name)
    print(f"Arch models identified: {sorted(arch_models)}")  # Debug
    return arch_models


def identify_arch_groups(rgb_effects_file, arch_models):
    """Identify groups where all models are arch models."""
    arch_groups = set()
    root = parse_xml_file(rgb_effects_file)
    if root is None:
        return arch_groups
    for group in root.findall(".//modelGroup"):
        group_name = group.get("name", "").lower().strip().replace("-", " ")  # Normalize group name
        models_str = group.get("models", "").strip()
        print(f"Processing group: {group_name}, models attribute: '{models_str}'")  # Debug

        # Split models by commas, normalize each model name
        models = re.split(r',', models_str.strip())
        models = [m.lower().strip() for m in models if m.strip()]  # Lowercase, keep dashes
        print(f"  Models in group '{group_name}': {models}")  # Debug

        # Check if all models are arch models
        non_arch_models = [m for m in models if m not in arch_models]
        if not models:  # Empty model list
            print(f"  Rejected: Empty model list")
            continue
        if non_arch_models:
            print(f"  Rejected: Non-arch models found: {non_arch_models}")
            continue
        if all(m in arch_models for m in models):
            arch_groups.add(group_name)
            print(f"  Added to arch groups: All models are arches")

    print(f"Arch groups identified: {sorted(arch_groups)}")  # Debug
    return arch_groups


def extract_effect_db(root):
    """Extract effect definitions from EffectDB as list of param dicts."""
    effect_db = []
    for eff in root.findall(".//EffectDB/Effect"):
        params_str = eff.text or ""
        params = {}
        for param in params_str.split(','):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key.strip()] = value.strip()
        effect_db.append(params)
    return effect_db


def extract_timing_tracks(root):
    """
    Extract timing tracks from the XML root, grouping Effect elements under each track.
    Returns a list of dictionaries, each with 'track_name' and 'marks' keys.
    """
    timing_tracks = []
    try:
        # Find all <Element> nodes with type="timing"
        for element in root.findall(".//Element[@type='timing']"):
            track_name = element.get('name', 'Unnamed')
            # Find all <Effect> elements within this <Element>
            effects = element.findall(".//Effect")
            if effects:
                print(f"Timing track found in Element: {track_name}")
                # Create a list of marks for this track
                marks = [
                    {
                        'startTime': int(effect.get('startTime', 0)),  # Convert to int, default 0
                        'endTime': int(effect.get('endTime', 0)),      # Convert to int, default 0
                        'label': effect.get('label', '')
                    }
                    for effect in effects
                    if effect.get('startTime') and effect.get('endTime')  # Skip invalid effects
                ]
                # Add track dictionary to timing_tracks
                timing_tracks.append({
                    'track_name': track_name,
                    'marks': marks
                })
    except Exception as e:
        print(f"Error extracting timing tracks: {e}")
    return timing_tracks


def find_closest_beat(effect_time, beat_marks):
    """Find the closest beat mark to an effect's start time and calculate offset."""
    if not beat_marks:
        return None, None
    closest_beat = min(beat_marks, key=lambda x: abs(x - effect_time))
    offset = effect_time - closest_beat
    return closest_beat, offset


def extract_arch_effects(root, arch_models, arch_groups, timing_tracks, effect_db):
    """Extract effects on arch models and groups, including timing relationships."""
    arch_effects = defaultdict(lambda: {"count": 0, "parameters": [], "timings": []})

    # Debug: Log all element names found
    all_elements = set()
    for element in root.findall(".//Element") + root.findall(".//element"):
        element_name = element.get("name", "")
        all_elements.add(element_name)
        element_name_lower = element_name.lower().strip().replace("-", " ")  # Match group normalization

        # Check if element is an arch model or group
        if element_name_lower not in arch_models and element_name_lower not in arch_groups:
            continue

        # Debug: Log matched arch element
        print(f"Found arch element: {element_name} (type: {'group' if element_name_lower in arch_groups else 'model'})")

        # Process effects
        for effect in element.findall(".//Effect") + element.findall(".//effect"):
            ref = effect.get("ref")
            params = {}
            if ref:
                try:
                    params = effect_db[int(ref)]
                except (IndexError, ValueError):
                    params = {}

            effect_name = effect.get("name", "Unknown")
            start_time = int(effect.get("startTime", effect.get("starttime", 0)))
            end_time = int(effect.get("endTime", effect.get("endtime", 0)))
            duration = end_time - start_time

            # Debug: Log effect found
            print(
                f"  Effect: {effect_name}, Ref: {ref}, Start: {start_time}, Duration: {duration}, Params count: {len(params)}")

            # Timing info
            timing_info = []
            for track in timing_tracks:
                closest_beat, offset = find_closest_beat(start_time, track["marks"])
                if closest_beat is not None:
                    timing_info.append({
                        "track_name": track["name"],
                        "closest_beat": closest_beat,
                        "offset_ms": offset
                    })

            # Store
            arch_effects[effect_name]["count"] += 1
            arch_effects[effect_name]["parameters"].append({
                "element": element_name,
                "type": "group" if element_name_lower in arch_groups else "model",
                "start_time": start_time,
                "duration": duration,
                "params": params
            })
            arch_effects[effect_name]["timings"].append(timing_info)

    # Debug summary
    print(f"All elements found: {sorted(all_elements)}")
    print(f"Arch models expected: {sorted(arch_models)}")
    print(f"Arch groups expected: {sorted(arch_groups)}")

    return arch_effects


def analyze_directory(directory_path, rgb_effects_file):
    """Analyze all .xsq files in the directory and summarize arch effects."""
    summary = {
        "files_processed": 0,
        "arch_effects": {},
        "arch_models": [],
        "arch_groups": [],
        "errors": []
    }

    # Identify arch models and groups
    arch_models = identify_arch_models(rgb_effects_file)
    arch_groups = identify_arch_groups(rgb_effects_file, arch_models)
    summary["arch_models"] = list(arch_models)
    summary["arch_groups"] = list(arch_groups)

    if not arch_models and not arch_groups:
        summary["errors"].append("No arch models or groups found in xlights_rgbeffects.xml")
        return summary

    # Process each .xsq file
    for filename in os.listdir(directory_path):
        if not filename.endswith(".xsq"):
            continue

        filepath = os.path.join(directory_path, filename)
        root = parse_xml_file(filepath)
        if root is None:
            summary["errors"].append(f"Failed to parse {filename}")
            continue

        summary["files_processed"] += 1

        # Extract effect_db
        effect_db = extract_effect_db(root)

        # Extract timing tracks
        timing_tracks = extract_timing_tracks(root)

        # Extract arch effects
        arch_effects = extract_arch_effects(root, arch_models, arch_groups, timing_tracks, effect_db)

        # Merge into summary
        for effect_name, data in arch_effects.items():
            if effect_name not in summary["arch_effects"]:
                summary["arch_effects"][effect_name] = {
                    "total_count": 0,
                    "parameters": [],
                    "timings": [],
                    "elements": set()
                }
            summary["arch_effects"][effect_name]["total_count"] += data["count"]
            summary["arch_effects"][effect_name]["parameters"].extend(data["parameters"])
            summary["arch_effects"][effect_name]["timings"].extend(data["timings"])
            for param in data["parameters"]:
                summary["arch_effects"][effect_name]["elements"].add(param["element"])

    # Convert sets to lists
    for effect_name in summary["arch_effects"]:
        summary["arch_effects"][effect_name]["elements"] = list(summary["arch_effects"][effect_name]["elements"])

    return summary


def save_summary(summary, output_path):
    """Save the summary to a JSON file."""
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=4)
    print(f"Summary saved to {output_path}")


def main():
    # Configuration
    directory_path = r"E:\2023\ShowFolder3D"  # Path to .xsq files
    rgb_effects_file = r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\xlights_rgbeffects.xml"  # Path to xlights_rgbeffects.xml
    output_path = "arch_effects_summary.json"

    # Validate inputs
    if not os.path.exists(directory_path):
        print(f"Directory {directory_path} does not exist")
        return
    if not os.path.exists(rgb_effects_file):
        print(f"xlights_rgbeffects.xml file {rgb_effects_file} does not exist")
        return

    # Analyze
    summary = analyze_directory(directory_path, rgb_effects_file)

    # Save
    save_summary(summary, output_path)

    # Print stats
    print(f"Processed {summary['files_processed']} sequence files")
    print(f"Found {len(summary['arch_effects'])} unique effects on arch models/groups")
    print(f"Arch models: {summary['arch_models']}")
    print(f"Arch groups: {summary['arch_groups']}")
    if summary["errors"]:
        print(f"Encountered {len(summary['errors'])} errors: {summary['errors']}")


if __name__ == "__main__":
    main()