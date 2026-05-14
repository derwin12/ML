# add_timing_tracks.py
#
# Adds timing tracks (Beats, Downbeats, Energy Peaks, Structure) to existing
# .xsq files and writes the results to a separate output folder.
#
# SOURCE SEQUENCES ARE NEVER MODIFIED.
# Each file is parsed into memory, timing tracks are appended to the in-memory
# tree, and the result is written to OUTPUT_FOLDER only.
#
# Usage:
#   python add_timing_tracks.py                     # add all 4 tracks
#   python add_timing_tracks.py --no-structure      # skip Lemonade call
#   python add_timing_tracks.py --structure-only    # only add Structure
#   python add_timing_tracks.py --overwrite         # re-process already-output files
#
# Tracks added (skipped if already present in the file):
#   Beats        — librosa beat detection, labels 1-2-3-4
#   Downbeats    — every 4th beat (bar 1), derived from the same beat detection pass
#   Energy Peaks — RMS energy peaks, marks loudest moments
#   Structure    — LLM-generated section labels via Lemonade (requires Lemonade running)

import os
import sys
import argparse
import xml.etree.ElementTree as ET

SOURCE_FOLDER = r"E:\2023\ShowFolder3D"
OUTPUT_FOLDER = r"E:\2023\ShowFolder3D\LabeledShowFolder"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_audio(media_path: str, xsq_path: str) -> str | None:
    """Resolve the audio file path. Tries the embedded path first, then common
    fallback locations relative to the source folder."""
    if media_path and os.path.isfile(media_path):
        return media_path

    # Try Audio subfolder of source folder
    if media_path:
        basename = os.path.basename(media_path)
        candidates = [
            os.path.join(SOURCE_FOLDER, "Audio", basename),
            os.path.join(os.path.dirname(xsq_path), basename),
            os.path.join(os.path.dirname(xsq_path), "Audio", basename),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
    return None


def get_existing_track_names(root) -> set:
    """Return set of timing track names already present anywhere in the XSQ."""
    names = set()
    for elem in root.findall(".//Element[@type='timing']"):
        name = elem.get("name", "").strip()
        if name:
            names.add(name)
    return names


def get_media_info(root) -> tuple[str, str, str]:
    """Return (media_file_path, song, artist) from the XSQ <head> section."""
    head = root.find(".//head")
    if head is None:
        return "", "", ""
    return (
        head.findtext("mediaFile", "").strip(),
        head.findtext("song", "").strip(),
        head.findtext("artist", "").strip(),
    )


def get_sections(root):
    """Return the DisplayElements and ElementEffects XML elements."""
    display_elem   = root.find(".//DisplayElements")
    element_effects = root.find(".//ElementEffects")
    return display_elem, element_effects


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------

def process_file(xsq_path: str, output_path: str,
                 add_beats: bool, add_structure: bool) -> str:
    """
    Parse xsq_path into memory, add missing timing tracks, write to output_path.
    Never touches xsq_path.  Returns a human-readable status string.
    """
    # Import heavy deps here so startup stays fast even if librosa isn't installed
    from utils import (
        _load_audio, _add_timing_track,
        generate_beats_track, generate_energy_peaks_track,
        generate_structure_track, get_audio_duration, indent,
    )
    import librosa

    # --- Parse ---
    tree = ET.parse(xsq_path)
    root = tree.getroot()

    raw_media, song, artist = get_media_info(root)

    if not raw_media:
        return "skip — animation (no mediaFile)"

    audio_path = find_audio(raw_media, xsq_path)
    if not audio_path:
        return f"skip — audio not found ({raw_media})"

    display_elem, element_effects = get_sections(root)
    if display_elem is None or element_effects is None:
        return "skip — missing DisplayElements / ElementEffects"

    existing = get_existing_track_names(root)

    want_beats       = add_beats and "Beats"        not in existing
    want_downbeats   = add_beats and "Downbeats"    not in existing
    want_peaks       = add_beats and "Energy Peaks" not in existing
    want_structure   = add_structure and "Structure" not in existing

    if not any([want_beats, want_downbeats, want_peaks, want_structure]):
        return "skip — all requested tracks already present"

    duration_ms = int(get_audio_duration(audio_path) * 1000)

    # --- Load audio once ---
    y, sr = _load_audio(audio_path)

    added = []

    # Beats + Downbeats share one librosa beat_track call
    if want_beats or want_downbeats:
        _, beat_times = librosa.beat.beat_track(y=y, sr=sr, units="time")
        beat_ms = [int(b * 1000) for b in beat_times]

        if want_beats:
            labels = [str((i % 4) + 1) for i in range(len(beat_ms))]
            _add_timing_track("Beats", beat_ms, labels, display_elem, element_effects, duration_ms)
            print(f"    Beats: {len(beat_ms)} beats")
            added.append("Beats")

        if want_downbeats:
            db_ms     = beat_ms[::4]
            db_labels = [str(i + 1) for i in range(len(db_ms))]
            _add_timing_track("Downbeats", db_ms, db_labels, display_elem, element_effects, duration_ms)
            print(f"    Downbeats: {len(db_ms)} bars")
            added.append("Downbeats")

    if want_peaks:
        generate_energy_peaks_track(y, sr, display_elem, element_effects, duration_ms)
        added.append("Energy Peaks")

    if want_structure:
        generate_structure_track(audio_path, song, artist, display_elem, element_effects, duration_ms,
                                 y=y, sr=sr)
        added.append("Structure")

    # --- Write output (source never touched) ---
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    indent(root)
    tree.write(output_path, encoding="unicode", xml_declaration=True)

    return f"added: {', '.join(added)}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(add_beats: bool = True, add_structure: bool = True, overwrite: bool = False) -> dict:
    """
    Batch-add timing tracks to all .xsq files in SOURCE_FOLDER.
    Writes results to OUTPUT_FOLDER only — source files are never modified.
    Returns {"added": int, "skipped": int, "errors": int}.
    """
    if not add_beats and add_structure:
        print("Mode: Structure track only")
    elif not add_structure:
        print("Mode: Beats + Downbeats + Energy Peaks (no Structure)")
    else:
        print("Mode: all tracks (Beats, Downbeats, Energy Peaks, Structure)")

    xsq_files = sorted(
        f for f in os.listdir(SOURCE_FOLDER)
        if f.lower().endswith(".xsq") and os.path.isfile(os.path.join(SOURCE_FOLDER, f))
    )
    print(f"\nFound {len(xsq_files)} .xsq files in {SOURCE_FOLDER}")
    print(f"Output → {OUTPUT_FOLDER}\n")

    results = {"added": 0, "skipped": 0, "errors": 0}

    for i, fname in enumerate(xsq_files, 1):
        src  = os.path.join(SOURCE_FOLDER, fname)
        dest = os.path.join(OUTPUT_FOLDER, fname)

        if not overwrite and os.path.isfile(dest):
            print(f"[{i:3}/{len(xsq_files)}] {fname}  →  skip (output exists)")
            results["skipped"] += 1
            continue

        print(f"[{i:3}/{len(xsq_files)}] {fname}")
        try:
            status = process_file(src, dest, add_beats=add_beats, add_structure=add_structure)
            if status.startswith("skip"):
                print(f"           {status}")
                results["skipped"] += 1
            else:
                print(f"           {status}")
                results["added"] += 1
        except Exception as e:
            print(f"           ERROR: {e}")
            results["errors"] += 1

    print(f"\n{'='*60}")
    print(f"Done.  {results['added']} updated  |  {results['skipped']} skipped  |  {results['errors']} errors")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Add timing tracks to xLights .xsq files without modifying originals."
    )
    parser.add_argument("--no-structure",   action="store_true",
                        help="Skip Structure track")
    parser.add_argument("--structure-only", action="store_true",
                        help="Only add Structure track (skip Beats/Downbeats/Energy Peaks)")
    parser.add_argument("--overwrite",      action="store_true",
                        help="Re-process files that already exist in the output folder")
    args = parser.parse_args()

    run(
        add_beats     = not args.structure_only,
        add_structure = not args.no_structure,
        overwrite     = args.overwrite,
    )


if __name__ == "__main__":
    main()
