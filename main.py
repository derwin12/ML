# main.py

from utils import indent, load_structure_map, get_audio_duration, get_eligible_models, sort_models, update_metadata, \
    generate_beats_track
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
import json
import re
import ollama

fixed_colors = [
    "#FF0000",  # Palette1: Red
    "#00FF00",  # Palette2: Green
    "#0000FF",  # Palette3: Blue
    "#FFFF00",  # Palette4: Yellow
    "#FF00FF",  # Palette5: Magenta
    "#00FFFF",  # Palette6: Cyan
    "#FFA500",  # Palette7: Orange
    "#800080"  # Palette8: Purple
]


def get_color_palette(song_name, artist_name):
    """
    Generate a color palette using Ollama Python API based on song name and artist.
    Returns a list of 8 hex color codes or None if the call fails.
    """
    prompt = f"""
You are a creative assistant tasked with generating a color palette inspired by a specific song and artist. The palette should reflect the mood, theme, or imagery evoked by the song's title and the artist's style. Generate a palette of exactly 8 hex color codes (#RRGGBB format) that are distinct, vibrant, and suitable for a dynamic lighting sequence in a visual display. Provide a brief explanation of how the colors relate to the song and artist, describing colors by their qualities (e.g., 'golden yellow', 'deep purple') without including hex codes in the explanation to ensure valid JSON.

Song: {song_name}
Artist: {artist_name}

Output the response in strict JSON format, ensuring:
- The 'palette' array contains exactly 8 hex color codes as quoted strings (e.g., "#RRGGBB").
- No trailing commas in the 'palette' array.
- The 'explanation' field does not contain hex codes, only descriptive color names.
- No inline comments or extra text outside the JSON structure.

Example:
```json
{{
  "palette": ["#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB"],
  "explanation": "The palette includes vibrant reds and blues to reflect the song's energy, with soft pinks for its romantic tone."
}}
"""
    print(f"Sending prompt to Ollama:\n{prompt}")

    try:
        # Call Ollama API
        response = ollama.generate(model='llama3', prompt=prompt)
        stdout = response['response']
        print(f"Ollama response: {stdout}")

        # Check if response is empty
        if not stdout.strip():
            print("Ollama returned empty response. Falling back to default colors.")
            return None

        # Extract JSON portion (between first { and last })
        start_idx = stdout.find('{')
        end_idx = stdout.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
            print(f"No valid JSON found in Ollama output: {stdout}. Falling back to default colors.")
            return None
        json_str = stdout[start_idx:end_idx]

        # Remove inline comments and fix trailing comma in palette
        json_str = re.sub(r'//.*?(?=\n|$)', '', json_str)  # Remove // comments
        json_str = re.sub(r',\s*\]', r']', json_str)  # Remove trailing comma in palette
        print(f"Fixed JSON: {json_str}")

        # Parse JSON
        data = json.loads(json_str)
        palette = data.get('palette', [])

        # Validate palette: must be exactly 8 valid hex colors
        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
        if (
                isinstance(palette, list) and
                len(palette) == 8 and
                all(isinstance(c, str) and hex_pattern.match(c) for c in palette)
        ):
            return palette
        else:
            print(f"Invalid palette from Ollama: {palette}. Falling back to default colors.")
            return None
    except ollama.ResponseError as e:
        print(f"Ollama API error: {e}")
        print(f"Ollama response: {stdout if 'stdout' in locals() else 'N/A'}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw Ollama output: {stdout if 'stdout' in locals() else 'N/A'}")
        return None
    except Exception as e:
        print(f"Unexpected error while calling Ollama: {e}")
        print(f"Raw Ollama output: {stdout if 'stdout' in locals() else 'N/A'}")
        return None


def create_xsq_from_template(
        template_xsq,
        xlights_xml,
        output_xsq,
        structure_json,
        sequence_name="AI_Sequence",
        duration=60,
        audio_path=None,
        sequence_type="Animation",
        artist_name=None,
        song_name=None
):
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
    Groups containing "last" or "override" sorted to the very end, sub-sorted alphabetically.
    Does not place effects on image, DMX, or MH models.
    Sets visible="0" for models/groups with no effects.
    Pretty-prints the output XML.
    Uses a coordinated palette of 8 colors for effects, with custom palettes for multi-color effects.
    For Media sequences, uses a palette generated by Ollama based on song_name and artist_name if available; otherwise, uses fixed_colors.
    For Animation sequences, uses fixed_colors.
    Supports Animation or Media sequence type; for Media, uses audio_path for duration and sets media metadata.
    For Media, generates a beats timing track from audio analysis.
    Uses provided artist_name and song_name for metadata if available; otherwise, falls back to filename parsing or defaults.
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
        # Use provided artist_name and song_name if available, else fall back to filename parsing
        if artist_name and song_name:
            song = song_name
            artist = artist_name
        else:
            # Extract song/artist from filename for metadata (simple heuristic)
            filename = os.path.basename(audio_path).replace('.mp3', '')
            parts = filename.split(' - ')
            song = parts[0] if len(parts) > 0 else "Unknown Song"
            artist = parts[1] if len(parts) > 1 else "Unknown Artist"
        # Generate color palette using Ollama for Media sequences
        colors = get_color_palette(song, artist) if song and artist else None
        if colors is None:
            colors = fixed_colors
    else:
        seq_type = "Animation"
        seq_timing = "50 ms"
        media_file = ""
        song = song_name or "Unknown Song"
        artist = artist_name or "Unknown Artist"
        colors = fixed_colors  # Use fixed_colors for Animation sequences
        if sequence_type.lower() == "animation":
            duration = random.choice([30, 60, 90, 120])

    print(f"Generating {seq_type} sequence with duration: {duration} seconds")
    print(f"Using artist: {artist}, song: {song}")
    print(f"Using colors: {colors}")

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

    num_ons_added = add_on_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, colors,
                                   beats)
    num_bars_added = add_bars_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes,
                                      colors, beats)
    num_color_wash_added = add_color_wash_effects(eligible_elements, eligible_group_elements, seq_duration_ms,
                                                  color_palettes, colors, beats)
    num_shockwave_added = add_shockwave_effects(eligible_elements, eligible_group_elements, seq_duration_ms,
                                                color_palettes, colors, beats)
    num_spirals_added = add_spirals_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes,
                                            colors, beats)
    num_pinwheel_added = add_pinwheel_effects(eligible_elements, eligible_group_elements, seq_duration_ms,
                                              color_palettes, colors, beats)

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
    print(
        f"Included {len(sorted_all_model_names)} models/groups from {xlights_xml} (sorted: groups first, then alphabetical)")
    print(f"{num_visible} models/groups visible (those with effects)")
    print(
        f"Eligible groups: {len(eligible_groups)}, Eligible individuals: {len(eligible_individuals)} (excluding images, DMX, and MH)")
    print(f"Using structure definition: {structure_json}")
    print(f"Sequence duration: {duration} seconds")
    print(f"Using coordinated palette: {colors}")
    print(
        f"Generated {num_ons_added + num_bars_added + num_color_wash_added + num_shockwave_added + num_spirals_added + num_pinwheel_added} custom palettes for effects")
    print(f"Added {num_ons_added} random 'On' effects (1 color each) to models/groups.")
    print(f"Added {num_bars_added} random 'Bars' effects (3 colors each, 5-10s) to models/groups.")
    print(f"Added {num_color_wash_added} random 'Color Wash' effects (2 colors each, 5-10s) to models/groups.")
    print(f"Added {num_shockwave_added} random 'Shockwave' effects (2 colors each, 5-10s) to models/groups.")
    print(f"Added {num_spirals_added} random 'Spirals' effects (2-4 colors each, 5-10s) to models/groups.")
    print(f"Added {num_pinwheel_added} random 'Pinwheel' effects (2-4 colors each, 5-10s) to models/groups.")


# Example usage
if __name__ == "__main__":
    # For testing: Media sequence with default audio and new parameters
    audio_path = r"E:\2023\ShowFolder3D\Audio\Pretty Baby - Alex Sampson.mp3"
    create_xsq_from_template(
        template_xsq=r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\Empty Sequence.xsq",
        xlights_xml=r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\xlights_rgbeffects.xml",
        output_xsq=r"C:\Users\daryl\PycharmProjects\ML\training data\test outputs\Empty_AI_Sequence.xsq",
        structure_json=r"C:\Users\daryl\PycharmProjects\ML\training data\templates\xlights_template_structures.json",
        audio_path=audio_path,
        sequence_type="Media",
        artist_name="Alex Sampson",
        song_name="Pretty Baby"
    )