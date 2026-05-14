# liquid_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_liquid_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_liquid_added = 0
    placements = section_effect_placements(6, structure or [], beats or [], min_beats=6, max_beats=20)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(6000, 14000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Liquid")
        speed        = p.get("E_SLIDER_Liquid_Speed", random.randint(1, 50))
        num_drops    = p.get("E_SLIDER_Liquid_Streams", random.randint(1, 10))
        thickness    = p.get("E_SLIDER_Liquid_Thickness", random.randint(1, 10))
        draw_blur    = p.get("E_CHECKBOX_Liquid_DrawBackground", random.choice([0, 1]))
        erase        = p.get("E_CHECKBOX_Liquid_Erase", random.choice([0, 1]))

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

        settings_str = (f"E_SLIDER_Liquid_Speed={speed},"
                        f"E_SLIDER_Liquid_Streams={num_drops},"
                        f"E_SLIDER_Liquid_Thickness={thickness},"
                        f"E_CHECKBOX_Liquid_DrawBackground={draw_blur},"
                        f"E_CHECKBOX_Liquid_Erase={erase},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Liquid", start_time, end_time, palette_id, settings_str, registry)
        num_liquid_added += 1
    return num_liquid_added
