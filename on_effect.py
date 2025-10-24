# on_effect.py

import xml.etree.ElementTree as ET
import random

def add_on_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None):
    num_ons_added = 0
    for _ in range(10):
        # 30% chance to pick group if available
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)  # fallback to all eligible

        effect_layer = elem.find("EffectLayer")
        if effect_layer is None:
            effect_layer = ET.SubElement(elem, "EffectLayer")

        if beats is not None and len(beats) > 1:
            start_idx = random.randint(0, len(beats) - 2)
            num_beats_span = random.randint(1, 3)  # for 1-3s duration
            end_idx = min(start_idx + num_beats_span, len(beats) - 1)
            start_time = int(beats[start_idx] * 1000)
            end_time = int(beats[end_idx] * 1000)
        else:
            start_time = random.randint(0, seq_duration_ms - 2000)
            effect_dur = random.randint(1000, 3000)  # 1-3 seconds
            end_time = start_time + effect_dur

        # Select 1 random color index (1-8)
        selected_indices = [random.randint(1, 8)]
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        # Add the ColorPalette
        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str

        # Palette ID is 0-based index of this new one (after template's)
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        effect = ET.SubElement(effect_layer, "Effect", {
            "name": "On",
            "startTime": f"{start_time}",
            "endTime": f"{end_time}",
            "selected": "0",
            "palette": str(palette_id)
        })
        settings = ET.SubElement(effect, "Settings")
        # Settings without C1, using palette
        settings.text = "E1=100;E2=100;T1=0;CHECKBOX_Shimmer=0"
        num_ons_added += 1
    return num_ons_added