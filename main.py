# main.py

from utils import indent, load_structure_map, get_audio_duration, get_eligible_models, sort_models, update_metadata, \
    generate_beats_track, generate_downbeats_track, generate_onsets_track, generate_energy_peaks_track, \
    generate_stem_tracks, \
    generate_lyrics_track, generate_structure_track, _lemonade_complete, _load_audio, get_or_create_layer, \
    categorize_models, add_everything_group_effect, EffectDBRegistry, place_effect, find_singing_props, \
    filter_by_effect, EffectBudget, set_effect_budget, filter_beats_vocals_only, \
    get_model_positions, sort_elements_by_position, generate_phrase_boundaries, get_foreground_elements, \
    filter_by_probability
from spatial_sweep import add_spatial_sweep_effects
from singing_face_effect import add_singing_face_effects
from on_effect import add_on_effects
from bars_effect import add_bars_effects
from color_wash_effect import add_color_wash_effects
from shockwave_effect import add_shockwave_effects
from spirals_effect import add_spirals_effects
from pinwheel_effect import add_pinwheel_effects
from single_strand_effect import add_single_strand_effects
from morph_effect import add_morph_effects
from fill_effect import add_fill_effects
from ripple_effect import add_ripple_effects
from wave_effect import add_wave_effects
from twinkle_effect import add_twinkle_effects
from meteors_effect import add_meteors_effects
from fire_effect import add_fire_effects
from shimmer_effect import add_shimmer_effects
from strobe_effect import add_strobe_effects
from fan_effect import add_fan_effects
from galaxy_effect import add_galaxy_effects
from shape_effect import add_shape_effects
from warp_effect import add_warp_effects
from marquee_effect import add_marquee_effects
from curtain_effect import add_curtain_effects
from butterfly_effect import add_butterfly_effects
from snowflakes_effect import add_snowflakes_effects
from garlands_effect import add_garlands_effects
from spirograph_effect import add_spirograph_effects
from lightning_effect import add_lightning_effects
from circles_effect import add_circles_effects
from kaleidoscope_effect import add_kaleidoscope_effects
from liquid_effect import add_liquid_effects
from plasma_effect import add_plasma_effects
from fireworks_effect import add_fireworks_effects
from tendril_effect import add_tendril_effects
import os
import xml.etree.ElementTree as ET
import random
from datetime import datetime
import json
import re
import argparse

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
    Generate a color palette using Lemonade Python API based on song name and artist.
    Returns a list of 8 hex color codes or None if the call fails.
    """
    prompt = f"""
You are a creative assistant tasked with generating a color palette inspired by a specific song and artist.
The palette should reflect the mood, theme, or imagery evoked by the song's title and the artist's style.
Generate a palette of exactly 8 hex color codes (#RRGGBB format) that are distinct, vibrant, and suitable for a dynamic lighting sequence in a visual display.
Provide a brief explanation of how the colors relate to the song and artist, describing colors by their qualities (e.g., 'golden yellow', 'deep purple') without including hex codes in the explanation to ensure valid JSON.

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
    print(f"Sending prompt to Lemonade:\n{prompt}")

    try:
        stdout = _lemonade_complete(prompt)
        print(f"Lemonade response: {stdout}")

        # Check if response is empty
        if not stdout.strip():
            print("Lemonade returned empty response. Falling back to default colors.")
            return None

        # Extract JSON portion (between first { and last })
        start_idx = stdout.find('{')
        end_idx = stdout.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
            print(f"No valid JSON found in Lemonade output: {stdout}. Falling back to default colors.")
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
            print(f"Invalid palette from Lemonade: {palette}. Falling back to default colors.")
            return None
    except Exception as e:
        print(f"Lemonade API error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw Lemonade output: {stdout if 'stdout' in locals() else 'N/A'}")
        return None
    except Exception as e:
        print(f"Unexpected error while calling Lemonade: {e}")
        return None


def add_first_beat_effects(eligible_elements, color_palettes, colors, beats, structure=None, registry=None):
    """Place one random On/Bars/ColorWash effect on every eligible model spanning the intro section.
    Falls back to beats[0]→beats[1] if no structure is available."""
    effect_choices = ["On", "Bars", "Color Wash"]
    count = 0

    if structure:
        section = next(
            (s for s in structure if "intro" in s["section"].lower()),
            structure[0]
        )
        start_ms = int(section["start"] * 1000)
        end_ms = int(section["end"] * 1000)
        print(f"First-section effects spanning: {section['section']} ({section['start']:.1f}s → {section['end']:.1f}s)")
    elif beats and len(beats) >= 2:
        start_ms = beats[0]
        end_ms = beats[1]
    else:
        return 0

    for elem in eligible_elements:
        effect_layer = get_or_create_layer(elem, start_ms, end_ms)
        if effect_layer is None:
            continue

        effect_name = random.choice(effect_choices)
        selected_indices = random.sample(range(1, 9), min(2, 8))
        parts = [f"C_BUTTON_Palette{i+1}={colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        if registry is not None:
            place_effect(effect_layer, effect_name, start_ms, end_ms, palette_id, "E1=100,E2=100", registry)
        else:
            effect = ET.SubElement(effect_layer, "Effect", {
                "name": effect_name,
                "startTime": str(start_ms),
                "endTime": str(end_ms),
                "selected": "0",
                "palette": str(palette_id)
            })
            settings = ET.SubElement(effect, "Settings")
            settings.text = "E1=100,E2=100"
        count += 1

    return count


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
    For Media sequences, uses a palette generated by Lemonade based on song_name and artist_name if available; otherwise, uses fixed_colors.
    For Animation sequences, uses fixed_colors.
    Supports Animation or Media sequence type; for Media, uses audio_path for duration and sets media metadata.
    For Media, generates a beats timing track and a structure timing track from audio analysis and Lemonade.
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
        # Generate color palette using Lemonade for Media sequences
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
    model_categories = categorize_models(layout_models, layout_groups)
    eligible_groups, eligible_individuals, everything_group_name = get_eligible_models(
        layout_models, layout_groups, model_categories
    )
    eligible_model_names = eligible_groups + eligible_individuals
    set_effect_budget(EffectBudget(model_categories))
    model_positions = get_model_positions(layout_models)
    singing_props_map = find_singing_props(layout_models)
    if singing_props_map:
        print(f"Singing props detected ({len(singing_props_map)}): {', '.join(singing_props_map.keys())}")

    # Print categorization summary
    from collections import Counter
    cat_counts = Counter(model_categories[n] for n in eligible_model_names if n in model_categories)
    print("Model categories:", ", ".join(f"{k}={v}" for k, v in sorted(cat_counts.items())))
    generic_count = sum(1 for v in model_categories.values() if v == "generic_group")
    print(f"Groups: typed={len(eligible_groups)}, generic={generic_count} (excluded), "
          f"everything={everything_group_name} ({len(layout_groups)} total groups)")

    # Find sections
    display_elem = template_root.find(".//DisplayElements")
    element_effects = template_root.find(".//ElementEffects")
    color_palettes = template_root.find("ColorPalettes")
    effect_db_elem = template_root.find("EffectDB")
    head = template_root.find("head")

    if display_elem is None or element_effects is None or color_palettes is None or head is None:
        raise ValueError("Template missing expected sections.")

    if effect_db_elem is None:
        effect_db_elem = ET.SubElement(template_root, "EffectDB")

    registry = EffectDBRegistry()

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

    # Singing props get only a Faces effect
    singing_prop_elements = [e for e in elements if e.attrib.get("name") in singing_props_map]

    seq_duration_ms = int(duration * 1000)

    beats = None
    downbeats = None
    structure = None
    onsets = None
    energy_peaks = None
    lyrics = None
    vocal_onsets = None
    phrase_boundaries = []
    if seq_type == "Media" and audio_path:
        y, sr = _load_audio(audio_path)
        audio_duration_s = len(y) / sr
        beats = generate_beats_track(y, sr, display_elem, element_effects, seq_duration_ms)
        downbeats = generate_downbeats_track(y, sr, display_elem, element_effects, seq_duration_ms)
        onsets = generate_onsets_track(y, sr, display_elem, element_effects, seq_duration_ms)
        energy_peaks = generate_energy_peaks_track(y, sr, display_elem, element_effects, seq_duration_ms)
        lyrics = generate_lyrics_track(song, artist, audio_duration_s, display_elem, element_effects, seq_duration_ms)
        structure = generate_structure_track(audio_path, song, artist, display_elem, element_effects, seq_duration_ms)
        generate_stem_tracks(audio_path, display_elem, element_effects, seq_duration_ms)
        vocal_onsets = filter_beats_vocals_only(onsets or [], lyrics or [])
        if lyrics and vocal_onsets is not onsets:
            suppressed = len(onsets or []) - len(vocal_onsets)
            print(f"Lyrics gating: suppressed {suppressed} onset beats in instrumental gaps.")
        phrase_boundaries = generate_phrase_boundaries(downbeats or [], phrase_size=4)
        print(f"Phrase boundaries: {len(phrase_boundaries)} phrases detected.")

    # Everything group gets only a Black Cherry Cosmos shader (no normal effects)
    if everything_group_name:
        everything_elem = next(
            (e for e in elements if e.attrib.get("name") == everything_group_name), None
        )
        if everything_elem is not None:
            add_everything_group_effect(everything_elem, seq_duration_ms, color_palettes, registry)
            print(f"Everything group '{everything_group_name}': Black Cherry Cosmos shader added.")

    # Singing props get only a Faces effect
    if singing_prop_elements:
        num_singing = add_singing_face_effects(
            singing_prop_elements, singing_props_map, color_palettes, seq_duration_ms, registry
        )
        print(f"Singing props: {num_singing} Faces effects placed.")

    # POC: place one random effect on every eligible model/group spanning the first beat
    num_first_beat = add_first_beat_effects(eligible_elements, color_palettes, colors, beats, structure, registry)
    print(f"First-beat POC: placed {num_first_beat} effects across all eligible models.")

    # Build position-sorted element list for spatial sweeps
    x_sorted_elements = sort_elements_by_position(eligible_elements, model_positions, axis='x')

    # Spatial sweep: staggered On effect across models in X order at each phrase boundary
    if phrase_boundaries:
        num_sweep = add_spatial_sweep_effects(
            x_sorted_elements, seq_duration_ms, color_palettes, colors,
            phrase_boundaries, structure=structure, registry=registry
        )
        print(f"Spatial sweeps: {num_sweep} On effects placed across {len(x_sorted_elements)} models.")

    # Helpers: filter eligible elements by exclusion rules + learned probability threshold
    def fe(effect_name):
        base = filter_by_effect(eligible_elements, effect_name, model_categories)
        return filter_by_probability(base, effect_name, model_categories)
    def fg(effect_name):
        base = filter_by_effect(eligible_group_elements, effect_name, model_categories)
        return filter_by_probability(base, effect_name, model_categories)

    # Foreground elements for high-impact effects (chorus/drop category leaders)
    chorus_fg = get_foreground_elements(eligible_elements, model_categories, "chorus")
    chorus_fg_groups = get_foreground_elements(eligible_group_elements, model_categories, "chorus")

    # Timing aliases — fall back to beats when the richer track is unavailable
    _peaks   = energy_peaks or beats or []         # loud-burst effects
    _onsets  = onsets or beats or []               # rapid reactive effects
    _down    = downbeats or beats or []            # slow sweeping effects
    _vocal   = vocal_onsets if vocal_onsets is not None else _onsets  # lyrics-gated rapid effects

    num_ons_added        = add_on_effects(fe("On"), fg("On"), seq_duration_ms, color_palettes, colors, _vocal, structure, registry=registry)
    num_bars_added       = add_bars_effects(fe("Bars"), fg("Bars"), seq_duration_ms, color_palettes, colors, _down, structure, registry=registry)
    num_color_wash_added = add_color_wash_effects(fe("Color Wash"), fg("Color Wash"), seq_duration_ms, color_palettes, colors, _down, structure, registry=registry)
    num_shockwave_added  = add_shockwave_effects(fe("Shockwave"), fg("Shockwave"), seq_duration_ms, color_palettes, colors, _peaks, structure, registry=registry)
    num_spirals_added    = add_spirals_effects(fe("Spirals"), fg("Spirals"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_pinwheel_added   = add_pinwheel_effects(fe("Pinwheel"), fg("Pinwheel"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_single_strand_added = add_single_strand_effects(fe("SingleStrand"), fg("SingleStrand"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_morph_added      = add_morph_effects(fe("Morph"), fg("Morph"), seq_duration_ms, color_palettes, colors, _down, structure, registry=registry)
    num_fill_added       = add_fill_effects(fe("Fill"), fg("Fill"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_ripple_added     = add_ripple_effects(fe("Ripple"), fg("Ripple"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_wave_added       = add_wave_effects(fe("Wave"), fg("Wave"), seq_duration_ms, color_palettes, colors, _down, structure, registry=registry)
    num_twinkle_added    = add_twinkle_effects(fe("Twinkle"), fg("Twinkle"), seq_duration_ms, color_palettes, colors, _vocal, structure, registry=registry)
    num_meteors_added    = add_meteors_effects(fe("Meteors"), fg("Meteors"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_fire_added       = add_fire_effects(fe("Fire"), fg("Fire"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_shimmer_added    = add_shimmer_effects(fe("Shimmer"), fg("Shimmer"), seq_duration_ms, color_palettes, colors, _vocal, structure, registry=registry)
    num_strobe_added     = add_strobe_effects(
        filter_by_effect(chorus_fg, "Strobe", model_categories),
        filter_by_effect(chorus_fg_groups, "Strobe", model_categories),
        seq_duration_ms, color_palettes, colors, _peaks, structure, registry=registry)
    num_fan_added        = add_fan_effects(fe("Fan"), fg("Fan"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_galaxy_added     = add_galaxy_effects(fe("Galaxy"), fg("Galaxy"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_shape_added      = add_shape_effects(fe("Shape"), fg("Shape"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_warp_added       = add_warp_effects(fe("Warp"), fg("Warp"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_marquee_added    = add_marquee_effects(fe("Marquee"), fg("Marquee"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_curtain_added    = add_curtain_effects(fe("Curtain"), fg("Curtain"), seq_duration_ms, color_palettes, colors, _down, structure, registry=registry)
    num_butterfly_added  = add_butterfly_effects(fe("Butterfly"), fg("Butterfly"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_snowflakes_added = add_snowflakes_effects(fe("Snowflakes"), fg("Snowflakes"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_garlands_added   = add_garlands_effects(fe("Garlands"), fg("Garlands"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_spirograph_added = add_spirograph_effects(fe("Spirograph"), fg("Spirograph"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_lightning_added  = add_lightning_effects(
        filter_by_effect(chorus_fg, "Lightning", model_categories),
        filter_by_effect(chorus_fg_groups, "Lightning", model_categories),
        seq_duration_ms, color_palettes, colors, _peaks, structure, registry=registry)
    num_circles_added    = add_circles_effects(fe("Circles"), fg("Circles"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_kaleidoscope_added = add_kaleidoscope_effects(fe("Kaleidoscope"), fg("Kaleidoscope"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_liquid_added     = add_liquid_effects(fe("Liquid"), fg("Liquid"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_plasma_added     = add_plasma_effects(fe("Plasma"), fg("Plasma"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)
    num_fireworks_added  = add_fireworks_effects(
        filter_by_effect(chorus_fg, "Fireworks", model_categories),
        filter_by_effect(chorus_fg_groups, "Fireworks", model_categories),
        seq_duration_ms, color_palettes, colors, _peaks, structure, registry=registry)
    num_tendril_added    = add_tendril_effects(fe("Tendril"), fg("Tendril"), seq_duration_ms, color_palettes, colors, beats, structure, registry=registry)

    set_effect_budget(None)

    # --- DEV: category label overlay — last 5 s, new layer per model ---
    text_start = max(0, seq_duration_ms - 5000)
    text_end   = seq_duration_ms
    _SKIP_CATS = {"skip", "everything_group", "generic_group"}
    for elem in elements:
        name     = elem.attrib.get("name", "")
        category = model_categories.get(name, "")
        if not category or category in _SKIP_CATS:
            continue
        label_layer = ET.SubElement(elem, "EffectLayer")
        palette_parts = [f"C_BUTTON_Palette{i+1}=#FFFFFF" for i in range(8)]
        palette_parts.append("C_CHECKBOX_Palette1=1")
        new_palette      = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = ",".join(palette_parts)
        palette_id       = len(color_palettes) - 1
        settings_str = (
            f"E_TEXTCTRL_Text={category},"
            "E_CHOICE_Text_Dir=none,"
            "E_SLIDER_Text_Speed=10,"
            "E_CHECKBOX_Text_PixelOffsets=0,"
            "E_SLIDER_Text_XStart=0,"
            "E_SLIDER_Text_YStart=50,"
            "E_SLIDER_Text_XEnd=100,"
            "E_SLIDER_Text_YEnd=50,"
            "E_CHOICE_Text_Effect=normal,"
            "T_CHECKBOX_LayerMorph=0,"
            "T_CHECKBOX_OverlayBkg=0,"
            "T_CHOICE_LayerMethod=Normal,"
            "T_SLIDER_SparkleFrequency=200,"
            "T_CHECKBOX_MusicSparkles=0,"
            "T_SLIDER_Brightness=100,"
            "T_SLIDER_Contrast=0,"
            "T_CHECKBOX_ResetAtStart=0"
        )
        place_effect(label_layer, "Text", text_start, text_end, palette_id, settings_str, registry)

    # Write all collected EffectDB entries to XML
    registry.write_to_xml(effect_db_elem)

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
        f"Generated {num_ons_added + num_bars_added + num_color_wash_added + num_shockwave_added + num_spirals_added + num_pinwheel_added + num_single_strand_added + num_morph_added + num_fill_added + num_ripple_added + num_wave_added + num_twinkle_added + num_meteors_added + num_fire_added + num_shimmer_added + num_strobe_added + num_fan_added + num_galaxy_added + num_shape_added + num_warp_added + num_marquee_added + num_curtain_added + num_butterfly_added + num_snowflakes_added + num_garlands_added + num_spirograph_added + num_lightning_added + num_circles_added + num_kaleidoscope_added + num_liquid_added + num_plasma_added + num_fireworks_added + num_tendril_added} custom palettes for effects")
    print(f"Added {num_ons_added} random 'On' effects (1 color each) to models/groups.")
    print(f"Added {num_bars_added} random 'Bars' effects (3 colors each, 5-10s) to models/groups.")
    print(f"Added {num_color_wash_added} random 'Color Wash' effects (2 colors each, 5-10s) to models/groups.")
    print(f"Added {num_shockwave_added} random 'Shockwave' effects (2 colors each, 5-10s) to models/groups.")
    print(f"Added {num_spirals_added} random 'Spirals' effects (2-4 colors each, 5-10s) to models/groups.")
    print(f"Added {num_pinwheel_added} random 'Pinwheel' effects (2-4 colors each, 5-10s) to models/groups.")
    print(f"Added {num_single_strand_added} 'SingleStrand' effects to models/groups.")
    print(f"Added {num_morph_added} 'Morph' effects to models/groups.")
    print(f"Added {num_fill_added} 'Fill' effects to models/groups.")
    print(f"Added {num_ripple_added} 'Ripple' effects to models/groups.")
    print(f"Added {num_wave_added} 'Wave' effects to models/groups.")
    print(f"Added {num_twinkle_added} 'Twinkle' effects to models/groups.")
    print(f"Added {num_meteors_added} 'Meteors' effects to models/groups.")
    print(f"Added {num_fire_added} 'Fire' effects to models/groups.")
    print(f"Added {num_shimmer_added} 'Shimmer' effects to models/groups.")
    print(f"Added {num_strobe_added} 'Strobe' effects to models/groups.")
    print(f"Added {num_fan_added} 'Fan' effects to models/groups.")
    print(f"Added {num_galaxy_added} 'Galaxy' effects to models/groups.")
    print(f"Added {num_shape_added} 'Shape' effects to models/groups.")
    print(f"Added {num_warp_added} 'Warp' effects to models/groups.")
    print(f"Added {num_marquee_added} 'Marquee' effects to models/groups.")
    print(f"Added {num_curtain_added} 'Curtain' effects to models/groups.")
    print(f"Added {num_butterfly_added} 'Butterfly' effects to models/groups.")
    print(f"Added {num_snowflakes_added} 'Snowflakes' effects to models/groups.")
    print(f"Added {num_garlands_added} 'Garlands' effects to models/groups.")
    print(f"Added {num_spirograph_added} 'Spirograph' effects to models/groups.")
    print(f"Added {num_lightning_added} 'Lightning' effects to models/groups.")
    print(f"Added {num_circles_added} 'Circles' effects to models/groups.")
    print(f"Added {num_kaleidoscope_added} 'Kaleidoscope' effects to models/groups.")
    print(f"Added {num_liquid_added} 'Liquid' effects to models/groups.")
    print(f"Added {num_plasma_added} 'Plasma' effects to models/groups.")
    print(f"Added {num_fireworks_added} 'Fireworks' effects to models/groups.")
    print(f"Added {num_tendril_added} 'Tendril' effects to models/groups.")
    if structure:
        print(f"Added structure track with sections: {[s['section'] for s in structure]}")

if __name__ == "__main__":
    _here = os.path.dirname(__file__)
    _td   = os.path.join(_here, "training data")

    parser = argparse.ArgumentParser(
        description="Generate an xLights .xsq sequence file from an audio track."
    )
    parser.add_argument("--audio",     metavar="PATH",
                        help="Path to the audio file (MP3). Omit for Animation mode.")
    parser.add_argument("--type",      metavar="TYPE", default=None,
                        choices=["Media", "Animation"],
                        help="Sequence type. Auto-detected from --audio if omitted.")
    parser.add_argument("--artist",    metavar="NAME", default=None,
                        help="Artist name (used for palette + structure generation).")
    parser.add_argument("--song",      metavar="NAME", default=None,
                        help="Song name (used for palette + structure generation).")
    parser.add_argument("--name",      metavar="NAME", default="AI_Sequence",
                        help="Sequence name embedded in the XSQ (default: AI_Sequence).")
    parser.add_argument("--duration",  metavar="SECS", type=int, default=None,
                        help="Duration in seconds for Animation sequences (random 30-120 if omitted).")
    parser.add_argument("--template",  metavar="PATH",
                        default=os.path.join(_td, "folder 1", "Empty Sequence.xsq"),
                        help="Path to the template XSQ.")
    parser.add_argument("--layout",    metavar="PATH",
                        default=os.path.join(_td, "folder 1", "xlights_rgbeffects.xml"),
                        help="Path to xlights_rgbeffects.xml.")
    parser.add_argument("--output",    metavar="PATH",
                        default=os.path.join(_td, "test outputs", "Empty_AI_Sequence.xsq"),
                        help="Output XSQ file path.")
    parser.add_argument("--structure", metavar="PATH",
                        default=os.path.join(_td, "templates", "xlights_template_structures.json"),
                        help="Path to xlights_template_structures.json.")

    args = parser.parse_args()

    seq_type = args.type or ("Media" if args.audio else "Animation")

    kwargs = dict(
        template_xsq=args.template,
        xlights_xml=args.layout,
        output_xsq=args.output,
        structure_json=args.structure,
        sequence_name=args.name,
        sequence_type=seq_type,
        artist_name=args.artist,
        song_name=args.song,
    )
    if args.audio:
        kwargs["audio_path"] = args.audio
    if args.duration:
        kwargs["duration"] = args.duration

    create_xsq_from_template(**kwargs)