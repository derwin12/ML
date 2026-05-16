# marquee_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_marquee_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_marquee_added = 0
    placements = section_effect_placements(10, structure or [], beats or [], min_beats=4, max_beats=16)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 8000)
            end_time = start_time + random.randint(4000, 10000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Marquee")
        band_size    = p.get("E_SLIDER_Marquee_Band_Size", random.randint(1, 20))
        skip_size    = p.get("E_SLIDER_Marquee_Skip_Size", random.randint(0, 20))
        speed        = p.get("E_SLIDER_Marquee_Speed", random.randint(1, 50))
        start_pos    = p.get("E_SLIDER_Marquee_Start_Pos", random.randint(0, 100))
        reverse      = p.get("E_CHECKBOX_Marquee_Reverse", random.choice([0, 1]))
        scale        = p.get("E_CHECKBOX_Marquee_Scale", random.choice([0, 1]))
        x_center     = p.get("E_SLIDER_Marquee_X_Center", random.randint(0, 100))
        y_center     = p.get("E_SLIDER_Marquee_Y_Center", random.randint(0, 100))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_SLIDER_Marquee_Band_Size={band_size},"
                        f"E_SLIDER_Marquee_Skip_Size={skip_size},"
                        f"E_SLIDER_Marquee_Speed={speed},"
                        f"E_SLIDER_Marquee_Start_Pos={start_pos},"
                        f"E_CHECKBOX_Marquee_Reverse={reverse},"
                        f"E_CHECKBOX_Marquee_Scale={scale},"
                        f"E_SLIDER_Marquee_X_Center={x_center},"
                        f"E_SLIDER_Marquee_Y_Center={y_center},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Marquee", start_time, end_time, palette_id, settings_str, registry)
        num_marquee_added += 1
    return num_marquee_added
