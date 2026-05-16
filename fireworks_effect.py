# fireworks_effect.py

import random
from utils import chorus_only_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_fireworks_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_fireworks_added = 0
    placements = chorus_only_placements(5, structure or [], beats or [], min_beats=4, max_beats=14)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 8000)
            end_time = start_time + random.randint(4000, 10000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Fireworks")
        num_explosions = p.get("E_SLIDER_Fireworks_Number_Explosions", random.randint(1, 10))
        count          = p.get("E_SLIDER_Fireworks_Count", random.randint(1, 100))
        velocity_min   = p.get("E_SLIDER_Fireworks_Velocity_Min", random.randint(1, 10))
        velocity_max   = p.get("E_SLIDER_Fireworks_Velocity_Max", random.randint(10, 50))
        fade           = p.get("E_SLIDER_Fireworks_Fade", random.randint(1, 100))
        gravity        = p.get("E_SLIDER_Fireworks_Gravity", random.randint(1, 100))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_SLIDER_Fireworks_Number_Explosions={num_explosions},"
                        f"E_SLIDER_Fireworks_Count={count},"
                        f"E_SLIDER_Fireworks_Velocity_Min={velocity_min},"
                        f"E_SLIDER_Fireworks_Velocity_Max={velocity_max},"
                        f"E_SLIDER_Fireworks_Fade={fade},"
                        f"E_SLIDER_Fireworks_Gravity={gravity},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Fireworks", start_time, end_time, palette_id, settings_str, registry)
        num_fireworks_added += 1
    return num_fireworks_added
