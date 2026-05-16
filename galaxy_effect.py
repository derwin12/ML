# galaxy_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_galaxy_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_galaxy_added = 0
    placements = section_effect_placements(10, structure or [], beats or [], min_beats=6, max_beats=20)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(6000, 12000)
        if random.random() < 0.4 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("Galaxy")
        accel           = p.get("E_SLIDER_Galaxy_Accel", random.randint(-10, 10))
        angle_offset    = p.get("E_SLIDER_Galaxy_Angle_offset", random.randint(0, 360))
        center_x        = p.get("E_SLIDER_Galaxy_CenterX", random.randint(0, 100))
        center_y        = p.get("E_SLIDER_Galaxy_CenterY", random.randint(0, 100))
        duration        = p.get("E_SLIDER_Galaxy_Duration", random.randint(10, 100))
        num_points      = p.get("E_SLIDER_Galaxy_Num_Points", random.randint(1, 20))
        radius_end      = p.get("E_SLIDER_Galaxy_Radius_end", random.randint(10, 100))
        radius_start    = p.get("E_SLIDER_Galaxy_Radius_start", random.randint(0, 50))
        rev_time        = p.get("E_SLIDER_Galaxy_Revolution_Time", random.randint(1, 50))
        spiral_wrap     = p.get("E_SLIDER_Galaxy_Spiral_wrap", random.randint(0, 20))
        start_angle     = p.get("E_SLIDER_Galaxy_Start_Angle", random.randint(0, 360))
        width           = p.get("E_SLIDER_Galaxy_Width", random.randint(1, 50))
        reverse         = p.get("E_CHECKBOX_Galaxy_Reverse", random.choice([0, 1]))
        blend_edges     = p.get("E_CHECKBOX_Galaxy_Blend_Edges", random.choice([0, 1]))

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (f"E_SLIDER_Galaxy_Accel={accel},"
                        f"E_SLIDER_Galaxy_Angle_offset={angle_offset},"
                        f"E_SLIDER_Galaxy_CenterX={center_x},"
                        f"E_SLIDER_Galaxy_CenterY={center_y},"
                        f"E_SLIDER_Galaxy_Duration={duration},"
                        f"E_SLIDER_Galaxy_Num_Points={num_points},"
                        f"E_SLIDER_Galaxy_Radius_end={radius_end},"
                        f"E_SLIDER_Galaxy_Radius_start={radius_start},"
                        f"E_SLIDER_Galaxy_Revolution_Time={rev_time},"
                        f"E_SLIDER_Galaxy_Spiral_wrap={spiral_wrap},"
                        f"E_SLIDER_Galaxy_Start_Angle={start_angle},"
                        f"E_SLIDER_Galaxy_Width={width},"
                        f"E_CHECKBOX_Galaxy_Reverse={reverse},"
                        f"E_CHECKBOX_Galaxy_Blend_Edges={blend_edges},"
                        f"E1=100,E2=100")
        place_effect(effect_layer, "Galaxy", start_time, end_time, palette_id, settings_str, registry)
        num_galaxy_added += 1
    return num_galaxy_added
