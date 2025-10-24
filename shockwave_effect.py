# shockwave_effect.py

import xml.etree.ElementTree as ET
import random

def add_shockwave_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors):
    num_shockwave = random.randint(5, 10)
    num_shockwave_added = 0
    for _ in range(num_shockwave):
        # 30% chance to pick group if available
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
            is_group = True
        else:
            elem = random.choice(eligible_elements)  # fallback to all eligible
            is_group = elem.attrib["name"] in [g.attrib["name"] for g in eligible_group_elements]

        effect_layer = elem.find("EffectLayer")
        if effect_layer is None:
            effect_layer = ET.SubElement(elem, "EffectLayer")

        start_time = random.randint(0, seq_duration_ms - 10000)
        effect_dur = random.randint(5000, 10000)  # 5-10 seconds
        end_time = start_time + effect_dur

        # Random parameters for Shockwave
        center_x = random.randint(0, 100)
        center_y = random.randint(0, 100)
        cycles = random.uniform(1, 5)
        start_radius = random.randint(1, 10)
        start_width = random.randint(1, 10)
        end_width = random.randint(5, 20)
        accel = random.randint(-50, 50)
        blend_edges = random.choice([0, 1])
        scale = random.choice([0, 1])

        # Set end_radius based on whether it's a group or model
        end_radius = random.randint(50, 200) if is_group else random.randint(20, 50)

        # Select 2 random distinct color indices (1-8) for Shockwave
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
            "name": "Shockwave",
            "startTime": f"{start_time}",
            "endTime": f"{end_time}",
            "selected": "0",
            "palette": str(palette_id)
        })
        settings = ET.SubElement(effect, "Settings")
        # Settings for Shockwave using palette
        settings.text = (f"E_SLIDER_Shockwave_CenterX={center_x};"
                         f"E_SLIDER_Shockwave_CenterY={center_y};"
                         f"E_SLIDER_Shockwave_Cycles={cycles:.1f};"
                         f"E_SLIDER_Shockwave_Start_Radius={start_radius};"
                         f"E_SLIDER_Shockwave_End_Radius={end_radius};"
                         f"E_SLIDER_Shockwave_Start_Width={start_width};"
                         f"E_SLIDER_Shockwave_End_Width={end_width};"
                         f"E_SLIDER_Shockwave_Accel={accel};"
                         f"E_CHECKBOX_Shockwave_Blend_Edges={blend_edges};"
                         f"E_CHECKBOX_Shockwave_Scale={scale};"
                         f"E1=100;E2=100")
        num_shockwave_added += 1
    return num_shockwave_added