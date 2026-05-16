# generate_lyrics_track.py
#
# Adds a 3-layer Lyrics timing track to an .xsq file.
#
# Layer 0 — Phrases  : lrclib.net synced timestamps (accurate)
#                      Whisper segments as fallback if lrclib unavailable
# Layer 1 — Words    : text split from phrases, distributed proportionally
#                      within each phrase window
# Layer 2 — Phonemes : CMU dict → Preston Blair, distributed within each word
#
# Whisper is NO LONGER used for word-level timing — lrclib phrase timestamps
# are the source of truth and words/phonemes fall strictly within them.
#
# Usage:
#   python generate_lyrics_track.py song.xsq
#   python generate_lyrics_track.py song.xsq --audio path\to\audio.mp3
#   python generate_lyrics_track.py song.xsq --overwrite

import os
import re
import sys
import argparse
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# CMU Arpabet → Preston Blair phoneme map (from xLights phoneme_mapping)
# ---------------------------------------------------------------------------
_CMU_TO_BLAIR = {
    "AA": "AI", "AE": "AI", "AH": "AI",
    "AO": "O",  "AW": "O",
    "AY": "AI",
    "EH": "E",  "ER": "E",  "EY": "E",
    "IH": "E",  "IY": "E",
    "OW": "O",  "OY": "O",
    "UH": "U",  "UW": "U",
    "B": "MBP", "P": "MBP", "M": "MBP",
    "F": "FV",  "V": "FV",
    "L": "L",   "R": "L",
    "W": "WQ",  "Y": "WQ",
    "CH": "etc", "D": "etc",  "DH": "etc", "G": "etc",
    "HH": "etc", "JH": "etc", "K": "etc",  "N": "etc",
    "NG": "etc", "S": "etc",  "SH": "etc", "T": "etc",
    "TH": "etc", "Z": "etc",  "ZH": "etc",
}

_SHORT_PHONEME_MS = 50
_MIN_PHONEME_MS   = 25   # one frame at 25 ms sequence timing


def _cmudict():
    if not hasattr(_cmudict, "_cache"):
        import nltk
        try:
            _cmudict._cache = nltk.corpus.cmudict.dict()
        except LookupError:
            nltk.download("cmudict", quiet=True)
            _cmudict._cache = nltk.corpus.cmudict.dict()
    return _cmudict._cache


# Punctuation xLights strips before dictionary lookup (apostrophe is NOT in this set)
_XLIGHTS_STRIP = set(r'/#~@$%^*,!&-_+=[]{}":;.<>?`')

# Delimiters xLights uses to split words out of a phrase (apostrophe NOT a delimiter)
_XLIGHTS_DELIMS = set(' \t:;,.-_!?{}[]()<>+=|')


def _word_to_blair(word: str) -> list[str]:
    """
    Map a word to Preston Blair phonemes using the same logic as xLights
    PhonemeDictionary::BreakdownWord():
      - Strip xLights punctuation set (apostrophes preserved)
      - Case-fold to lowercase for NLTK cmudict lookup
      - Return [] if not found (xLights silently skips unfound words)
      - Deduplicate consecutive identical phonemes
    """
    stripped = "".join(c for c in word if c not in _XLIGHTS_STRIP)
    key = stripped.lower()
    if not key:
        return []
    entries = _cmudict().get(key)
    if not entries:
        return []
    arp = [re.sub(r"\d", "", p) for p in entries[0]]
    blair = [_CMU_TO_BLAIR.get(p, "etc") for p in arp]
    deduped = [blair[0]] if blair else []
    for ph in blair[1:]:
        if ph != deduped[-1]:
            deduped.append(ph)
    return deduped


def _distribute_phonemes(phonemes: list[str], word_start_ms: int, word_end_ms: int,
                         min_ms: int = _MIN_PHONEME_MS,
                         ) -> list[tuple[int, int, str]]:
    """Distribute phonemes proportionally within a word's time window.

    Each phoneme is guaranteed to be at least min_ms wide (one xLights frame).
    If the word window is too short to fit all phonemes at min_ms, phonemes
    overflow past word_end_ms — xLights handles overlapping timing entries fine.
    """
    n = len(phonemes)
    if n == 0:
        return []
    duration = word_end_ms - word_start_ms
    if duration <= 0:
        t = word_start_ms
        result = []
        for ph in phonemes:
            result.append((t, t + min_ms, ph))
            t += min_ms
        return result

    short_types = {"MBP", "etc"}
    short_count = sum(1 for ph in phonemes if ph in short_types)
    long_count  = n - short_count

    short_ms = max(min_ms, min(_SHORT_PHONEME_MS, duration // max(n, 1)))
    remaining = duration - short_ms * short_count
    long_ms   = max(min_ms, remaining // max(long_count, 1))

    result = []
    t = word_start_ms
    for i, ph in enumerate(phonemes):
        dur = short_ms if ph in short_types else long_ms
        end = (t + dur) if i < n - 1 else max(t + min_ms, word_end_ms)
        result.append((t, end, ph))
        t = end
    return result


def _split_phrase_to_words(phrase_text: str, phrase_start_ms: int, phrase_end_ms: int
                            ) -> list[tuple[int, int, str]]:
    """
    Split a phrase into words using the same delimiter set as xLights
    LyricBreakdown::BreakdownPhrase(). Apostrophes are NOT delimiters so
    contractions like "don't" stay as one token.
    """
    tokens = []
    current = []
    for ch in phrase_text:
        if ch in _XLIGHTS_DELIMS:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    tokens = [t for t in tokens if t]
    if not tokens:
        return []
    duration = phrase_end_ms - phrase_start_ms
    if duration <= 0:
        return [(phrase_start_ms, phrase_end_ms, t) for t in tokens]

    # Weight each word by its character length for more natural timing
    lengths = [max(1, len(re.sub(r"[^a-zA-Z]", "", t))) for t in tokens]
    total = sum(lengths)

    result = []
    t = phrase_start_ms
    for i, (token, length) in enumerate(zip(tokens, lengths)):
        word_dur = int(duration * length / total)
        end = t + word_dur if i < len(tokens) - 1 else phrase_end_ms
        result.append((t, end, token))
        t = end
    return result


def _snap_words_to_onsets(
    phrase_words: list[tuple[int, int, str]],
    phrase_end_ms: int,
    vocal_onsets_ms: list[int],
) -> list[tuple[int, int, str]]:
    """
    Re-time a phrase's word list by snapping word starts to vocal onsets.
    Onsets outside the phrase window are ignored. If fewer onsets than words,
    the remaining words are redistributed proportionally from the last onset.
    """
    if not phrase_words or not vocal_onsets_ms:
        return phrase_words
    phrase_start_ms = phrase_words[0][0]
    phrase_onsets = sorted(o for o in vocal_onsets_ms
                           if phrase_start_ms <= o < phrase_end_ms)
    if not phrase_onsets:
        return phrase_words

    tokens = [w[2] for w in phrase_words]
    n = len(tokens)
    starts = list(phrase_onsets[:n])

    if len(starts) < n:
        # Distribute remaining words proportionally from the last onset to phrase end
        last = starts[-1]
        remaining = tokens[len(starts):]
        lengths = [max(1, len(re.sub(r"[^a-zA-Z]", "", t))) for t in remaining]
        total = sum(lengths) or 1
        dur = phrase_end_ms - last
        t = last
        for length in lengths:
            starts.append(t)
            t += int(dur * length / total)

    result = []
    for i, (token, start) in enumerate(zip(tokens, starts)):
        end = starts[i + 1] if i + 1 < n else phrase_end_ms
        result.append((start, max(start + 1, end), token))
    return result


def build_layers_from_phrases(phrases: list[tuple[int, int, str]],
                               vocal_onsets_ms: list[int] | None = None,
                               ) -> tuple[list, list]:
    """
    Given accurate phrase timings, derive word and phoneme layers.
    When vocal_onsets_ms is provided, word starts are snapped to onsets.
    Returns (words, phonemes) — each a list of (start_ms, end_ms, label).
    """
    words:    list[tuple[int, int, str]] = []
    phonemes: list[tuple[int, int, str]] = []

    for start_ms, end_ms, text in phrases:
        phrase_words = _split_phrase_to_words(text, start_ms, end_ms)
        if vocal_onsets_ms:
            phrase_words = _snap_words_to_onsets(phrase_words, end_ms, vocal_onsets_ms)
        words.extend(phrase_words)
        for w_start, w_end, w_text in phrase_words:
            blair = _word_to_blair(w_text)
            if blair:  # xLights skips words not found in dictionary
                phonemes.extend(_distribute_phonemes(blair, w_start, w_end))

    return words, phonemes


def lrclib_phrases(song: str, artist: str, duration_s: float,
                   seq_duration_ms: int) -> list[tuple[int, int, str]]:
    """Fetch synced phrase timestamps from lrclib.net. Returns [] if unavailable."""
    from utils import _fetch_lyrics, _parse_lrc

    track = _fetch_lyrics(song, artist, duration_s)
    if not track:
        return []
    synced = track.get("syncedLyrics") or ""
    if not synced:
        return []
    lines = _parse_lrc(synced)
    if not lines:
        return []

    result = []
    for i, (t_ms, text) in enumerate(lines):
        end_ms = lines[i + 1][0] if i + 1 < len(lines) else seq_duration_ms
        if text.strip():
            result.append((t_ms, end_ms, text.strip()))
    return result


def forced_align_words(vocal_path: str,
                        phrases: list[tuple[int, int, str]],
                        seq_duration_ms: int,
                        device: str = "cpu") -> list[tuple[int, int, str]]:
    """
    Use WhisperX forced alignment to get accurate word-level timestamps.
    Aligns the known lrclib phrase text against the clean vocal stem.

    Returns list of (start_ms, end_ms, word) or [] if WhisperX unavailable.
    """
    try:
        import whisperx
    except ImportError:
        print("Lyrics: whisperx not installed — using proportional word distribution.")
        return []

    import torch
    if device == "cpu" and torch.cuda.is_available():
        device = "cuda"

    # Build flat transcript from phrases for alignment
    full_text = " ".join(text for _, _, text in phrases)
    if not full_text.strip():
        return []

    print(f"Lyrics: forced-aligning {len(phrases)} phrases against vocal stem…")

    # Load audio at 16kHz (WhisperX requirement)
    audio = whisperx.load_audio(vocal_path)

    # Detect language from a short sample via whisper
    model = whisperx.load_model("base", device, compute_type="int8")
    result = model.transcribe(audio, batch_size=8)
    language = result.get("language", "en")

    # Build segment list from our lrclib phrases so the aligner uses correct text
    segments = [
        {"start": start_ms / 1000.0, "end": end_ms / 1000.0, "text": text}
        for start_ms, end_ms, text in phrases
    ]
    result["segments"] = segments

    # Load alignment model and align
    align_model, metadata = whisperx.load_align_model(language_code=language, device=device)
    aligned = whisperx.align(result["segments"], align_model, metadata, audio, device,
                              return_char_alignments=False)

    words = []
    for seg in aligned.get("segments", []):
        for w in seg.get("words", []):
            word_text  = w.get("word", "").strip()
            w_start_ms = int(w.get("start", 0) * 1000)
            w_end_ms   = min(int(w.get("end",   0) * 1000), seq_duration_ms)
            if word_text and w_start_ms < w_end_ms:
                words.append((w_start_ms, w_end_ms, word_text))

    print(f"Lyrics: forced alignment produced {len(words)} word timestamps.")
    return words


def whisper_phrases(audio_path: str, seq_duration_ms: int) -> list[tuple[int, int, str]]:
    """
    Fallback: use Whisper for phrase-level segments only (no word timestamps).
    Returns [] if Whisper is not installed.
    """
    try:
        import whisper
    except ImportError:
        print("Lyrics: Whisper not installed — no phrase fallback available.")
        return []

    print("Lyrics: lrclib unavailable — falling back to Whisper for phrase timing.")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=False, verbose=False)
    phrases = []
    for seg in result.get("segments", []):
        start_ms = int(seg["start"] * 1000)
        end_ms   = min(int(seg["end"] * 1000), seq_duration_ms)
        text     = seg.get("text", "").strip()
        if text and start_ms < end_ms:
            phrases.append((start_ms, end_ms, text))
    return phrases


def _add_lyrics_timing_track(name: str,
                              phrases:  list[tuple[int, int, str]],
                              words:    list[tuple[int, int, str]],
                              phonemes: list[tuple[int, int, str]],
                              display_elem, element_effects):
    """Insert a 3-layer lyrics timing track into the XSQ XML tree."""
    ET.SubElement(display_elem, "Element", {
        "collapsed": "0", "type": "timing", "name": name,
        "visible": "1", "active": "0",
    })
    elem = ET.SubElement(element_effects, "Element", {"type": "timing", "name": name})
    for layer_items in (phrases, words, phonemes):
        layer = ET.SubElement(elem, "EffectLayer")
        for start_ms, end_ms, text in layer_items:
            ET.SubElement(layer, "Effect", {
                "label":     text,
                "startTime": str(start_ms),
                "endTime":   str(end_ms),
            })


def generate_whisper_lyrics_track(audio_path: str, song: str, artist: str,
                                   display_elem, element_effects,
                                   seq_duration_ms: int,
                                   model_name: str = "base",
                                   track_name: str = "Lyrics",
                                   whisper_only: bool = False) -> list:
    """
    In-memory entry point for main.py's sequence generation pipeline.

    Word-timing pipeline (first success wins):
      1. Enhanced LRC from lrclib (<mm:ss> inline word tags) — zero extra cost
      2. WhisperX forced alignment on vocal stem
      3. Vocal onset snapping (lightweight, no model required)
      4. Proportional distribution by character length (pure fallback)

    Returns list of (time_ms, text) tuples for filter_beats_vocals_only().
    """
    from utils import _fetch_lyrics, _parse_lrc, _parse_enhanced_lrc

    duration_s = seq_duration_ms / 1000.0

    # Layer 0: phrase timestamps
    phrases = []
    phrase_source = "none"
    lrc_track = {}
    if not whisper_only and song and artist:
        lrc_track = _fetch_lyrics(song, artist, duration_s)
        if lrc_track and lrc_track.get("syncedLyrics"):
            lines = _parse_lrc(lrc_track["syncedLyrics"])
            for i, (t_ms, text) in enumerate(lines):
                end_ms = lines[i + 1][0] if i + 1 < len(lines) else seq_duration_ms
                if text.strip():
                    phrases.append((t_ms, end_ms, text.strip()))
            if phrases:
                phrase_source = "lrclib"
                print(f"Lyrics: {len(phrases)} phrases from lrclib.net")

    if not phrases:
        phrases = whisper_phrases(audio_path, seq_duration_ms)
        phrase_source = "whisper" if phrases else "none"

    if not phrases:
        print("Lyrics: no phrase source available — skipping lyrics track.")
        return []

    # Layer 1: word timestamps — work through tiers until one succeeds
    word_source = "proportional"
    words: list[tuple[int, int, str]] = []
    phonemes: list[tuple[int, int, str]] = []

    # Tier 1: enhanced LRC word timestamps (already fetched above, free)
    if lrc_track.get("syncedLyrics"):
        enhanced_words = _parse_enhanced_lrc(lrc_track["syncedLyrics"])
        if enhanced_words:
            words = enhanced_words
            word_source = "enhanced-lrc"
            print(f"Lyrics: {len(words)} word timestamps from enhanced LRC.")

    # Tier 2: WhisperX forced alignment on vocal stem
    vocal_path = ""
    if not words:
        try:
            from stem_separator import separate_stems
            stems = separate_stems(audio_path)
            vocal_path = stems.get("vocals", "")
            if vocal_path and os.path.isfile(vocal_path):
                aligned_words = forced_align_words(vocal_path, phrases, seq_duration_ms)
                if aligned_words:
                    words = aligned_words
                    word_source = "forced-align"
        except Exception as e:
            print(f"Lyrics: stem separation failed ({e}).")

    # Tier 3: vocal onset snapping
    vocal_onsets_ms = None
    if not words and vocal_path and os.path.isfile(vocal_path):
        try:
            from stem_separator import get_stem_onsets
            vocal_onsets_ms = get_stem_onsets(vocal_path, "vocals")
            if vocal_onsets_ms:
                word_source = "onset-snap"
                print(f"Lyrics: snapping words to {len(vocal_onsets_ms)} vocal onsets.")
        except Exception as e:
            print(f"Lyrics: onset detection failed ({e}).")

    # Build phonemes from whichever word source won; tier 4 is proportional fallback
    if words:
        for w_start, w_end, w_text in words:
            blair = _word_to_blair(w_text)
            phonemes.extend(_distribute_phonemes(blair, w_start, w_end))
    else:
        # Tier 4: proportional (with optional onset snapping baked in)
        words, phonemes = build_layers_from_phrases(phrases, vocal_onsets_ms)

    _add_lyrics_timing_track(track_name, phrases, words, phonemes,
                             display_elem, element_effects)

    print(f"Lyrics track: {len(phrases)} phrases ({phrase_source}), "
          f"{len(words)} words ({word_source}), {len(phonemes)} phonemes.")

    return [(start_ms, text) for start_ms, _, text in phrases]


def generate_lyrics_track(xsq_path: str,
                           audio_path: str | None = None,
                           track_name: str = "Lyrics",
                           output_path: str | None = None,
                           overwrite: bool = False,
                           whisper_only: bool = False) -> str:
    """Standalone CLI entry point — parses XSQ, injects lyrics track, writes file."""
    from add_timing_tracks import find_audio, get_media_info, get_sections
    from utils import indent

    tree = ET.parse(xsq_path)
    root = tree.getroot()

    raw_media, song, artist = get_media_info(root)
    resolved_audio = audio_path or find_audio(raw_media, xsq_path)
    if not resolved_audio or not os.path.isfile(resolved_audio):
        return f"ERROR — audio not found (tried: {audio_path or raw_media})"

    display_elem, element_effects = get_sections(root)
    if display_elem is None or element_effects is None:
        return "ERROR — missing DisplayElements / ElementEffects"

    existing = {e.get("name", "") for e in root.findall(".//Element[@type='timing']")}
    if track_name in existing and not overwrite:
        return f"skip — '{track_name}' track already present (use --overwrite)"
    if track_name in existing:
        for container in (display_elem, element_effects):
            for old in container.findall(f"Element[@name='{track_name}']"):
                container.remove(old)

    head = root.find(".//head")
    dur_attr = head.findtext("sequenceDuration", "") if head is not None else ""
    if dur_attr:
        seq_duration_ms = int(float(dur_attr) * 1000)
    else:
        import librosa
        seq_duration_ms = int(librosa.get_duration(path=resolved_audio) * 1000)

    result = generate_whisper_lyrics_track(
        resolved_audio, song, artist,
        display_elem, element_effects, seq_duration_ms,
        track_name=track_name, whisper_only=whisper_only,
    )

    if not result:
        return "ERROR — no lyrics found"

    out = output_path or xsq_path
    indent(root)
    tree.write(out, encoding="unicode", xml_declaration=True)
    return f"done — {len(result)} phrases → {out}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Inject a 3-layer lyrics timing track into an xLights .xsq file."
    )
    parser.add_argument("xsq", help="Path to the .xsq sequence file")
    parser.add_argument("--audio",       default=None,
                        help="Audio file path (uses mediaFile from XSQ if omitted)")
    parser.add_argument("--name",        default="Lyrics",
                        help="Timing track name in xLights (default: Lyrics)")
    parser.add_argument("--output",      default=None,
                        help="Output .xsq path (overwrites input if omitted)")
    parser.add_argument("--overwrite",   action="store_true",
                        help="Replace existing Lyrics track if present")
    parser.add_argument("--whisper-only", action="store_true",
                        help="Skip lrclib; use Whisper segments for phrases")
    args = parser.parse_args()

    if not os.path.isfile(args.xsq):
        print(f"ERROR — file not found: {args.xsq}", file=sys.stderr)
        sys.exit(1)

    status = generate_lyrics_track(
        xsq_path     = args.xsq,
        audio_path   = args.audio,
        track_name   = args.name,
        output_path  = args.output,
        overwrite    = args.overwrite,
        whisper_only = args.whisper_only,
    )
    print(status)
    sys.exit(0 if status.startswith("done") else 1)


if __name__ == "__main__":
    main()
