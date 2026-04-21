# spatial_sweep.py
#
# Fires a staggered "On" effect across models sorted by their X position,
# creating a left-to-right (or right-to-left) visual sweep at each phrase boundary.
# Direction alternates phrase-by-phrase within a section.

import xml.etree.ElementTree as ET
import random
from utils import get_or_create_layer, place_effect, section_intensity, get_section_for_beat


# Minimum section intensity to fire a sweep (skips intro/outro/breakdown)
_SWEEP_INTENSITY_THRESHOLD = 0.5

# Maximum number of sweeps per section (prevents saturation in long choruses)
_MAX_SWEEPS_PER_SECTION = 3


def add_spatial_sweep_effects(
    sorted_elements,        # eligible elements sorted by WorldPosX (left → right)
    seq_duration_ms: int,
    color_palettes,
    fixed_colors: list,
    phrase_boundaries: list,
    structure: list = None,
    registry=None,
) -> int:
    """
    At each musical phrase boundary, fire a staggered On effect across all eligible
    models in spatial order. The result is a visual sweep from left to right (or
    right to left) that is tied to phrase starts rather than arbitrary beats.

    Returns the number of individual On effects placed.
    """
    if not sorted_elements or not phrase_boundaries:
        return 0

    n_models = len(sorted_elements)
    num_added = 0

    # Track how many sweeps have fired per section label (cap at _MAX_SWEEPS_PER_SECTION)
    section_sweep_counts: dict = {}

    # Stagger so the full sweep finishes within ~1 second regardless of prop count
    stagger_ms = max(15, min(80, 1000 // max(n_models, 1)))
    effect_hold_ms = 500  # each prop stays lit for 500 ms

    phrase_dir = 0  # alternates direction each phrase

    for phrase_start in phrase_boundaries:
        if phrase_start + stagger_ms * n_models > seq_duration_ms:
            break

        # Section gate: skip low-energy sections
        section_label = "unknown"
        if structure:
            sec = get_section_for_beat(phrase_start, structure)
            if sec:
                section_label = sec["section"]
                if section_intensity(section_label) < _SWEEP_INTENSITY_THRESHOLD:
                    continue

        # Per-section cap
        count = section_sweep_counts.get(section_label, 0)
        if count >= _MAX_SWEEPS_PER_SECTION:
            continue
        section_sweep_counts[section_label] = count + 1

        # Pick a single color for the whole sweep to keep it cohesive
        color_idx = random.randint(0, 7)
        parts = [f"C_BUTTON_Palette{i + 1}={fixed_colors[i]}" for i in range(8)]
        parts.append(f"C_CHECKBOX_Palette{color_idx + 1}=1")
        palette_str = ",".join(parts)

        # Alternate direction each phrase within a section
        ordered = sorted_elements if phrase_dir % 2 == 0 else list(reversed(sorted_elements))
        phrase_dir += 1

        for i, elem in enumerate(ordered):
            start_ms = phrase_start + i * stagger_ms
            end_ms = start_ms + effect_hold_ms
            if end_ms > seq_duration_ms:
                break

            effect_layer = get_or_create_layer(elem, start_ms, end_ms, skip_budget=True)
            if effect_layer is None:
                continue

            new_palette = ET.SubElement(color_palettes, "ColorPalette")
            new_palette.text = palette_str
            palette_id = len(color_palettes.findall("ColorPalette")) - 1

            place_effect(effect_layer, "On", start_ms, end_ms, palette_id, "E1=100,E2=100", registry)
            num_added += 1

    return num_added
