# color_wash_effect.py

import xml.etree.ElementTree as ET
import random

def add_color_wash_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors):
    num_color_wash = random.randint(5, 15)
    num_color_wash_added = 0
    for _ in range(num_color_wash):
        # 30% chance to pick group if available
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)  # fallback to all eligible

        effect_layer = elem.find("EffectLayer")
        if effect_layer is None:
            effect_layer = ET.SubElement(elem, "EffectLayer")

        start_time = random.randint(0, seq_duration_ms - 10000)
        effect_dur = random.randint(5000, 10000)  # 5-10 seconds
        end_time = start_time + effect_dur

        # Random parameters for Color Wash
        count = random.randint(1, 5)
        vfade = random.choice([0, 1])
        hfade = random.choice([0, 1])
        shimmer = random.choice([0, 1])
        circ = random.choice([0, 1])

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

        effect = ET.SubElement(effect_layer, "Effect", {
            "name": "Color Wash",
            "startTime": f"{start_time}",
            "endTime": f"{end_time}",
            "selected": "0",
            "palette": str(palette_id)
        })
        settings = ET.SubElement(effect, "Settings")
        # Settings without C1 C2, using palette
        settings.text = (f"Count={count};"
                         f"CHECKBOX_VerticalFade={vfade};"
                         f"CHECKBOX_HorizontalFade={hfade};"
                         f"CHECKBOX_Shimmer={shimmer};"
                         f"CHECKBOX_CircularPalette={circ};"
                         f"E1=100;E2=100")
        num_color_wash_added += 1
    return num_color_wash_added