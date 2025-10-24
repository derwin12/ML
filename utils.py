# utils.py (updated with beats generation)

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import random
from mutagen.mp3 import MP3  # For MP3 duration; install if needed, or use pydub for other formats
import librosa  # For beat detection

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
    if level == 0:
        elem.text = "\n  "

def load_structure_map(structure_json_path):
    """Load the xlights_template_structures.json file and pick the Empty Sequence base if possible."""
    if not os.path.isfile(structure_json_path):
        raise FileNotFoundError(f"Structure map not found: {structure_json_path}")

    with open(structure_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Prefer the one named 'Empty Sequence.xsq', else take first entry
    for entry in data:
        if entry["file"].lower().startswith("empty sequence"):
            print(f"Using structure from template: {entry['file']}")
            return entry

    print("No 'Empty Sequence.xsq' found in structure map — using first entry.")
    return data[0] if data else None


def get_audio_duration(audio_path):
    """Get duration of audio file in seconds."""
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    try:
        audio = MP3(audio_path)
        return audio.info.length
    except Exception as e:
        raise ValueError(f"Could not read audio duration: {e}")

def get_eligible_models(layout_models, layout_groups):
    eligible_groups = []
    eligible_individuals = []
    for m in layout_models:
        model_name = m.attrib.get("name", "Unnamed")
        display_as = m.attrib.get("DisplayAs", "").lower()
        protocol = m.attrib.get("Protocol", "").upper()
        layout = m.attrib.get('Layout', '').lower()
        group_check = (layout == 'group' or display_as == 'group')
        if (display_as != "image" and
            protocol != "DMX" and
            not model_name.upper().startswith("MH-")):
            if group_check:
                eligible_groups.append(model_name)
            else:
                eligible_individuals.append(model_name)

    for g in layout_groups:
        group_name = g.attrib.get("name", "Unnamed")
        # Groups typically don't have DisplayAs/Protocol, so assume eligible unless MH-
        if not group_name.upper().startswith("MH-"):
            eligible_groups.append(group_name)

    return eligible_groups, eligible_individuals

def sort_models(layout_models, layout_groups):
    all_model_list = []
    for m in layout_models:
        model_name = m.attrib.get("name", "Unnamed")
        display_as = m.attrib.get('DisplayAs', '').lower()
        layout = m.attrib.get('Layout', '').lower()
        is_group = (layout == 'group' or display_as == 'group')
        all_model_list.append((is_group, model_name))

    for g in layout_groups:
        group_name = g.attrib.get("name", "Unnamed")
        all_model_list.append((True, group_name))  # modelGroups are always groups

    # Sort: normal groups first, then "last" groups, then individuals; alphabetical within each
    def sort_key(item):
        is_group, name = item
        if is_group:
            if "last" in name.lower():
                return (1, name)  # "last" groups second
            else:
                return (0, name)  # normal groups first
        else:
            return (2, name)  # individuals last

    all_model_list.sort(key=sort_key)
    sorted_all_model_names = [name for _, name in all_model_list]
    return sorted_all_model_names

def update_metadata(head, seq_type, seq_timing, media_file, song, artist, duration):
    if head is not None:
        seq_dur_elem = head.find("sequenceDuration")
        if seq_dur_elem is not None:
            seq_dur_elem.text = f"{duration:.3f}"

        seq_type_elem = head.find("sequenceType")
        if seq_type_elem is not None:
            seq_type_elem.text = seq_type

        seq_timing_elem = head.find("sequenceTiming")
        if seq_timing_elem is not None:
            seq_timing_elem.text = seq_timing

        media_file_elem = head.find("mediaFile")
        if media_file_elem is not None:
            media_file_elem.text = media_file

        song_elem = head.find("song")
        if song_elem is not None:
            song_elem.text = song

        artist_elem = head.find("artist")
        if artist_elem is not None:
            artist_elem.text = artist

def generate_beats_track(audio_path, display_elem, element_effects, seq_duration_ms):
    # Load audio with librosa
    y, sr = librosa.load(audio_path, sr=None)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')

    # Add to DisplayElements
    ET.SubElement(display_elem, "Element", {
        "collapsed": "0",
        "type": "timing",
        "name": "Beats",
        "visible": "1",
        "active": "1"
    })

    # Add to ElementEffects
    beats_effect_elem = ET.SubElement(element_effects, "Element", {
        "type": "timing",
        "name": "Beats"
    })

    effect_layer = ET.SubElement(beats_effect_elem, "EffectLayer")

    for i in range(len(beats)):
        label = str((i % 4) + 1)  # Cycle 1-2-3-4
        start_ms = int(beats[i] * 1000)
        if i + 1 < len(beats):
            end_ms = int(beats[i + 1] * 1000)
        else:
            end_ms = seq_duration_ms
        ET.SubElement(effect_layer, "Effect", {
            "label": label,
            "startTime": f"{start_ms}",
            "endTime": f"{end_ms}"
        })
    return beats