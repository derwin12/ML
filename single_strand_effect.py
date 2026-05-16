# single_strand_effect.py

import random
from utils import section_effect_placements, section_colors, get_or_create_layer, place_effect, get_or_create_palette
from param_sampler import sample_params

def add_single_strand_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_added = 0
    placements = section_effect_placements(10, structure or [], beats or [], min_beats=2, max_beats=8)
    for start_time, end_time in placements:
        # SingleStrand works best on individual strand models, but allow groups too
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 5000)
            end_time = start_time + random.randint(2000, 6000)
        if random.random() < 0.2 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
        else:
            elem = random.choice(eligible_elements)
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue

        p = sample_params("SingleStrand")
        num_chases = p.get("E_SLIDER_Chase_Number3dEff", random.randint(1, 5))
        chase_size = p.get("E_SLIDER_Chase_ChaseSize", random.randint(10, 50))
        direction  = p.get("E_CHOICE_Chase_Direction", random.choice(["Forward", "Backward", "Bounce Forward", "Bounce Backward"]))
        shimmer    = p.get("E_CHECKBOX_Chase_Shimmer", random.choice([0, 1]))
        freeze     = p.get("E_CHECKBOX_Chase_Freeze", 0)

        selected_indices = list(range(1, 3))
        _sc = section_colors(fixed_colors, structure, start_time)
        parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
        for k in selected_indices:
            parts.append(f"C_CHECKBOX_Palette{k}=1")
        palette_str = ",".join(parts)

        palette_id = get_or_create_palette(color_palettes, palette_str)

        settings_str = (
            f"E_SLIDER_Chase_Number3dEff={num_chases},"
            f"E_SLIDER_Chase_ChaseSize={chase_size},"
            f"E_CHOICE_Chase_Direction={direction},"
            f"E_CHECKBOX_Chase_Shimmer={shimmer},"
            f"E_CHECKBOX_Chase_Freeze={freeze},"
            f"E1=100,E2=100"
        )
        place_effect(effect_layer, "SingleStrand", start_time, end_time, palette_id, settings_str, registry)
        num_added += 1
    return num_added
