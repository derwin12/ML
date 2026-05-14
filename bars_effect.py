# bars_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_bars_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    directions = ["Up", "Down", "Expand", "Compress", "Left/Right", "H Expand", "H Compress", "Alternate"]
    num_bars_added = 0
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

        p = sample_params("Bars")
        bar_count = p.get("BarCount", random.randint(3, 8))
        direction = p.get("Direction", random.choice(directions))
        cycles = p.get("Cycles", round(random.uniform(1, 3), 1))
        palette_rep = p.get("PaletteRep", random.randint(1, 4))
        highlight = p.get("CHECKBOX_Highlight", random.choice([0, 1]))
        threed = p.get("CHECKBOX_3D", random.choice([0, 1]))
        gradient = p.get("CHECKBOX_Gradient", random.choice([0, 1]))
        use_first_for_highlight = p.get("CHECKBOX_UseFirstColorForHighlight", 0)

        # Select 3 random distinct color indices (1-8)
        selected_indices = random.sample(range(1, 9), 3)
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        # Add the ColorPalette
        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str

        # Palette ID
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (f"BarCount={bar_count},"
                        f"Direction={direction},"
                        f"Cycles={cycles:.1f},"
                        f"PaletteRep={palette_rep},"
                        f"CHECKBOX_Highlight={highlight},"
                        f"CHECKBOX_3D={threed},"
                        f"CHECKBOX_Gradient={gradient},"
                        f"CHECKBOX_UseFirstColorForHighlight={use_first_for_highlight},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Bars", start_time, end_time, palette_id, settings_str, registry)
        num_bars_added += 1
    return num_bars_added
