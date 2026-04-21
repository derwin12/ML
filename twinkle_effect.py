# twinkle_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_twinkle_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_added = 0
    placements = section_effect_placements(10, structure or [], beats or [], min_beats=4, max_beats=16)
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

        p = sample_params("Twinkle")
        count    = p.get("E_SLIDER_Twinkle_Count", random.randint(50, 200))
        steps    = p.get("E_SLIDER_Twinkle_Steps", random.randint(10, 100))
        strobe   = p.get("E_CHECKBOX_Twinkle_Strobe", random.choice([0, 1]))
        rerandom = p.get("E_CHECKBOX_Twinkle_ReRandom", random.choice([0, 1]))

        num_colors = random.randint(2, 4)
        selected_indices = random.sample(range(1, 9), num_colors)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = ",".join(parts)
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (
            f"E_SLIDER_Twinkle_Count={count},"
            f"E_SLIDER_Twinkle_Steps={steps},"
            f"E_CHECKBOX_Twinkle_Strobe={strobe},"
            f"E_CHECKBOX_Twinkle_ReRandom={rerandom},"
            f"E1=100,E2=100"
        )
        place_effect(effect_layer, "Twinkle", start_time, end_time, palette_id, settings_str, registry)
        num_added += 1
    return num_added
