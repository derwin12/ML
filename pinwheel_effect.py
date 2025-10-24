# pinwheel_effect.py

import xml.etree.ElementTree as ET
import random

def add_pinwheel_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None):
    num_pinwheel = random.randint(10, 30)
    num_pinwheel_added = 0
    for _ in range(num_pinwheel):
        # 30% chance to pick group if available
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)  # fallback to all eligible

        effect_layer = elem.find("EffectLayer")
        if effect_layer is None:
            effect_layer = ET.SubElement(elem, "EffectLayer")

        if beats is not None and len(beats) > 1:
            start_idx = random.randint(0, len(beats) - 6)
            num_beats_span = random.randint(5, 10)  # for 5-10s duration
            end_idx = min(start_idx + num_beats_span, len(beats) - 1)
            start_time = int(beats[start_idx] * 1000)
            end_time = int(beats[end_idx] * 1000)
        else:
            start_time = random.randint(0, seq_duration_ms - 10000)
            effect_dur = random.randint(5000, 10000)  # 5-10 seconds
            end_time = start_time + effect_dur

        # Random parameters for Pinwheel
        arms = random.randint(1, 8)
        arm_size = random.randint(1, 100)
        twist = random.randint(-180, 180)
        thickness = random.randint(0, 100)
        speed = random.randint(1, 50)
        rotation = random.choice([0, 1])
        xc_adj = random.randint(-100, 100)
        yc_adj = random.randint(-100, 100)
        style = random.randint(0, 3)  # Assuming 4 styles
        offset = random.randint(0, 100)

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

        effect = ET.SubElement(effect_layer, "Effect", {
            "name": "Pinwheel",
            "startTime": f"{start_time}",
            "endTime": f"{end_time}",
            "selected": "0",
            "palette": str(palette_id)
        })
        settings = ET.SubElement(effect, "Settings")
        # Settings for Pinwheel using palette
        settings.text = (f"E_SLIDER_Pinwheel_Arms={arms};"
                         f"E_SLIDER_Pinwheel_ArmSize={arm_size};"
                         f"E_SLIDER_Pinwheel_Twist={twist};"
                         f"E_SLIDER_Pinwheel_Thickness={thickness};"
                         f"E_SLIDER_Pinwheel_Speed={speed};"
                         f"E_CHECKBOX_Pinwheel_Rotation={rotation};"
                         f"E_SLIDER_Pinwheel_XC_Adj={xc_adj};"
                         f"E_SLIDER_Pinwheel_YC_Adj={yc_adj};"
                         f"E_CHOICE_Pinwheel_Style={style};"
                         f"E_SLIDER_Pinwheel_Offset={offset};"
                         f"E1=100;E2=100")
        num_pinwheel_added += 1
    return num_pinwheel_added