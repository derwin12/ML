# color_wash_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_color_wash_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_color_wash_added = 0
    placements = section_effect_placements(10, structure or [], beats or [], min_beats=5, max_beats=16)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(5000, 10000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Color Wash")
        count = p.get("Count", random.randint(1, 5))
        vfade = p.get("CHECKBOX_VerticalFade", random.choice([0, 1]))
        hfade = p.get("CHECKBOX_HorizontalFade", random.choice([0, 1]))
        shimmer = p.get("CHECKBOX_Shimmer", random.choice([0, 1]))
        circ = p.get("CHECKBOX_CircularPalette", random.choice([0, 1]))

        # Select 2 random distinct color indices (1-8)
        selected_indices = random.sample(range(1, 9), 2)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        # Add the ColorPalette
        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str

        # Palette ID
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (f"Count={count},"
                        f"CHECKBOX_VerticalFade={vfade},"
                        f"CHECKBOX_HorizontalFade={hfade},"
                        f"CHECKBOX_Shimmer={shimmer},"
                        f"CHECKBOX_CircularPalette={circ},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Color Wash", start_time, end_time, palette_id, settings_str, registry)
        num_color_wash_added += 1
    return num_color_wash_added
