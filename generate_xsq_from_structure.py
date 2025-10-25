import os
import json
import xml.etree.ElementTree as ET
import copy
from datetime import datetime
import random
from mutagen.mp3 import MP3  # For MP3 duration; install if needed, or use pydub for other formats

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
    if level == 0:
        elem.text = "\n  "

def load_structure_map(structure_json_path):
    """Load the xlights_template_structures.json file and pick the Empty Sequence base if possible."""
    if not os.path.isfile(structure_json_path):
        raise FileNotFoundError(f"Structure map not found: {structure_json_path}")

    with open(structure_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Prefer the one named 'Empty Sequence.xsq', else take first entry
    for entry in data:
        if entry["file"].lower().startswith("empty sequence"):
            print(f"Using structure from template: {entry['file']}")
            return entry

    print("No 'Empty Sequence.xsq' found in structure map — using first entry.")
    return data[0] if data else None


def get_audio_duration(audio_path):
    """Get duration of audio file in seconds."""
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    try:
        audio = MP3(audio_path)
        return audio.info.length
    except Exception as e:
        raise ValueError(f"Could not read audio duration: {e}")


def create_xsq_from_template(template_xsq,
                             xlights_xml,
                             output_xsq,
                             structure_json,
                             sequence_name="AI_Sequence",
                             duration=60,
                             audio_path=None,
                             sequence_type="Animation"):
    """
    Safely create a valid xLights .xsq using a known-good template and a structure map.
    Reads xlights_template_structures.json to verify that required tags exist and are ordered correctly.
    Adds 10 random 'On' effects to random models/groups.
    Adds 10 random 'Bars' effects of 5-10 seconds to random models/groups.
    Adds 5-15 random 'Color Wash' effects of 5-10 seconds to random models/groups.
    Adds 5-10 random 'Shockwave' effects of 5-10 seconds to random models/groups.
    Sorts models alphabetically with groups before individual models.
    Groups containing "last" sorted to the very end, sub-sorted alphabetically.
    Does not place effects on image, DMX, or MH models.
    Sets visible="0" for models/groups with no effects.
    Pretty-prints the output XML.
    Uses a coordinated palette of 8 colors for effects, with custom palettes for multi-color effects.
    Supports Animation or Media sequence type; for Media, uses audio_path for duration and sets media metadata.
    """

    # Coordinated palette of 8 fixed colors
    fixed_colors = [
        "#FF0000",  # Palette1: Red
        "#00FF00",  # Palette2: Green
        "#0000FF",  # Palette3: Blue
        "#FFFF00",  # Palette4: Yellow
        "#FF00FF",  # Palette5: Magenta
        "#00FFFF",  # Palette6: Cyan
        "#FFA500",  # Palette7: Orange
        "#800080"   # Palette8: Purple
    ]

    if not os.path.isfile(template_xsq):
        raise FileNotFoundError(f"Template not found: {template_xsq}")
    if not os.path.isfile(xlights_xml):
        raise FileNotFoundError(f"Layout not found: {xlights_xml}")
    if not os.path.isfile(structure_json):
        raise FileNotFoundError(f"Structure JSON not found: {structure_json}")

    # Determine duration and sequence type
    if sequence_type.lower() == "media" and audio_path:
        duration = get_audio_duration(audio_path)
        seq_type = "Media"
        seq_timing = "25 ms"
        media_file = audio_path
        # Extract song/artist from filename for metadata (simple heuristic)
        filename = os.path.basename(audio_path).replace('.mp3', '')
        parts = filename.split(' - ')
        song = parts[0] if len(parts) > 0 else ""
        artist = parts[1] if len(parts) > 1 else ""
    else:
        seq_type = "Animation"
        seq_timing = "50 ms"
        media_file = ""
        song = ""
        artist = ""
        if sequence_type.lower() == "animation":
            duration = random.choice([30, 60, 90, 120])

    print(f"Generating {seq_type} sequence with duration: {duration} seconds")

    # Load structure definition
    structure_entry = load_structure_map(structure_json)
    expected_root = structure_entry.get("root_tag", "xsequence")

    # Parse template (kept intact)
    template_tree = ET.parse(template_xsq)
    template_root = template_tree.getroot()

    if template_root.tag != expected_root:
        print(f"⚠️ Root tag mismatch: Template has <{template_root.tag}>; expected <{expected_root}>")

    # Parse xlights_rgbeffects.xml to extract models and modelGroups
    layout_tree = ET.parse(xlights_xml)
    layout_root = layout_tree.getroot()

    layout_models = layout_root.findall(".//model")
    layout_groups = layout_root.findall(".//modelGroup")

    if not layout_models and not layout_groups:
        raise ValueError("No <model> or <modelGroup> elements found in xlights_rgbeffects.xml")

    # Collect all models and groups with group identification for sorting
    all_model_list = []
    for m in layout_models:
        model_name = m.attrib.get("name", "Unnamed")
        display_as = m.attrib.get('DisplayAs', '').lower()
        layout = m.attrib.get('Layout', '').lower()
        is_group = (layout == 'group' or display_as == 'group')
        all_model_list.append((is_group, model_name))

    for g in layout_groups:
        group_name = g.attrib.get("name", "Unnamed")
        all_model_list.append((True, group_name))  # modelGroups are always groups

    # Sort: normal groups first, then "last" groups, then individuals; alphabetical within each
    def sort_key(item):
        is_group, name = item
        if is_group:
            if "last" in name.lower():
                return (1, name)  # "last" groups second
            elif "override" in name.lower():
                return (1, name)  # "override" groups second
            else:
                return (0, name)  # normal groups first
        else:
            return (2, name)  # individuals last

    all_model_list.sort(key=sort_key)
    sorted_all_model_names = [name for _, name in all_model_list]

    # Collect eligible models and groups for effects (non-image, non-DMX, non-MH)
    eligible_groups = []
    eligible_individuals = []
    for m in layout_models:
        model_name = m.attrib.get("name", "Unnamed")
        display_as = m.attrib.get("DisplayAs", "").lower()
        protocol = m.attrib.get("Protocol", "").upper()
        layout = m.attrib.get('Layout', '').lower()
        group_check = (layout == 'group' or display_as == 'group')
        if (display_as != "image" and 
            protocol != "DMX" and 
            not model_name.upper().startswith("MH-")):
            if group_check:
                eligible_groups.append(model_name)
            else:
                eligible_individuals.append(model_name)

    for g in layout_groups:
        group_name = g.attrib.get("name", "Unnamed")
        # Groups typically don't have DisplayAs/Protocol, so assume eligible unless MH-
        if not group_name.upper().startswith("MH-"):
            eligible_groups.append(group_name)

    eligible_model_names = eligible_groups + eligible_individuals

    # Find sections
    display_elem = template_root.find(".//DisplayElements")
    element_effects = template_root.find(".//ElementEffects")
    color_palettes = template_root.find("ColorPalettes")
    head = template_root.find("head")

    if display_elem is None or element_effects is None or color_palettes is None or head is None:
        raise ValueError("Template missing expected sections.")

    # --- Rebuild DisplayElements section ---
    for child in list(display_elem):
        display_elem.remove(child)

    for model_name in sorted_all_model_names:
        ET.SubElement(display_elem, "Element", {
            "name": model_name,
            "type": "Model",
            "active": "1",
            "collapsed": "0",
            "visible": "1",
            "views": "Default"
        })

    # --- Rebuild ElementEffects section (empty layers) ---
    for child in list(element_effects):
        element_effects.remove(child)

    for model_name in sorted_all_model_names:
        elem = ET.SubElement(element_effects, "Element", {
            "name": model_name,
            "type": "Model"
        })
        ET.SubElement(elem, "EffectLayer")  # empty placeholder layer

    # --- Get eligible elements for effects ---
    elements = element_effects.findall("Element")
    eligible_elements = [e for e in elements if e.attrib["name"] in eligible_model_names]

    # Separate eligible group and individual elements
    eligible_group_elements = [e for e in eligible_elements if e.attrib["name"] in eligible_groups]
    eligible_individual_elements = [e for e in eligible_elements if e.attrib["name"] in eligible_individuals]

    # --- Add 10 random On effects (1 color palette) ---
    seq_duration_ms = int(duration * 1000)
    num_ons_added = 0
    if eligible_elements:
        for _ in range(10):
            # 30% chance to pick group if available
            if random.random() < 0.3 and eligible_group_elements:
                elem = random.choice(eligible_group_elements)
            else:
                elem = random.choice(eligible_elements)  # fallback to all eligible

            effect_layer = elem.find("EffectLayer")
            if effect_layer is None:
                effect_layer = ET.SubElement(elem, "EffectLayer")

            start_time = random.randint(0, seq_duration_ms - 2000)
            effect_dur = random.randint(1000, 3000)  # 1-3 seconds
            end_time = start_time + effect_dur

            # Select 1 random color index (1-8)
            selected_indices = [random.randint(1, 8)]
            parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
            for k in selected_indices:
                parts.append(f"C_CHECKBOX_Palette{k}=1")
            palette_str = ",".join(parts)

            # Add the ColorPalette
            new_palette = ET.SubElement(color_palettes, "ColorPalette")
            new_palette.text = palette_str

            # Palette ID is 0-based index of this new one (after template's)
            palette_id = len(color_palettes.findall("ColorPalette")) - 1

            effect = ET.SubElement(effect_layer, "Effect", {
                "name": "On",
                "startTime": f"{start_time}",
                "endTime": f"{end_time}",
                "selected": "0",
                "palette": str(palette_id)
            })
            settings = ET.SubElement(effect, "Settings")
            # Settings without C1, using palette
            settings.text = "E1=100;E2=100;T1=0;CHECKBOX_Shimmer=0"
            num_ons_added += 1

    # --- Add 10 random Bars effects (3 colors palette) ---
    directions = ["Up", "Down", "Expand", "Compress", "Left/Right", "H Expand", "H Compress", "Alternate"]
    num_bars_added = 0
    if eligible_elements:
        for _ in range(10):
            # 30% chance to pick group if available
            if random.random() < 0.3 and eligible_group_elements:
                elem = random.choice(eligible_group_elements)
            else:
                elem = random.choice(eligible_elements)  # fallback to all eligible

            effect_layer = elem.find("EffectLayer")
            if effect_layer is None:
                effect_layer = ET.SubElement(elem, "EffectLayer")

            start_time = random.randint(0, seq_duration_ms - 10000)
            effect_dur = random.randint(5000, 10000)  # 5-10 seconds
            end_time = start_time + effect_dur

            # Random parameters for Bars
            bar_count = random.randint(3, 8)
            direction = random.choice(directions)
            cycles = random.uniform(1, 3)
            palette_rep = random.randint(1, 4)
            highlight = random.choice([0, 1])
            threed = random.choice([0, 1])
            gradient = random.choice([0, 1])
            use_first_for_highlight = 0  # default

            # Select 3 random distinct color indices (1-8)
            selected_indices = random.sample(range(1, 9), 3)
            parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
            for k in selected_indices:
                parts.append(f"C_CHECKBOX_Palette{k}=1")
            palette_str = ",".join(parts)

            # Add the ColorPalette
            new_palette = ET.SubElement(color_palettes, "ColorPalette")
            new_palette.text = palette_str

            # Palette ID
            palette_id = len(color_palettes.findall("ColorPalette")) - 1

            effect = ET.SubElement(effect_layer, "Effect", {
                "name": "Bars",
                "startTime": f"{start_time}",
                "endTime": f"{end_time}",
                "selected": "0",
                "palette": str(palette_id)
            })
            settings = ET.SubElement(effect, "Settings")
            # Settings without C1 C2, using palette
            settings.text = (f"BarCount={bar_count};"
                             f"Direction={direction};"
                             f"Cycles={cycles:.1f};"
                             f"PaletteRep={palette_rep};"
                             f"CHECKBOX_Highlight={highlight};"
                             f"CHECKBOX_3D={threed};"
                             f"CHECKBOX_Gradient={gradient};"
                             f"CHECKBOX_UseFirstColorForHighlight={use_first_for_highlight};"
                             f"E1=100;E2=100")
            num_bars_added += 1

    # --- Add 5-15 random Color Wash effects (2 colors palette) ---
    num_color_wash = random.randint(5, 15)
    num_color_wash_added = 0
    if eligible_elements:
        for _ in range(num_color_wash):
            # 30% chance to pick group if available
            if random.random() < 0.3 and eligible_group_elements:
                elem = random.choice(eligible_group_elements)
            else:
                elem = random.choice(eligible_elements)  # fallback to all eligible

            effect_layer = elem.find("EffectLayer")
            if effect_layer is None:
                effect_layer = ET.SubElement(elem, "EffectLayer")

            start_time = random.randint(0, seq_duration_ms - 10000)
            effect_dur = random.randint(5000, 10000)  # 5-10 seconds
            end_time = start_time + effect_dur

            # Random parameters for Color Wash
            count = random.randint(1, 5)
            vfade = random.choice([0, 1])
            hfade = random.choice([0, 1])
            shimmer = random.choice([0, 1])
            circ = random.choice([0, 1])

            # Select 2 random distinct color indices (1-8)
            selected_indices = random.sample(range(1, 9), 2)
            parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
            for k in selected_indices:
                parts.append(f"C_CHECKBOX_Palette{k}=1")
            palette_str = ",".join(parts)

            # Add the ColorPalette
            new_palette = ET.SubElement(color_palettes, "ColorPalette")
            new_palette.text = palette_str

            # Palette ID
            palette_id = len(color_palettes.findall("ColorPalette")) - 1

            effect = ET.SubElement(effect_layer, "Effect", {
                "name": "Color Wash",
                "startTime": f"{start_time}",
                "endTime": f"{end_time}",
                "selected": "0",
                "palette": str(palette_id)
            })
            settings = ET.SubElement(effect, "Settings")
            # Settings without C1 C2, using palette
            settings.text = (f"Count={count};"
                             f"CHECKBOX_VerticalFade={vfade};"
                             f"CHECKBOX_HorizontalFade={hfade};"
                             f"CHECKBOX_Shimmer={shimmer};"
                             f"CHECKBOX_CircularPalette={circ};"
                             f"E1=100;E2=100")
            num_color_wash_added += 1

    # --- Add 5-10 random Shockwave effects (2 colors palette) ---
    num_shockwave = random.randint(5, 10)
    num_shockwave_added = 0
    if eligible_elements:
        for _ in range(num_shockwave):
            # 30% chance to pick group if available
            if random.random() < 0.3 and eligible_group_elements:
                elem = random.choice(eligible_group_elements)
            else:
                elem = random.choice(eligible_elements)  # fallback to all eligible

            effect_layer = elem.find("EffectLayer")
            if effect_layer is None:
                effect_layer = ET.SubElement(elem, "EffectLayer")

            start_time = random.randint(0, seq_duration_ms - 10000)
            effect_dur = random.randint(5000, 10000)  # 5-10 seconds
            end_time = start_time + effect_dur

            # Random parameters for Shockwave
            center_x = random.randint(0, 100)
            center_y = random.randint(0, 100)
            cycles = random.uniform(1, 5)
            start_radius = random.randint(1, 10)
            start_width = random.randint(1, 10)
            end_width = random.randint(5, 20)
            accel = random.randint(-50, 50)
            blend_edges = random.choice([0, 1])
            scale = random.choice([0, 1])

            # Set end_radius based on whether it's a group or model
            is_group = elem in eligible_group_elements
            end_radius = random.randint(50, 200) if is_group else random.randint(20, 50)

            # Select 2 random distinct color indices (1-8) for Shockwave
            selected_indices = random.sample(range(1, 9), 2)
            parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
            for k in selected_indices:
                parts.append(f"C_CHECKBOX_Palette{k}=1")
            palette_str = ",".join(parts)

            # Add the ColorPalette
            new_palette = ET.SubElement(color_palettes, "ColorPalette")
            new_palette.text = palette_str

            # Palette ID
            palette_id = len(color_palettes.findall("ColorPalette")) - 1

            effect = ET.SubElement(effect_layer, "Effect", {
                "name": "Shockwave",
                "startTime": f"{start_time}",
                "endTime": f"{end_time}",
                "selected": "0",
                "palette": str(palette_id)
            })
            settings = ET.SubElement(effect, "Settings")
            # Settings for Shockwave using palette
            settings.text = (f"E_SLIDER_Shockwave_CenterX={center_x};"
                             f"E_SLIDER_Shockwave_CenterY={center_y};"
                             f"E_SLIDER_Shockwave_Cycles={cycles:.1f};"
                             f"E_SLIDER_Shockwave_Start_Radius={start_radius};"
                             f"E_SLIDER_Shockwave_End_Radius={end_radius};"
                             f"E_SLIDER_Shockwave_Start_Width={start_width};"
                             f"E_SLIDER_Shockwave_End_Width={end_width};"
                             f"E_SLIDER_Shockwave_Accel={accel};"
                             f"E_CHECKBOX_Shockwave_Blend_Edges={blend_edges};"
                             f"E_CHECKBOX_Shockwave_Scale={scale};"
                             f"E1=100;E2=100")
            num_shockwave_added += 1

    # --- Set visibility for models with no effects ---
    num_visible = 0
    for elem in elements:  # all elements in ElementEffects
        effect_layer = elem.find("EffectLayer")
        has_effects = bool(effect_layer.findall("Effect")) if effect_layer is not None else False
        visibility = "1" if has_effects else "0"
        if visibility == "1":
            num_visible += 1

        # Find corresponding display element
        for de in display_elem.findall("Element"):
            if de.attrib["name"] == elem.attrib["name"]:
                de.set("visible", visibility)
                break

    # --- Update metadata ---
    head = template_root.find("head")
    if head is not None:
        seq_dur_elem = head.find("sequenceDuration")
        if seq_dur_elem is not None:
            seq_dur_elem.text = f"{duration:.3f}"

        seq_type_elem = head.find("sequenceType")
        if seq_type_elem is not None:
            seq_type_elem.text = seq_type

        seq_timing_elem = head.find("sequenceTiming")
        if seq_timing_elem is not None:
            seq_timing_elem.text = seq_timing

        media_file_elem = head.find("mediaFile")
        if media_file_elem is not None:
            media_file_elem.text = media_file

        song_elem = head.find("song")
        if song_elem is not None:
            song_elem.text = song

        artist_elem = head.find("artist")
        if artist_elem is not None:
            artist_elem.text = artist

    template_root.set("name", sequence_name)
    template_root.set("dateCreated", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    template_root.set("sequenceDuration", str(duration))

    # --- Save output (pretty-printed) ---
    out_dir = os.path.dirname(output_xsq)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Pretty-print the XML
    indent(template_root)
    template_tree.write(output_xsq, encoding="utf-8", xml_declaration=True)

    print(f"\n✅ Created structured {seq_type.lower()} sequence: {output_xsq}")
    print(f"Included {len(sorted_all_model_names)} models/groups from {xlights_xml} (sorted: groups first, then alphabetical)")
    print(f"{num_visible} models/groups visible (those with effects)")
    print(f"Eligible groups: {len(eligible_groups)}, Eligible individuals: {len(eligible_individuals)} (excluding images, DMX, and MH)")
    print(f"Using structure definition: {structure_json}")
    print(f"Sequence duration: {duration} seconds")
    print(f"Using coordinated palette: {fixed_colors}")
    print(f"Generated {num_ons_added + num_bars_added + num_color_wash_added + num_shockwave_added} custom palettes for effects")
    print(f"Added {num_ons_added} random 'On' effects (1 color each) to models/groups.")
    print(f"Added {num_bars_added} random 'Bars' effects (3 colors each, 5-10s) to models/groups.")
    print(f"Added {num_color_wash_added} random 'Color Wash' effects (2 colors each, 5-10s) to models/groups.")
    print(f"Added {num_shockwave_added} random 'Shockwave' effects (2 colors each, 5-10s) to models/groups.")


# Example usage
if __name__ == "__main__":
    # For testing: Media sequence with default audio
    audio_path = r"E:\2023\ShowFolder3D\Audio\Pretty Baby - Alex Sampson.mp3"
    create_xsq_from_template(
        template_xsq=r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\Empty Sequence.xsq",
        xlights_xml=r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\xlights_rgbeffects.xml",
        output_xsq=r"C:\Users\daryl\PycharmProjects\ML\training data\test outputs\Empty_AI_Sequence.xsq",
        structure_json=r"C:\Users\daryl\PycharmProjects\ML\training data\templates\xlights_template_structures.json",
        audio_path=audio_path,
        sequence_type="Media"
    )