# plasma_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_plasma_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_plasma_added = 0
    placements = section_effect_placements(5, structure or [], beats or [], min_beats=6, max_beats=20)
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

        p = sample_params("Plasma")
        style    = p.get("E_SLIDER_Plasma_Style", random.randint(1, 4))
        line1    = p.get("E_SLIDER_Plasma_Line1", round(random.uniform(0.5, 5.0), 1))
        line2    = p.get("E_SLIDER_Plasma_Line2", round(random.uniform(0.5, 5.0), 1))
        line3    = p.get("E_SLIDER_Plasma_Line3", round(random.uniform(0.5, 5.0), 1))
        line4    = p.get("E_SLIDER_Plasma_Line4", round(random.uniform(0.5, 5.0), 1))
        speed    = p.get("E_SLIDER_Plasma_Speed", random.randint(1, 50))

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

        settings_str = (f"E_SLIDER_Plasma_Style={style},"
                        f"E_SLIDER_Plasma_Line1={line1:.1f},"
                        f"E_SLIDER_Plasma_Line2={line2:.1f},"
                        f"E_SLIDER_Plasma_Line3={line3:.1f},"
                        f"E_SLIDER_Plasma_Line4={line4:.1f},"
                        f"E_SLIDER_Plasma_Speed={speed},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Plasma", start_time, end_time, palette_id, settings_str, registry)
        num_plasma_added += 1
    return num_plasma_added
