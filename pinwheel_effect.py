# pinwheel_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_pinwheel_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_pinwheel_added = 0
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

        p = sample_params("Pinwheel")
        arms      = p.get("E_SLIDER_Pinwheel_Arms", random.randint(1, 8))
        arm_size  = p.get("E_SLIDER_Pinwheel_ArmSize", random.randint(1, 100))
        twist     = p.get("E_SLIDER_Pinwheel_Twist", random.randint(-180, 180))
        thickness = p.get("E_SLIDER_Pinwheel_Thickness", random.randint(0, 100))
        speed     = p.get("E_SLIDER_Pinwheel_Speed", random.randint(1, 50))
        rotation  = p.get("E_CHECKBOX_Pinwheel_Rotation", random.choice([0, 1]))
        xc_adj    = p.get("E_SLIDER_Pinwheel_XC_Adj", random.randint(-100, 100))
        yc_adj    = p.get("E_SLIDER_Pinwheel_YC_Adj", random.randint(-100, 100))
        style     = p.get("E_CHOICE_Pinwheel_Style", random.randint(0, 3))
        offset    = p.get("E_SLIDER_Pinwheel_Offset", random.randint(0, 100))

        # Select 2-4 random distinct color indices (1-8) for Pinwheel
        num_colors = random.randint(2, 4)
        selected_indices = random.sample(range(1, 9), num_colors)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        # Add the ColorPalette
        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str

        # Palette ID
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (f"E_SLIDER_Pinwheel_Arms={arms},"
                        f"E_SLIDER_Pinwheel_ArmSize={arm_size},"
                        f"E_SLIDER_Pinwheel_Twist={twist},"
                        f"E_SLIDER_Pinwheel_Thickness={thickness},"
                        f"E_SLIDER_Pinwheel_Speed={speed},"
                        f"E_CHECKBOX_Pinwheel_Rotation={rotation},"
                        f"E_SLIDER_Pinwheel_XC_Adj={xc_adj},"
                        f"E_SLIDER_Pinwheel_YC_Adj={yc_adj},"
                        f"E_CHOICE_Pinwheel_Style={style},"
                        f"E_SLIDER_Pinwheel_Offset={offset},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Pinwheel", start_time, end_time, palette_id, settings_str, registry)
        num_pinwheel_added += 1
    return num_pinwheel_added
