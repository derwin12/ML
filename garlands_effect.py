# garlands_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_garlands_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_garlands_added = 0
    placements = section_effect_placements(8, structure or [], beats or [], min_beats=5, max_beats=18)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(5000, 12000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Garlands")
        garland_type = p.get("E_SLIDER_Garlands_Type", random.randint(0, 4))
        speed        = p.get("E_SLIDER_Garlands_Speed", random.randint(1, 50))
        spacing      = p.get("E_SLIDER_Garlands_Spacing", random.randint(1, 20))
        direction    = p.get("E_CHOICE_Garlands_Direction", random.choice(["Down", "Up", "Left", "Right"]))

        num_colors = random.randint(2, 4)
        selected_indices = random.sample(range(1, 9), num_colors)
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (f"E_SLIDER_Garlands_Type={garland_type},"
                        f"E_SLIDER_Garlands_Speed={speed},"
                        f"E_SLIDER_Garlands_Spacing={spacing},"
                        f"E_CHOICE_Garlands_Direction={direction},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Garlands", start_time, end_time, palette_id, settings_str, registry)
        num_garlands_added += 1
    return num_garlands_added
