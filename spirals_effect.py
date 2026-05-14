# spirals_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_spirals_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_spirals_added = 0
    placements = section_effect_placements(15, structure or [], beats or [], min_beats=5, max_beats=16)
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

        p = sample_params("Spirals")
        cycles      = p.get("E_SLIDER_Spirals_Cycles", round(random.uniform(1, 5), 1))
        rotation    = p.get("E_SLIDER_Spirals_Rotation", random.randint(-180, 180))
        thickness   = p.get("E_SLIDER_Spirals_Thickness", random.randint(1, 50))
        blend       = p.get("E_CHECKBOX_Spirals_Blend", random.choice([0, 1]))
        direction   = p.get("E_CHECKBOX_Spirals_Direction", random.choice([0, 1]))
        growth      = p.get("E_SLIDER_Spirals_Growth", random.randint(-50, 50))
        start_width = p.get("E_SLIDER_Spirals_Start_Width", random.randint(1, 100))
        end_width   = p.get("E_SLIDER_Spirals_End_Width", random.randint(1, 100))

        # Select 2 random distinct color indices (1-8) for Spirals
        selected_indices = random.sample(range(1, 9), 2)
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

        settings_str = (f"E_SLIDER_Spirals_Cycles={cycles:.1f},"
                        f"E_SLIDER_Spirals_Rotation={rotation},"
                        f"E_SLIDER_Spirals_Thickness={thickness},"
                        f"E_CHECKBOX_Spirals_Blend={blend},"
                        f"E_CHECKBOX_Spirals_3D={random.choice([0, 1])},"
                        f"E_CHECKBOX_Spirals_Direction={direction},"
                        f"E_SLIDER_Spirals_Growth={growth},"
                        f"E_SLIDER_Spirals_Start_Width={start_width},"
                        f"E_SLIDER_Spirals_End_Width={end_width},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Spirals", start_time, end_time, palette_id, settings_str, registry)
        num_spirals_added += 1
    return num_spirals_added
