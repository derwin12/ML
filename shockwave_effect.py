# shockwave_effect.py

import xml.etree.ElementTree as ET
import random
from utils import section_effect_placements, alternating_beat_placements, get_or_create_layer, place_effect, section_colors
from param_sampler import sample_params, sample_beat_stride


def _place_shockwave(effect_layer, start_time, end_time, color_palettes, fixed_colors, is_group, palette_id, registry=None, structure=None):
    p = sample_params("Shockwave")
    center_x    = p.get("E_SLIDER_Shockwave_CenterX", random.randint(0, 100))
    center_y    = p.get("E_SLIDER_Shockwave_CenterY", random.randint(0, 100))
    cycles      = p.get("E_SLIDER_Shockwave_Cycles", round(random.uniform(1, 5), 1))
    start_radius= p.get("E_SLIDER_Shockwave_Start_Radius", random.randint(1, 10))
    start_width = p.get("E_SLIDER_Shockwave_Start_Width", random.randint(1, 10))
    end_width   = p.get("E_SLIDER_Shockwave_End_Width", random.randint(5, 20))
    accel       = p.get("E_SLIDER_Shockwave_Accel", random.randint(-50, 50))
    blend_edges = p.get("E_CHECKBOX_Shockwave_Blend_Edges", random.choice([0, 1]))
    scale       = p.get("E_CHECKBOX_Shockwave_Scale", random.choice([0, 1]))
    end_radius  = p.get("E_SLIDER_Shockwave_End_Radius",
                        random.randint(50, 200) if is_group else random.randint(20, 50))

    selected_indices = random.sample(range(1, 9), 2)
    _sc = section_colors(fixed_colors, structure, start_time)
    parts = [f"C_BUTTON_Palette{i+1}={_sc[i]}" for i in range(8)]
    for k in selected_indices:
        parts.append(f"C_CHECKBOX_Palette{k}=1")
    new_palette = ET.SubElement(color_palettes, "ColorPalette")
    new_palette.text = ",".join(parts)

    # Groups must use Per Model Default so the wave spans the group's coordinate space.
    render_prefix = "B_CHOICE_BufferStyle=Per Model Default," if is_group else ""
    settings_str = (f"{render_prefix}"
                    f"E_SLIDER_Shockwave_CenterX={center_x},"
                    f"E_SLIDER_Shockwave_CenterY={center_y},"
                    f"E_SLIDER_Shockwave_Cycles={cycles:.1f},"
                    f"E_SLIDER_Shockwave_Start_Radius={start_radius},"
                    f"E_SLIDER_Shockwave_End_Radius={end_radius},"
                    f"E_SLIDER_Shockwave_Start_Width={start_width},"
                    f"E_SLIDER_Shockwave_End_Width={end_width},"
                    f"E_SLIDER_Shockwave_Accel={accel},"
                    f"E_CHECKBOX_Shockwave_Blend_Edges={blend_edges},"
                    f"E_CHECKBOX_Shockwave_Scale={scale},"
                    f"E1=100,E2=100")
    place_effect(effect_layer, "Shockwave", start_time, end_time, palette_id, settings_str, registry)


def add_shockwave_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, fixed_colors, beats=None, structure=None, registry=None):
    num_shockwave_added = 0

    # --- Beat pass: groups always fire on every beat; models get a strided subset ---
    if beats and len(beats) >= 4:
        stride = sample_beat_stride("Shockwave")
        beat_placements = alternating_beat_placements(beats, stride=stride, duration_beats=1, structure=structure)

        # Groups (e.g. "Group - Stars") get every beat — this is the primary visual.
        # max_layers=4 + skip_budget so beat-aligned shockwaves are never blocked by
        # effects placed in earlier sections consuming the per-model budget.
        for elem in eligible_group_elements:
            for start_time, end_time in beat_placements:
                effect_layer = get_or_create_layer(elem, start_time, end_time, max_layers=4, skip_budget=True)
                if effect_layer is None:
                    blocked += 1
                    continue
                palette_id = len(color_palettes.findall("ColorPalette"))
                _place_shockwave(effect_layer, start_time, end_time, color_palettes, fixed_colors, True, palette_id, registry, structure)
                num_shockwave_added += 1

        # Individual models: 1-2 randomly chosen, same stride
        if eligible_elements:
            num_alt = random.randint(1, min(2, len(eligible_elements)))
            alt_elements = random.sample(eligible_elements, num_alt)
            for elem in alt_elements:
                for start_time, end_time in beat_placements:
                    effect_layer = get_or_create_layer(elem, start_time, end_time)
                    if effect_layer is None:
                        continue
                    palette_id = len(color_palettes.findall("ColorPalette"))
                    _place_shockwave(effect_layer, start_time, end_time, color_palettes, fixed_colors, False, palette_id, registry, structure)
                    num_shockwave_added += 1

    # --- Sparse pass: existing section-weighted placement on other elements ---
    placements = section_effect_placements(8, structure or [], beats or [], min_beats=5, max_beats=16)
    for start_time, end_time in placements:
        if start_time is None:
            start_time = random.randint(0, seq_duration_ms - 10000)
            end_time = start_time + random.randint(5000, 10000)
        if random.random() < 0.3 and eligible_group_elements:
            elem = random.choice(eligible_group_elements)
            is_group = True
        else:
            elem = random.choice(eligible_elements)
            is_group = elem in eligible_group_elements
        effect_layer = get_or_create_layer(elem, start_time, end_time)
        if effect_layer is None:
            continue
        palette_id = len(color_palettes.findall("ColorPalette"))
        _place_shockwave(effect_layer, start_time, end_time, color_palettes, fixed_colors, is_group, palette_id, registry)
        num_shockwave_added += 1

    return num_shockwave_added
