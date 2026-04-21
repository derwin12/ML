# morph_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, get_or_create_layer, place_effect
from param_sampler import sample_params

def add_morph_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_added = 0
    placements = section_effect_placements(15, structure or [], beats or [], min_beats=2, max_beats=12)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 5000)
            end_time = start_time + random.randint(2000, 8000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Morph")
        start_x1   = p.get("E_SLIDER_Morph_Start_X1", random.randint(0, 100))
        start_y1   = p.get("E_SLIDER_Morph_Start_Y1", random.randint(0, 100))
        start_x2   = p.get("E_SLIDER_Morph_Start_X2", random.randint(0, 100))
        start_y2   = p.get("E_SLIDER_Morph_Start_Y2", random.randint(0, 100))
        end_x1     = p.get("E_SLIDER_Morph_End_X1", random.randint(0, 100))
        end_y1     = p.get("E_SLIDER_Morph_End_Y1", random.randint(0, 100))
        end_x2     = p.get("E_SLIDER_Morph_End_X2", random.randint(0, 100))
        end_y2     = p.get("E_SLIDER_Morph_End_Y2", random.randint(0, 100))
        duration   = p.get("E_SLIDER_Morph_Duration", random.randint(10, 100))
        accel      = p.get("E_SLIDER_Morph_Accel", random.randint(-10, 10))
        repeat     = p.get("E_CHECKBOX_Morph_Repeat_Count", random.choice([0, 1]))
        show_tail  = p.get("E_CHECKBOX_Morph_Show_Tail", random.choice([0, 1]))
        head_dur   = p.get("E_SLIDER_Morph_Head_Duration", random.randint(10, 50))
        head_start = p.get("E_SLIDER_Morph_Head_Start_Length", random.randint(1, 20))
        head_end   = p.get("E_SLIDER_Morph_Head_End_Length", random.randint(1, 20))

        num_colors = random.randint(2, 4)
        selected_indices = random.sample(range(1, 9), num_colors)
        parts = [f"C_BUTTON_Palette{i+1}={fixed_colors[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")

        new_palette = ET.SubElement(color_palettes, "ColorPalette")
        new_palette.text = ",".join(parts)
        palette_id = len(color_palettes.findall("ColorPalette")) - 1

        settings_str = (
            f"E_SLIDER_Morph_Start_X1={start_x1},"
            f"E_SLIDER_Morph_Start_Y1={start_y1},"
            f"E_SLIDER_Morph_Start_X2={start_x2},"
            f"E_SLIDER_Morph_Start_Y2={start_y2},"
            f"E_SLIDER_Morph_End_X1={end_x1},"
            f"E_SLIDER_Morph_End_Y1={end_y1},"
            f"E_SLIDER_Morph_End_X2={end_x2},"
            f"E_SLIDER_Morph_End_Y2={end_y2},"
            f"E_SLIDER_Morph_Duration={duration},"
            f"E_SLIDER_Morph_Accel={accel},"
            f"E_CHECKBOX_Morph_Repeat_Count={repeat},"
            f"E_CHECKBOX_Morph_Show_Tail={show_tail},"
            f"E_SLIDER_Morph_Head_Duration={head_dur},"
            f"E_SLIDER_Morph_Head_Start_Length={head_start},"
            f"E_SLIDER_Morph_Head_End_Length={head_end},"
            f"E1=100,E2=100"
        )
        place_effect(effect_layer, "Morph", start_time, end_time, palette_id, settings_str, registry)
        num_added += 1
    return num_added
