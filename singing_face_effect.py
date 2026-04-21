# singing_face_effect.py

from utils import get_or_create_layer, place_effect, EffectDBRegistry

_FACES_PALETTE = (
    "C_BUTTON_Palette1=#FFFFFF,C_BUTTON_Palette2=#FF0000,C_BUTTON_Palette3=#00FF00,"
    "C_BUTTON_Palette4=#0000FF,C_BUTTON_Palette5=#FFFF00,C_BUTTON_Palette6=#000000,"
    "C_BUTTON_Palette7=#00FFFF,C_BUTTON_Palette8=#FF00FF,"
    "C_CHECKBOXBRIGHTNESSLEVEL=0,C_CHECKBOX_Chroma=0,C_CHECKBOX_MusicSparkles=0,"
    "C_CHECKBOX_Palette1=1,C_CHECKBOX_Palette2=1,C_CHECKBOX_Palette3=0,"
    "C_CHECKBOX_Palette4=0,C_CHECKBOX_Palette5=0,C_CHECKBOX_Palette6=0,"
    "C_CHECKBOX_Palette7=0,C_CHECKBOX_Palette8=0,C_SLIDER_SparkleFrequency=0"
)


def _faces_settings(face_def_name):
    return (
        f"E_CHECKBOX_Faces_Outline=1,E_CHECKBOX_Faces_SuppressShimmer=0,"
        f"E_CHECKBOX_Faces_SuppressWhenNotSinging=0,E_CHECKBOX_Faces_TransparentBlack=0,"
        f"E_CHOICE_Faces_EyeBlinkDuration=Normal,E_CHOICE_Faces_EyeBlinkFrequency=Normal,"
        f"E_CHOICE_Faces_Eyes=Auto,E_CHOICE_Faces_FaceDefinition={face_def_name},"
        f"E_CHOICE_Faces_Phoneme=AI,E_CHOICE_Faces_UseState=,"
        f"E_TEXTCTRL_Faces_TransparentBlack=0,"
        f"T_CHECKBOX_Canvas=0,T_CHECKBOX_LayerMorph=0,"
        f"T_CHOICE_LayerMethod=Normal,T_SLIDER_EffectLayerMix=0"
    )


def add_singing_face_effects(singing_prop_elements, face_defs, color_palettes,
                              seq_duration_ms, registry=None):
    """
    Place a Faces effect spanning the full sequence on each singing prop element.

    singing_prop_elements: list of ElementEffects <Element> nodes for singing props
    face_defs: dict of model_name -> face_definition_name
    """
    count = 0
    for elem in singing_prop_elements:
        model_name = elem.attrib.get("name", "")
        face_def = face_defs.get(model_name, "Green")

        effect_layer = get_or_create_layer(elem, 0, seq_duration_ms)
        if effect_layer is None:
            continue

        palette_id = len(color_palettes.findall("ColorPalette"))

        import xml.etree.ElementTree as ET
        cp = ET.SubElement(color_palettes, "ColorPalette")
        cp.text = _FACES_PALETTE

        settings_str = _faces_settings(face_def) + "\t" + _FACES_PALETTE
        place_effect(effect_layer, "Faces", 0, seq_duration_ms, palette_id, settings_str, registry)
        count += 1
        print(f"  Singing prop '{model_name}': Faces effect placed (def='{face_def}')")

    return count
