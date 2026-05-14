# xLights AI Sequence Generator — Project Reference

## What this is

A Python tool that generates `.xsq` xLights sequence files automatically. It reads your show layout (`xlights_rgbeffects.xml`), an audio file, and a template sequence, then places beat-aligned lighting effects across all your models using an AI-generated color palette and song structure.

---

## File Map

| File | Role |
|---|---|
| `main.py` | Entry point. Orchestrates the full generation pipeline. |
| `utils.py` | Shared helpers: Lemonade client, beat/structure helpers, XML utilities, audio analysis, model categorization. |
| `app.py` | Flask web UI — async generation with SSE streaming, Lemonade health check, category preview, history. |
| `templates/index.html` | Single-page UI: live log panel, Lemonade badge, history sidebar, localStorage autocomplete. |
| `name_category_rules.json` | Editable substring rules for name-based category resolution (secondary pass). |
| `name_exact_overrides.json` | Exact name → category overrides; highest user-controlled precedence. |
| `scan_for_arches.py` | Analyzes existing `.xsq` files and extracts effect params for arch models — training data harvesting. |
| `analyze_xsq_templates.py` | Analyzes template structure for use in generation. |
| `xlights_classifier.py` | Classifies XML elements. |
| `param_sampler.py` | Samples effect parameters from training data observations. |
| `grok3api_example.py` | Scratch file: testing Grok-3 API for structure generation. |

### Effect modules (33 total)

Each module follows the same signature:
`add_X_effects(eligible_elements, eligible_group_elements, seq_duration_ms, color_palettes, colors, beats, structure, registry)`

| Module | Effect Name | Notes |
|---|---|---|
| `on_effect.py` | On | 1–3 beats each |
| `bars_effect.py` | Bars | 5–16 beats |
| `color_wash_effect.py` | Color Wash | 5–16 beats |
| `shockwave_effect.py` | Shockwave | 5–16 beats |
| `spirals_effect.py` | Spirals | 5–16 beats |
| `pinwheel_effect.py` | Pinwheel | 5–16 beats |
| `single_strand_effect.py` | SingleStrand | — |
| `morph_effect.py` | Morph | — |
| `fill_effect.py` | Fill | — |
| `ripple_effect.py` | Ripple | — |
| `wave_effect.py` | Wave | — |
| `twinkle_effect.py` | Twinkle | — |
| `meteors_effect.py` | Meteors | — |
| `fire_effect.py` | Fire | — |
| `shimmer_effect.py` | Shimmer | — |
| `strobe_effect.py` | Strobe | — |
| `fan_effect.py` | Fan | 19,127 training obs |
| `galaxy_effect.py` | Galaxy | 19,023 training obs |
| `shape_effect.py` | Shape | 20,390 training obs |
| `warp_effect.py` | Warp | 18,103 training obs |
| `marquee_effect.py` | Marquee | 12,439 training obs |
| `curtain_effect.py` | Curtain | 11,421 training obs |
| `butterfly_effect.py` | Butterfly | 7,296 training obs |
| `snowflakes_effect.py` | Snowflakes | 6,981 training obs |
| `garlands_effect.py` | Garlands | 8,280 training obs |
| `spirograph_effect.py` | Spirograph | 3,955 training obs |
| `lightning_effect.py` | Lightning | 3,841 training obs |
| `circles_effect.py` | Circles | 3,394 training obs |
| `kaleidoscope_effect.py` | Kaleidoscope | 3,265 training obs |
| `liquid_effect.py` | Liquid | 3,166 training obs |
| `plasma_effect.py` | Plasma | 2,337 training obs |
| `fireworks_effect.py` | Fireworks | 1,315 training obs |
| `tendril_effect.py` | Tendril | 1,278 training obs |

### Key data files

| Path | Description |
|---|---|
| `training data/folder 1/Empty Sequence.xsq` | Template used as the base for every generated sequence. |
| `training data/folder 1/xlights_rgbeffects.xml` | Your show layout — all model names, types, groups. |
| `training data/templates/xlights_template_structures.json` | Structural schema of the template XSQ. |
| `arch_effects_summary.json` | Output of `scan_for_arches.py` — real effect params from existing shows. |
| `name_category_rules.json` | Editable substring rules for name-based category resolution (see below). |

---

## Generation Pipeline (`create_xsq_from_template`)

```
Audio file
  → librosa beat detection          → beats (ms list)
  → Lemonade: song structure        → structure [{section, start, end}]
  → Lemonade: color palette         → 8 hex colors
  → xlights_rgbeffects.xml          → model/group names + categorization
  → Empty Sequence.xsq (template)
        ↓
  Rebuild DisplayElements + ElementEffects
  Add Beats timing track
  Add Structure timing track
  add_first_beat_effects()     — POC: 1 effect per model spanning the intro section
  add_on_effects()             — On
  add_bars_effects()           — Bars
  add_color_wash_effects()     — Color Wash
  add_shockwave_effects()      — Shockwave
  add_spirals_effects()        — Spirals
  add_pinwheel_effects()       — Pinwheel
  add_single_strand_effects()  — SingleStrand
  add_morph_effects()          — Morph
  add_fill_effects()           — Fill
  add_ripple_effects()         — Ripple
  add_wave_effects()           — Wave
  add_twinkle_effects()        — Twinkle
  add_meteors_effects()        — Meteors
  add_fire_effects()           — Fire
  add_shimmer_effects()        — Shimmer
  add_strobe_effects()         — Strobe
  add_fan_effects()            — Fan
  add_galaxy_effects()         — Galaxy
  add_shape_effects()          — Shape
  add_warp_effects()           — Warp
  add_marquee_effects()        — Marquee
  add_curtain_effects()        — Curtain
  add_butterfly_effects()      — Butterfly
  add_snowflakes_effects()     — Snowflakes
  add_garlands_effects()       — Garlands
  add_spirograph_effects()     — Spirograph
  add_lightning_effects()      — Lightning
  add_circles_effects()        — Circles
  add_kaleidoscope_effects()   — Kaleidoscope
  add_liquid_effects()         — Liquid
  add_plasma_effects()         — Plasma
  add_fireworks_effects()      — Fireworks
  add_tendril_effects()        — Tendril
  DEV: Text label effect on last 4 beats (shows category name per model)
  Set visibility (hide models with no effects)
  Write EffectDB entries
  Write pretty-printed XML → output.xsq
```

---

## Beat & Structure System

### Beat alignment (`utils.py`)

Audio is loaded once with `_load_audio(audio_path) -> (y, sr)` and passed to all generators to avoid re-reading the file.

**Timing track generators** (all write to both `DisplayElements` and `ElementEffects`):

| Function | Track name | Description | Returns |
|---|---|---|---|
| `generate_beats_track(y, sr, ...)` | Beats | Every beat, labelled 1-2-3-4 | `list[int]` ms |
| `generate_downbeats_track(y, sr, ...)` | Downbeats | Every 4th beat (bar 1), labelled by bar number | `list[int]` ms |
| `generate_onsets_track(y, sr, ...)` | Onsets | Every note/drum onset — denser than beats | `list[int]` ms |
| `generate_energy_peaks_track(y, sr, ...)` | Energy Peaks | RMS energy peaks — loudest moments | `list[int]` ms |
| `generate_lyrics_track(song, artist, duration_s, ...)` | Lyrics | Synced lyrics from lrclib.net — one mark per sung line | `list[(ms, text)]` |
| `generate_structure_track(audio_path, ...)` | Structure | LLM-generated section labels (Intro/Verse/Chorus…) | `list[dict]` |

**Beat placement helpers:**
- `beat_aligned_window(beat_times_ms, min_beats, max_beats)` — picks a random start beat and spans N beats; returns `(start_ms, end_ms)`.
- `structure_weighted_beat_window(beat_times_ms, structure, min_beats, max_beats)` — same but **biases toward high-intensity sections** (chorus = weight 1.0, intro/outro = 0.3). Used by all effect modules.
- `section_effect_placements(base_count, structure, beat_times_ms, min_beats, max_beats)` — distributes `base_count` effect windows across sections, scaled by intensity.
- `alternating_beat_placements(beat_times_ms, stride, duration_beats, structure)` — places effects every N beats, skipping low-intensity sections.

### Section intensity weights

```python
SECTION_INTENSITY = {
    "intro": 0.3, "verse": 0.5, "pre-chorus": 0.7,
    "chorus": 1.0, "bridge": 0.8, "outro": 0.3,
    "breakdown": 0.4, "drop": 1.0,
}
```

### Structure generation

`generate_structure_track()` calls Lemonade with the song name/artist/duration and gets back section labels with timestamps. Falls back to a simple 5-section default (Intro/Verse/Chorus/Verse2/Outro) if the call fails or returns invalid JSON.

---

## Layer & Overlap System

Effects are placed using `get_or_create_layer(elem, start_ms, end_ms, max_layers=N)`:

1. Scans existing `EffectLayer` children of the element for a free slot.
2. If all existing layers conflict, creates a new `EffectLayer` (up to `max_layers`).
3. Returns `None` if no layer is available — callers skip that placement.

Most effect modules use `max_layers=2`. The DEV text label pass uses `max_layers=4` to avoid overwriting real effects. The everything-group shader uses the first available layer unconditionally.

---

## AI / LLM Integration (Lemonade)

The project uses **Lemonade**, a local OpenAI-compatible LLM server.

```python
# Config (utils.py) — override with environment variables
LEMONADE_BASE_URL = os.environ.get("LEMONADE_URL", "http://localhost:8000/api/v1")
LEMONADE_MODEL    = os.environ.get("LEMONADE_MODEL", "")   # auto-discovers first model if blank
```

Lemonade is used for:
1. **Color palette** — 8 hex colors themed to the song/artist (Media sequences only).
2. **Song structure** — Intro/Verse/Chorus/Outro timestamps for the structure timing track.

Animation sequences skip AI and use `fixed_colors` (hardcoded 8-color set).

---

## Running the Generator

### Directly (CLI)

```bash
# Media sequence
python main.py --audio "E:\Audio\Pretty Baby - Alex Sampson.mp3" --artist "Alex Sampson" --song "Pretty Baby"

# Animation sequence
python main.py --type Animation --duration 60

# All options
python main.py --help
```

All path arguments (`--template`, `--layout`, `--output`, `--structure`) default to the `training data/` folder so only audio/song/artist need to change between runs.

### Via Flask web UI

```bash
python app.py
```

Then open `http://localhost:5000`.

#### Web UI features

| Feature | Details |
|---|---|
| **Lemonade status badge** | Header shows green/red dot; click for URL + model list; auto-refreshes every 30 s |
| **Async generation** | `/generate` returns immediately with a `task_id`; generation runs in a background thread |
| **Live log streaming** | SSE endpoint `/stream/<task_id>` streams every `print()` from the pipeline to the browser in real-time |
| **Model category preview** | "Preview Model Categories" button calls `/preview_categories` — shows colored chips per category before running a full generation |
| **Generation history** | Right-column sidebar lists last 20 runs with elapsed time and download links; persists for the session |
| **localStorage autocomplete** | Artist, Song, Sequence Name fields remember the last 15 values |
| **Per-request output isolation** | Output files are UUID-prefixed — concurrent users never overwrite each other |
| **Auto temp cleanup** | Downloaded files are deleted from disk 10 s after the download completes |
| **Friendly error messages** | Connection errors, missing files, and parse failures show human-readable messages; tracebacks stay server-side |
| **Duration field auto-hide** | Duration input is only shown when Sequence Type is Animation |

#### API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Serve the UI |
| `/generate` | POST | Start async generation; returns `{task_id}` |
| `/stream/<task_id>` | GET | SSE stream of log lines and completion event |
| `/status/<task_id>` | GET | Poll task status (fallback if SSE fails) |
| `/download/<filename>` | GET | Download generated XSQ; file auto-deleted after 10 s |
| `/lemonade_status` | GET | Check if local Lemonade LLM server is reachable |
| `/preview_categories` | POST | Parse layout XML and return model category breakdown |
| `/history` | GET | Return last 20 generation results for the session |
| `/get_defaults` | GET | Return default path/value configuration |

#### PyCharm run configuration

A `Flask Web App` run configuration is included in `.idea/runConfigurations/Flask_Web_App.xml`. Select it from the Run dropdown and click Run.

---

## Model Filtering

Models and groups are excluded from all effect placement if:
- `DisplayAs == "image"`
- `Protocol == "DMX"`
- Name starts with `MH-`

Groups are sorted before individual models in the output XSQ. Groups with `"last"` in the name sort to the very end.

---

## Model Categorization

`categorize_models(layout_models, layout_groups)` in `utils.py` assigns every model and group a category string. The category is used for effect selection, density tuning, and the DEV text label overlay.

### Category resolution — individual models

Resolution runs in this order; the first match wins:

#### Step 1 — Auto-skip
Applied before anything else:
- `DisplayAs == "image"` → `skip`
- `Protocol == "DMX"` → `skip`

Skipped models are excluded from all effect placement.

#### Step 2 — `[T:TypeHint]` description hint
If the model's `Description` attribute contains `[T:SomeType]`, that value (lowercased) becomes the category. This overrides everything else and is the recommended way to manually classify a model.

Examples:
```
Description="Roofline [T:line]"    → line
Description="Pixel matrix [T:matrix_horizontal]"  → matrix_horizontal
Description="Flood 1 [T:flood]"    → flood
Description="[T:skip]"             → skip (excluded)
```

Known useful hints: `arch`, `candy_cane`, `cross`, `cube`, `flood`, `icicles`, `line`,
`matrix`, `matrix_horizontal`, `matrix_column`, `matrix_pole`, `snowflake`, `sphere`,
`spinner`, `star`, `tune_to`, `tree`, `mega_tree`, `window_frame`

#### Step 3 — `DisplayAs` attribute mapping
If no hint is present, the `DisplayAs` value is looked up in this table:

| DisplayAs | Category |
|---|---|
| Arches | `arch` |
| Single Line | `line` |
| Tree | `tree` |
| Matrix | `matrix` |
| Star | `star` |
| Spinner | `spinner` |
| Sphere | `sphere` |
| Icicles | `icicles` |
| Wreath | `unknown` |
| Custom | `unknown` |
| Window Frame | `window_frame` |
| Snowflake | `snowflake` |
| ModelGroup | `group` |

Anything not in this table resolves to `unknown`.

#### Step 4 — Flood promotion
After Step 3, any model classified as `"line"` is re-checked using its node count attributes:
- `NodesPerString × NumStrings == 1` AND `LightsPerNode == 1` → reclassified as `flood`
- Falls back to `parm1` / `parm2` for older xLights XML that uses positional parameters instead of named attributes.

A single-node, single-light Single Line is a flood/par-can style fixture, not an addressable strand.

### Category resolution — groups

Groups are classified after all individual models are resolved.

#### Step 1 — Everything group
The group with the most child models is designated the `everything_group`. It receives only a Black Cherry Cosmos shader spanning the full sequence and is excluded from all other effect placement.

#### Step 2 — `[T:TypeHint]` description hint
Same as individual models — overrides all other logic.

#### Step 3 — Member homogeneity
- All children share one non-`unknown` category → group inherits that category.
- Children span multiple categories → `generic_group` (excluded from effect placement).

### Category resolution — secondary name pass

After all models and groups are classified, any remaining `unknown` entries go through a **name-based substring pass** using rules loaded from `name_category_rules.json`. Rules are checked in order; the first match wins. All matches are case-insensitive.

Example rule file entry:
```json
{"match": "matrix", "category": "matrix"}
```

This would resolve `"Seed Matrix"` → `matrix`, `"LED Matrix Panel"` → `matrix`, etc.

Set `"exact": true` on a rule for a whole-name match instead of substring:
```json
{"match": "Roof", "category": "line", "exact": true}
```

The file is hot-loaded at generation time — edit it without restarting. If the file is missing or malformed, a minimal hardcoded fallback is used and a warning is printed.

### Category resolution — parent group inheritance

After the name pass, any model or group still marked `unknown` (or `generic_group`) checks which groups it belongs to. If all parent groups that have a usable category agree on the **same** category, the model inherits it.

- Only `unknown` and `generic_group` items are candidates.
- Parent categories of `unknown`, `generic_group`, `everything_group`, or `skip` are not inherited.
- If a model's parents disagree (e.g. one parent is `arch`, another is `tree`), the model stays `unknown` rather than guessing.

Example: `"West Arch 3"` has `DisplayAs=Custom` → `unknown`. Its only parent group is `"Arches West"` which resolved to `arch`. Result: `"West Arch 3"` → `arch`.

### Category resolution — exact-name overrides

Final pass. `name_exact_overrides.json` maps exact model/group names (case-insensitive) to categories. This is the highest user-controlled precedence and runs after everything else, so it can correct any automatic result.

```json
{
  "overrides": {
    "Roof":         "line",
    "Singing Face": "skip",
    "Pixel Panel":  "matrix"
  }
}
```

Auto-skip models (`image`, `DMX`) are never overridden — hardware rules take priority.

### Full resolution order (precedence high → low)

| Step | Method | Scope |
|---|---|---|
| 1 | Auto-skip (DisplayAs=image / Protocol=DMX) | Individual models |
| 2 | `[T:TypeHint]` in Description | Models + groups |
| 3 | `DisplayAs` attribute mapping | Individual models |
| 4 | Flood promotion (parm1=1 or parm1=group count) | Individual models |
| 5 | Everything-group detection (largest group) | Groups |
| 6 | Member homogeneity (all children same category) | Groups |
| 7 | Substring name rules (`name_category_rules.json`) | Models + groups |
| 8 | Parent group inheritance | Models + groups |
| 9 | Exact-name overrides (`name_exact_overrides.json`) | Models + groups |
| — | Still unresolved → `unknown` (logged) | — |

### Categorization log

At generation time, stdout shows:
```
Model categories: arch=12, flood=4, line=8, matrix=5, tree=3, unknown=1
Groups: typed=8, generic=6 (excluded), everything=01 Everything (209 total groups)
Name-resolved (3): Seed Matrix → matrix, Big Line → line, Par Can Wash → flood
Parent-inherited (2): West Arch 3 → arch, East Arch 5 → arch
Exact overrides (1): Singing Face → skip
Still unknown (1): Weird Thing 1
```

---

## EffectDB Deduplication

`EffectDBRegistry` in `utils.py` collects all unique effect-settings strings across every placed effect. Each unique string gets a 0-based index; `Effect` elements reference it with `ref="N"`. All entries are written to the `<EffectDB>` section at the end of generation. This keeps the XSQ compact — identical settings strings are stored once regardless of how many effects reference them.

---

## Future Tasks / Roadmap

### High priority — next up
- [x] **Category-aware effect selection** — `EFFECT_EXCLUDED_CATS` + `filter_by_effect()` in `utils.py`; all 33 effect calls in `main.py` pre-filter via `fe()`/`fg()` helpers.
- [x] **Use new timing tracks in effects** — `downbeats` captured; burst effects (Fireworks/Lightning/Shockwave/Strobe) use `energy_peaks`; slow sweeping (Bars/Color Wash/Wave/Morph/Curtain) use `downbeats`; rapid (On/Shimmer/Twinkle) use `onsets`.
- [ ] **Smarter palette application** — cool/desaturated colors in low-intensity sections (intro, outro, verse), warm/saturated in high-energy sections (chorus, drop). Section intensity values are already available via `section_intensity()`.
- [x] **Identify singing prop category** — `_is_singing_prop()` requires both `Mouth-WQ` + `Eyes-Open` numeric pixel lists in `<faceInfo>`; inactive models excluded.
- [x] **Singing props → Faces effect only** — `singing_face_effect.py`; uses `CustomColors='1'` face def; excluded from all other effect modules via `get_eligible_models()`.
- [x] **Add snowflake, cane, cube categories** — `cube` added to `name_category_rules.json`; both included in `EFFECT_EXCLUDED_CATS` for 2D-only effects.
- [x] **Stem separation** — `stem_separator.py` (Demucs `htdemucs_6s`); timing tracks for Kick/Snare/Hihat/Toms/Cymbal/Bass/Guitar/Piano; blank labels; stems cached per audio file.


### Medium priority
- [x] **Per-model effect budgeting** — `CATEGORY_EFFECT_BUDGET` dict + `EffectBudget` class in `utils.py`; enforced in `get_or_create_layer` via `_active_budget` global; set per run in `main.py`.
- [x] **Effect density tuning** — budget caps naturally limit density per category (flood=4, matrix/mega_tree=20, etc.); no effect-module changes required.
- [x] **Section-aware effect gating** — `chorus_only_placements()` in `utils.py`; `Strobe`, `Lightning`, `Fireworks` restricted to chorus/drop (threshold ≥ 0.9).
- [x] **Lyrics-driven vocal gating** — `filter_beats_vocals_only()` in `utils.py`; `_vocal` beat list used for On/Twinkle/Shimmer; suppresses rapid effects during 8s+ instrumental gaps.
- [x] **App.py / web UI sync** — paths now relative to script dir (VM-compatible); `sequence_name` and `duration` added to form, handler, and `index.html`.
- [x] **Async generation** — background thread + SSE streaming; browser never times out; live log panel streams every `print()` line.
- [x] **Lemonade health badge** — `/lemonade_status` endpoint; header badge shows online/offline with model list; auto-refreshes every 30 s.
- [x] **Model category preview** — `/preview_categories` parses layout XML and returns categorized model breakdown before generation.
- [x] **Per-request UUID output isolation** — prevents concurrent-user file collisions; UUID prefix stripped from download filename.
- [x] **Friendly error messages** — maps `ConnectionRefusedError`, `FileNotFoundError`, `ET.ParseError` to readable strings; tracebacks stay server-side.
- [x] **Auto temp file cleanup** — generated XSQ deleted 10 s after download completes.
- [x] **Generation history sidebar** — last 20 runs with elapsed time and download links; in-memory `deque`.
- [x] **localStorage autocomplete** — Artist, Song, Sequence Name remember last 15 values across sessions.
- [x] **Duration field auto-hide** — hidden for Media sequences, visible for Animation only.
- [x] **PyCharm run config** — `Flask Web App` added to `.idea/runConfigurations/Flask_Web_App.xml`.

### Choreography (new priority tier — highest impact on output quality)
- [x] **Spatial position extraction** — `get_model_positions()` reads `WorldPosX/Z` from layout; `sort_elements_by_position()` sorts elements by axis.
- [x] **Phrase boundary detection** — `generate_phrase_boundaries()` returns one timestamp per 4 downbeats.
- [x] **Spatial sweep effect** — `spatial_sweep.py`; staggered On effect fires left→right (alternating) at phrase boundaries in sections with intensity ≥ 0.5; capped at 3 sweeps per section.
- [x] **Section foreground assignment** — `FOREGROUND_CATS_BY_SECTION` + `get_foreground_elements()`; Strobe/Lightning/Fireworks now only fire on chorus-foreground prop categories (matrix/mega_tree/cube/tree_360).
- [x] **Learn from example XSQ files** — `analyze_choreography.py` reads `training_data.json` (1.6M obs from 379 real XSQs); builds `choreography_probs.json` mapping each prop category to effect probability distribution. `filter_by_probability()` in `utils.py` gates every effect call against learned thresholds. `sample_effect_for_category()` in `param_sampler.py` for weighted random sampling.
- [ ] **Smarter palette application** — cool/desaturated in intro/verse, warm/saturated in chorus/drop (section intensity already available).
- [ ] **Cross-prop coordination (call & response)** — designate one prop category per section as "lead" and others as "support"; support props hold a sustained color while lead fires reactive effects.

### Web app / UX (next up)
- [ ] **Lemonade URL config** — let the user set a custom Lemonade URL from the UI and persist it in `localStorage`; surface in the badge tooltip.
- [ ] **Cancel in-flight generation** — add a Cancel button that signals the background thread to stop early (requires cooperative cancellation flag checked between effect modules).
- [ ] **Session-persistent history** — write history to a local SQLite or JSON file so it survives server restarts.
- [ ] **Shareable generation presets** — export/import JSON of artist/song/type/sequence_name so a preset can be pasted or bookmarked.

### Low priority / future ideas
- [ ] **Harmonic/percussive separation** (`librosa.effects.hpss`) — cleaner kick/snare detection on percussive channel; chord-change detection on harmonic channel.
- [ ] **Spectral flux peaks** — catch section transitions that the LLM structure track misses.
- [ ] **Vocal activity detection** — mid-frequency harmonic energy as a proxy for "vocals present" without requiring a lyrics file.
- [ ] **Chord change detection** — `librosa.feature.chroma_stft` to mark harmonic shifts as a timing track.
- [ ] **Phrase boundary segmentation** — `librosa.segment` recurrence matrix for phrase-level timing independent of the LLM.


### Completed
- [x] .xsq output validated — generated files load and play correctly in xLights.
- [x] Timing tracks inactive — all generated timing tracks use `active="0"` so they don't interfere with playback.
- [x] Model categorization — `categorize_models()` with 9-step resolution pipeline (see Model Categorization section).
- [x] Unknown model logging — stdout shows each resolution pass result and lists any still-unknown names.
- [x] `name_category_rules.json` — editable substring rules for secondary name pass.
- [x] `name_exact_overrides.json` — exact-name overrides as highest user-controlled precedence.
- [x] Parent group inheritance — unknowns inherit category from parent group when all parents agree.
- [x] Flood promotion — Single Line with `NodesPerString × NumStrings == 1` and `LightsPerNode == 1` → `flood`; falls back to `parm1`/`parm2` for older XML.
- [x] Beat-aligned effect placement — all 33 modules use `structure_weighted_beat_window` / `section_effect_placements`.
- [x] Structure-aware intensity scaling — section weights (chorus=1.0, intro=0.3, etc.) applied to effect counts.
- [x] Overlap prevention — `get_or_create_layer` prevents effects from overwriting each other; text label uses `max_layers=4`.
- [x] EffectDB deduplication — `EffectDBRegistry` stores settings strings once; `Effect` elements reference by index.
- [x] Everything group — largest group receives only a Black Cherry Cosmos shader; excluded from all other effects.
- [x] Lemonade LLM integration — color palette + song structure generated locally; auto-discovers model if `LEMONADE_MODEL` not set.
- [x] Training data pipeline — 1.6M observations from real `.xsq` files → `param_sampler.py`.
- [x] CLI interface — `argparse` in `main.py`; two PyCharm run configs (`Generate Media Sequence`, `Generate Animation Sequence`).
- [x] Audio loaded once — `_load_audio(audio_path)` returns `(y, sr)`; all librosa generators share the same load.
- [x] Beats timing track — librosa beat detection, labels cycle 1–2–3–4.
- [x] Downbeats timing track — every 4th beat labelled by bar number.
- [x] Onsets timing track — `librosa.onset.onset_detect`, denser than beats.
- [x] Energy Peaks timing track — RMS peaks via `librosa.util.peak_pick`, marks loudest moments.
- [x] Lyrics timing track — synced lyrics from lrclib.net (no API key); `/api/get` with duration first, `/api/search` + nearest-duration fallback.
- [x] Structure timing track — LLM-generated section labels with timestamps; 5-section fallback on failure.
- [x] 33 effect modules — covers all high/medium-frequency effects from 1.6M training observations.
- [x] DEV text label overlay — last 4 beats show category name per model on a spare layer (non-destructive, `max_layers=4`).
- [x] Category-aware effect selection — `EFFECT_EXCLUDED_CATS` + `filter_by_effect()`; floods/lines excluded from 2D effects; SingleStrand excluded from matrices/trees.
- [x] Timing track routing — burst effects use `energy_peaks`; slow effects use `downbeats`; rapid effects use `onsets`; all fall back to `beats`.
- [x] Singing prop detection — `Mouth-WQ` + `Eyes-Open` check; `singing_face_effect.py`; inactive models excluded.
- [x] Stem separation — Demucs `htdemucs_6s`; Kick/Snare/Hihat/Toms/Cymbal/Bass/Guitar/Piano timing tracks; stems cached.
- [x] `beat_aligned_window` crash fix — clamps min/max beats to available markers (prevents crash with sparse downbeat/energy_peak lists).
- [x] Energy peaks tuned — `delta=mean*0.2`, `wait=0.25s`; ~3–4× more peaks than before.

---

## Dependencies

```
Flask==2.3.3
Werkzeug==2.3.7
openai>=1.0.0        # Lemonade / any OpenAI-compatible LLM
grok3api==0.1.0rc2
setuptools==80.9.0
mutagen              # MP3 duration
librosa              # Beat detection, onset detection, audio analysis
numpy                # Audio processing
scipy                # Bandpass/highpass filters for drum sub-separation
demucs               # Stem separation (drums, bass, guitar, piano, vocals) — downloads ~300MB model on first run
```

Lemonade must be running locally before generating Media sequences. Set `LEMONADE_URL` if it's not on the default port 8000.
