# spirals_effect.py

import xml.etree.ElementTree as ET
import random

def add_spirals_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None):
    num_spirals = random.randint(10, 30)
    num_spirals_added = 0
    for _ in range(num_spirals):
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

        # Random parameters for Spirals
        cycles = random.uniform(1, 5)
        rotation = random.randint(-180, 180)
        thickness = random.randint(1, 50)
        blend = random.choice([0, 1])
        direction = random.choice([0, 1])  # 0: clockwise, 1: counter-clockwise
        growth = random.randint(-50, 50)
        start_width = random.randint(1, 100)
        end_width = random.randint(1, 100)

        # Select 2 random distinct color indices (1-8) for Spirals
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
            "name": "Spirals",
            "startTime": f"{start_time}",
            "endTime": f"{end_time}",
            "selected": "0",
            "palette": str(palette_id)
        })
        settings = ET.SubElement(effect, "Settings")
        # Settings for Spirals using palette
        settings.text = (f"E_SLIDER_Spirals_Cycles={cycles:.1f};"
                         f"E_SLIDER_Spirals_Rotation={rotation};"
                         f"E_SLIDER_Spirals_Thickness={thickness};"
                         f"E_CHECKBOX_Spirals_Blend={blend};"
                         f"E_CHECKBOX_Spirals_3D={random.choice([0, 1])}; "
                         f"E_CHECKBOX_Spirals_Direction={direction};"
                         f"E_SLIDER_Spirals_Growth={growth};"
                         f"E_SLIDER_Spirals_Start_Width={start_width};"
                         f"E_SLIDER_Spirals_End_Width={end_width};"
                         f"E1=100;E2=100")
        num_spirals_added += 1
    return num_spirals_added