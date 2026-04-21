# tendril_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_tendril_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_tendril_added = 0
    placements = section_effect_placements(5, structure or [], beats or [], min_beats=5, max_beats=18)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(5000, 12000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Tendril")
        movement    = p.get("E_SLIDER_Tendril_Movement", random.randint(1, 100))
        thickness   = p.get("E_SLIDER_Tendril_Thickness", random.randint(1, 10))
        speed       = p.get("E_SLIDER_Tendril_Speed", random.randint(1, 50))
        length      = p.get("E_SLIDER_Tendril_Length", random.randint(1, 100))
        num_tendrils= p.get("E_SLIDER_Tendril_Num", random.randint(1, 8))
        tune_fft    = p.get("E_SLIDER_Tendril_Tune_FFT", random.randint(0, 10))

        num_colors = random.randint(2, 3)
        selected_indices = random.sample(range(1, 9), num_colors)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = palette_str
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (f"E_SLIDER_Tendril_Movement={movement},"
                        f"E_SLIDER_Tendril_Thickness={thickness},"
                        f"E_SLIDER_Tendril_Speed={speed},"
                        f"E_SLIDER_Tendril_Length={length},"
                        f"E_SLIDER_Tendril_Num={num_tendrils},"
                        f"E_SLIDER_Tendril_Tune_FFT={tune_fft},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Tendril", start_time, end_time, palette_id, settings_str, registry)
        num_tendril_added += 1
    return num_tendril_added
