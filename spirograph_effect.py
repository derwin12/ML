# spirograph_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_spirograph_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_spirograph_added = 0
    placements = section_effect_placements(6, structure or [], beats or [], min_beats=6, max_beats=20)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(6000, 12000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Spirograph")
        r          = p.get("E_SLIDER_Spirograph_R", random.randint(1, 100))
        r2         = p.get("E_SLIDER_Spirograph_r", random.randint(1, 100))
        d          = p.get("E_SLIDER_Spirograph_d", random.randint(1, 100))
        speed      = p.get("E_SLIDER_Spirograph_Speed", random.randint(1, 50))
        animate    = p.get("E_CHECKBOX_Spirograph_Animate", random.choice([0, 1]))
        length     = p.get("E_SLIDER_Spirograph_Length", random.randint(1, 100))

        num_colors = random.randint(2, 4)
        selected_indices = random.sample(range(1, 9), num_colors)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (f"E_SLIDER_Spirograph_R={r},"
                        f"E_SLIDER_Spirograph_r={r2},"
                        f"E_SLIDER_Spirograph_d={d},"
                        f"E_SLIDER_Spirograph_Speed={speed},"
                        f"E_CHECKBOX_Spirograph_Animate={animate},"
                        f"E_SLIDER_Spirograph_Length={length},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Spirograph", start_time, end_time, palette_id, settings_str, registry)
        num_spirograph_added += 1
    return num_spirograph_added
