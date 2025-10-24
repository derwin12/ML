# bars_effect.py

import xml.etree.ElementTree as ET
import random

def add_bars_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors):
    directions = ["Up", "Down", "Expand", "Compress", "Left/Right", "H Expand", "H Compress", "Alternate"]
    num_bars_added = 0
    for _ in range(10):
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

        # Random parameters for Bars
        bar_count = random.randint(3, 8)
        direction = random.choice(directions)
        cycles = random.uniform(1, 3)
        palette_rep = random.randint(1, 4)
        highlight = random.choice([0, 1])
        threed = random.choice([0, 1])
        gradient = random.choice([0, 1])
        use_first_for_highlight = 0  # default

        # Select 3 random distinct color indices (1-8)
        selected_indices = random.sample(range(1, 9), 3)
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
            "name": "Bars",
            "startTime": f"{start_time}",
            "endTime": f"{end_time}",
            "selected": "0",
            "palette": str(palette_id)
        })
        settings = ET.SubElement(effect, "Settings")
        # Settings without C1 C2, using palette
        settings.text = (f"BarCount={bar_count};"
                         f"Direction={direction};"
                         f"Cycles={cycles:.1f};"
                         f"PaletteRep={palette_rep};"
                         f"CHECKBOX_Highlight={highlight};"
                         f"CHECKBOX_3D={threed};"
                         f"CHECKBOX_Gradient={gradient};"
                         f"CHECKBOX_UseFirstColorForHighlight={use_first_for_highlight};"
                         f"E1=100;E2=100")
        num_bars_added += 1
    return num_bars_added