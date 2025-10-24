# main.py

from utils import indent, load_structure_map, get_audio_duration, get_eligible_models, sort_models, update_metadata, generate_beats_track
from on_effect import add_on_effects
from bars_effect import add_bars_effects
from color_wash_effect import add_color_wash_effects
from shockwave_effect import add_shockwave_effects
from spirals_effect import add_spirals_effects
from pinwheel_effect import add_pinwheel_effects
import os
import xml.etree.ElementTree as ET
import random
from datetime import datetime

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
    Adds 10-30 random 'Spirals' effects of 5-10 seconds to random models/groups.
    Adds 10-30 random 'Pinwheel' effects of 5-10 seconds to random models/groups.
    Sorts models alphabetically with groups before individual models.
    Groups containing "last" sorted to the very end, sub-sorted alphabetically.
    Does not place effects on image, DMX, or MH models.
    Sets visible="0" for models/groups with no effects.
    Pretty-prints the output XML.
    Uses a coordinated palette of 8 colors for effects, with custom palettes for multi-color effects.
    Supports Animation or Media sequence type; for Media, uses audio_path for duration and sets media metadata.
    For Media, generates a beats timing track from audio analysis.
    """

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

    sorted_all_model_names = sort_models(layout_models, layout_groups)
    eligible_groups, eligible_individuals = get_eligible_models(layout_models, layout_groups)
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

    seq_duration_ms = int(duration * 1000)

    beats = None
    if seq_type == "Media" and audio_path:
        # Add beats timing track and get beats list
        beats = generate_beats_track(audio_path, display_elem, element_effects, seq_duration_ms)

    num_ons_added = add_on_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats)
    num_bars_added = add_bars_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats)
    num_color_wash_added = add_color_wash_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats)
    num_shockwave_added = add_shockwave_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats)
    num_spirals_added = add_spirals_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats)
    num_pinwheel_added = add_pinwheel_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats)

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
    update_metadata(head, seq_type, seq_timing, media_file, song, artist, duration)

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
    print(f"Generated {num_ons_added + num_bars_added + num_color_wash_added + num_shockwave_added + num_spirals_added + num_pinwheel_added} custom palettes for effects")
    print(f"Added {num_ons_added} random 'On' effects (1 color each) to models/groups.")
    print(f"Added {num_bars_added} random 'Bars' effects (3 colors each, 5-10s) to models/groups.")
    print(f"Added {num_color_wash_added} random 'Color Wash' effects (2 colors each, 5-10s) to models/groups.")
    print(f"Added {num_shockwave_added} random 'Shockwave' effects (2 colors each, 5-10s) to models/groups.")
    print(f"Added {num_spirals_added} random 'Spirals' effects (2-4 colors each, 5-10s) to models/groups.")
    print(f"Added {num_pinwheel_added} random 'Pinwheel' effects (2-4 colors each, 5-10s) to models/groups.")


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