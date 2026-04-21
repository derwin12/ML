# meteors_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_meteors_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_added = 0
    placements = section_effect_placements(8, structure or [], beats or [], min_beats=4, max_beats=16)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 5000)
            end_time = start_time + random.randint(3000, 8000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Meteors")
        count    = p.get("E_SLIDER_Meteors_Count", random.randint(5, 50))
        length   = p.get("E_SLIDER_Meteors_Length", random.randint(1, 25))
        trail    = p.get("E_SLIDER_Meteors_Trail", random.randint(0, 100))
        swirl    = p.get("E_SLIDER_Meteors_Swirl_Intensity", random.randint(0, 20))
        effect   = p.get("E_CHOICE_Meteors_Effect", random.choice(["Fall Down", "Fall Up", "Left", "Right"]))
        met_type = p.get("E_CHOICE_Meteors_Type", random.choice(["Palette", "Rainbow", "Alternate"]))

        num_colors = random.randint(2, 4)
        selected_indices = random.sample(range(1, 9), num_colors)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = ",".join(parts)
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (
            f"E_SLIDER_Meteors_Count={count},"
            f"E_SLIDER_Meteors_Length={length},"
            f"E_SLIDER_Meteors_Trail={trail},"
            f"E_SLIDER_Meteors_Swirl_Intensity={swirl},"
            f"E_CHOICE_Meteors_Effect={effect},"
            f"E_CHOICE_Meteors_Type={met_type},"
            f"E1=100,E2=100"
        )
        place_effect(effect_layer, "Meteors", start_time, end_time, palette_id, settings_str, registry)
        num_added += 1
    return num_added
