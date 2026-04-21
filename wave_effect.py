# wave_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_wave_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_added = 0
    placements = section_effect_placements(8, structure or [], beats or [], min_beats=4, max_beats=16)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 5000)
            end_time = start_time + random.randint(3000, 8000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Wave")
        height    = p.get("E_SLIDER_Wave_Height", random.randint(1, 100))
        length    = p.get("E_SLIDER_Wave_Length", random.randint(1, 100))
        speed     = p.get("E_SLIDER_Wave_Speed", random.randint(1, 50))
        thickness = p.get("E_SLIDER_Wave_Thickness", random.randint(1, 50))
        direction = p.get("E_CHOICE_Wave_Direction", random.choice(["Left", "Right", "Up", "Down"]))
        wave_type = p.get("E_CHOICE_Wave_Type", random.choice(["Sine", "Triangle", "Square", "Decaying Sine", "Decaying Cosine"]))
        mirror    = p.get("E_CHECKBOX_Wave_Mirror", random.choice([0, 1]))

        num_colors = random.randint(2, 3)
        selected_indices = random.sample(range(1, 9), num_colors)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = ",".join(parts)
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (
            f"E_SLIDER_Wave_Height={height},"
            f"E_SLIDER_Wave_Length={length},"
            f"E_SLIDER_Wave_Speed={speed},"
            f"E_SLIDER_Wave_Thickness={thickness},"
            f"E_CHOICE_Wave_Direction={direction},"
            f"E_CHOICE_Wave_Type={wave_type},"
            f"E_CHECKBOX_Wave_Mirror={mirror},"
            f"E1=100,E2=100"
        )
        place_effect(effect_layer, "Wave", start_time, end_time, palette_id, settings_str, registry)
        num_added += 1
    return num_added
