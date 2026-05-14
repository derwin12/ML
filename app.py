from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context, after_this_request
import os
import sys
import tempfile
import traceback
import threading
import queue
import uuid
import json
import time
import zipfile
from collections import Counter, deque
from werkzeug.utils import secure_filename
import xml.etree.ElementTree as ET

from main import create_xsq_from_template

# ---------------------------------------------------------------------------
# Thread-aware stdout capture
# Routes print() calls from worker threads into per-task log queues while
# still writing to the real stdout for server-side debugging.
# ---------------------------------------------------------------------------

class _ThreadAwareWriter:
    """Proxy for sys.stdout that routes writes to per-task queues by thread id."""

    def __init__(self, original):
        self._original = original
        self._lock = threading.Lock()
        self._thread_queues = {}

    def register(self, q):
        with self._lock:
            self._thread_queues[threading.current_thread().ident] = q

    def unregister(self):
        with self._lock:
            self._thread_queues.pop(threading.current_thread().ident, None)

    def write(self, text):
        with self._lock:
            q = self._thread_queues.get(threading.current_thread().ident)
        if q and text.strip():
            q.put(('log', text.rstrip('\n')))
        self._original.write(text)

    def flush(self):
        self._original.flush()

    def __getattr__(self, name):
        return getattr(self._original, name)


_writer = _ThreadAwareWriter(sys.stdout)
sys.stdout = _writer

# ---------------------------------------------------------------------------
# App + config
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

_HERE = os.path.dirname(os.path.abspath(__file__))
_TD   = os.path.join(_HERE, "training data")

DEFAULT_VALUES = {
    'template_xsq':    os.path.join(_TD, "folder 1", "Empty Sequence.xsq"),
    'xlights_xml':     os.path.join(_TD, "folder 1", "xlights_rgbeffects.xml"),
    'structure_json':  os.path.join(_TD, "templates", "xlights_template_structures.json"),
    'audio_path':      r"E:\2023\ShowFolder3D\Audio\Pretty Baby - Alex Sampson.mp3",
    'sequence_type':   "Media",
    'artist_name':     "Alex Sampson",
    'song_name':       "Pretty Baby",
    'sequence_name':   "Pretty Baby_AI",
    'duration':        "",
}

# ---------------------------------------------------------------------------
# In-memory task store + history ring buffer
# ---------------------------------------------------------------------------

TASKS: dict = {}          # task_id -> {status, queue, output_path, error, meta}
HISTORY: deque = deque(maxlen=20)
_TASKS_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------

_ERROR_MAP = [
    (ConnectionRefusedError,      "Lemonade is not running. Start the local LLM server (default: http://localhost:8000)."),
    (FileNotFoundError,           None),   # use str(e) — already descriptive
    (ET.ParseError,               "Could not parse the XML layout file. Verify it is a valid xLights export."),
    (ValueError,                  None),
]

def _friendly_error(exc: Exception) -> str:
    for exc_type, msg in _ERROR_MAP:
        if isinstance(exc, exc_type):
            return msg or str(exc)
    # Check for connection errors by string (openai wraps them)
    msg = str(exc)
    if "connection" in msg.lower() or "refused" in msg.lower():
        return "Lemonade is not running. Start the local LLM server (default: http://localhost:8000)."
    return f"Generation failed: {msg}"

# ---------------------------------------------------------------------------
# xsqz bundler
# xsqz is a standard ZIP renamed to .xsqz.  xLights expects at the root:
#   <sequence>.xsq  — with <mediaFile> rewritten to basename only
#   xlights_rgbeffects.xml
#   xlights_networks.xml  (optional)
#   <audio file>  — basename only
# ---------------------------------------------------------------------------

_NETWORKS_XML = os.path.join(_TD, "folder 1", "xlights_networks.xml")

def _bundle_xsqz(xsq_path: str, audio_path: str | None,
                 xlights_xml_path: str, xsqz_path: str) -> None:
    """Create an xsqz bundle from the generated xsq and supporting files."""
    tree = ET.parse(xsq_path)
    root = tree.getroot()

    # Rewrite <mediaFile> to just the audio basename so xLights finds it
    # inside the zip without any absolute path.
    if audio_path:
        audio_basename = os.path.basename(audio_path)
        for elem in root.iter("mediaFile"):
            elem.text = audio_basename

    import io
    xsq_buf = io.StringIO()
    tree.write(xsq_buf, encoding="unicode", xml_declaration=False)
    xsq_content = xsq_buf.getvalue()

    xsq_name = os.path.basename(xsq_path)
    # Strip the UUID prefix that was added for isolation (e.g. "abc12345_Name.xsq" → "Name.xsq")
    if '_' in xsq_name:
        xsq_name = xsq_name.split('_', 1)[1]

    with zipfile.ZipFile(xsqz_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(xsq_name, xsq_content)
        zf.write(xlights_xml_path, "xlights_rgbeffects.xml")
        if os.path.exists(_NETWORKS_XML):
            zf.write(_NETWORKS_XML, "xlights_networks.xml")
        if audio_path and os.path.exists(audio_path):
            zf.write(audio_path, os.path.basename(audio_path))

    print(f"xsqz bundle written → {os.path.basename(xsqz_path)}")


# ---------------------------------------------------------------------------
# Background generation worker
# ---------------------------------------------------------------------------

def _run_generation(task_id: str, kwargs: dict, meta: dict):
    task = TASKS[task_id]
    q = task['queue']
    _writer.register(q)
    start = time.time()
    output_xsq = kwargs['output_xsq']
    bundle_xsqz = meta.get('bundle_xsqz', False)
    try:
        create_xsq_from_template(**kwargs)
        if not os.path.exists(output_xsq):
            raise RuntimeError("Output file was not created.")

        # Optionally wrap everything into an xsqz bundle
        output_file = output_xsq
        download_filename = os.path.basename(output_xsq)
        if bundle_xsqz:
            xsqz_path = output_xsq.replace('.xsq', '.xsqz')
            _bundle_xsqz(
                xsq_path=output_xsq,
                audio_path=kwargs.get('audio_path'),
                xlights_xml_path=kwargs['xlights_xml'],
                xsqz_path=xsqz_path,
            )
            # Remove the intermediate .xsq now that we have the bundle
            try:
                os.unlink(output_xsq)
            except OSError:
                pass
            output_file = xsqz_path
            download_filename = os.path.basename(xsqz_path)

        elapsed = round(time.time() - start, 1)
        download_url = f"/download/{download_filename}"
        with _TASKS_LOCK:
            task['status'] = 'done'
            task['output_path'] = output_file
            task['elapsed'] = elapsed
        HISTORY.appendleft({
            'task_id':       task_id,
            'timestamp':     time.strftime('%Y-%m-%d %H:%M:%S'),
            'artist':        meta.get('artist_name', ''),
            'song':          meta.get('song_name', ''),
            'sequence_type': meta.get('sequence_type', ''),
            'sequence_name': meta.get('sequence_name', ''),
            'output_file':   download_filename,
            'elapsed':       elapsed,
            'status':        'done',
            'download_url':  download_url,
            'bundled':       bundle_xsqz,
        })
        q.put(('done', download_url))
    except Exception as exc:
        traceback.print_exc()
        friendly = _friendly_error(exc)
        with _TASKS_LOCK:
            task['status'] = 'error'
            task['error'] = friendly
        HISTORY.appendleft({
            'task_id':       task_id,
            'timestamp':     time.strftime('%Y-%m-%d %H:%M:%S'),
            'artist':        meta.get('artist_name', ''),
            'song':          meta.get('song_name', ''),
            'sequence_type': meta.get('sequence_type', ''),
            'sequence_name': meta.get('sequence_name', ''),
            'output_file':   '',
            'elapsed':       round(time.time() - start, 1),
            'status':        'error',
            'download_url':  '',
        })
        q.put(('error', friendly))
    finally:
        _writer.unregister()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html', defaults=DEFAULT_VALUES)


@app.route('/get_defaults')
def get_defaults():
    return jsonify(DEFAULT_VALUES)


@app.route('/generate', methods=['POST'])
def generate_sequence():
    try:
        xlights_xml_file = request.files.get('xlights_xml')
        audio_file       = request.files.get('audio_path')

        sequence_type  = request.form.get('sequence_type',  DEFAULT_VALUES['sequence_type'])
        artist_name    = request.form.get('artist_name',    DEFAULT_VALUES['artist_name'])
        song_name      = request.form.get('song_name',      DEFAULT_VALUES['song_name'])
        sequence_name  = request.form.get('sequence_name',  DEFAULT_VALUES['sequence_name']) or "AI_Sequence"
        duration_str   = request.form.get('duration',       DEFAULT_VALUES['duration'])
        duration       = int(duration_str) if duration_str and duration_str.isdigit() else None
        use_defaults   = request.form.get('use_default_paths') == 'true'
        bundle_xsqz    = request.form.get('bundle_xsqz') == 'true'
        output_filename = f"{sequence_name.replace(' ', '-')}.xsq"

        def _save(file):
            if file and file.filename:
                fname = secure_filename(file.filename)
                path  = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                file.save(path)
                return path
            return None

        xlights_xml_path = _save(xlights_xml_file)
        audio_path       = _save(audio_file)

        if use_defaults:
            if not xlights_xml_path and os.path.exists(DEFAULT_VALUES['xlights_xml']):
                xlights_xml_path = DEFAULT_VALUES['xlights_xml']
            if not audio_path and os.path.exists(DEFAULT_VALUES['audio_path']):
                audio_path = DEFAULT_VALUES['audio_path']

        template_xsq_path   = DEFAULT_VALUES['template_xsq']
        structure_json_path = DEFAULT_VALUES['structure_json']

        if not template_xsq_path or not os.path.exists(template_xsq_path):
            return jsonify({'error': 'Template XSQ not found at default path.'}), 400
        if not xlights_xml_path:
            return jsonify({'error': 'xLights XML is required. Upload a file or enable Use Defaults.'}), 400

        # Unique output path per request — prevents concurrent-user collisions
        task_id = str(uuid.uuid4())
        safe_name = secure_filename(output_filename or 'Generated_Sequence.xsq')
        if not safe_name.lower().endswith('.xsq'):
            safe_name += '.xsq'
        unique_name = f"{task_id[:8]}_{safe_name}"
        output_xsq = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

        kwargs = dict(
            template_xsq   = template_xsq_path,
            xlights_xml    = xlights_xml_path,
            output_xsq     = output_xsq,
            structure_json = structure_json_path,
            sequence_type  = sequence_type,
            sequence_name  = sequence_name,
            artist_name    = artist_name,
            song_name      = song_name,
        )
        if audio_path:
            kwargs['audio_path'] = audio_path
        if duration:
            kwargs['duration'] = duration

        meta = dict(artist_name=artist_name, song_name=song_name,
                    sequence_type=sequence_type, sequence_name=sequence_name,
                    bundle_xsqz=bundle_xsqz)

        log_queue = queue.Queue()
        with _TASKS_LOCK:
            TASKS[task_id] = {'status': 'running', 'queue': log_queue,
                              'output_path': None, 'error': None, 'meta': meta}

        thread = threading.Thread(target=_run_generation, args=(task_id, kwargs, meta), daemon=True)
        thread.start()

        return jsonify({'task_id': task_id})

    except Exception as exc:
        return jsonify({'error': _friendly_error(exc)}), 500


@app.route('/stream/<task_id>')
def stream_task(task_id):
    if task_id not in TASKS:
        return jsonify({'error': 'Task not found'}), 404

    def generate():
        task = TASKS[task_id]
        q    = task['queue']
        # Drain any logs already queued before the client connected
        while True:
            try:
                event_type, data = q.get(timeout=60)
                payload = json.dumps({'type': event_type, 'message': data} if event_type in ('log', 'error')
                                     else {'type': event_type, 'download_url': data})
                yield f"data: {payload}\n\n"
                if event_type in ('done', 'error'):
                    break
            except queue.Empty:
                # Send a heartbeat so the browser doesn't time out
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/status/<task_id>')
def task_status(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    resp = {'status': task['status']}
    if task['status'] == 'done':
        resp['download_url'] = f"/download/{os.path.basename(task['output_path'])}"
    elif task['status'] == 'error':
        resp['error'] = task['error']
    return jsonify(resp)


@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    @after_this_request
    def _schedule_cleanup(response):
        # Delete the temp file 10 s after the response is sent
        def _delete():
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except OSError:
                pass
        threading.Timer(10.0, _delete).start()
        return response

    return send_file(file_path, as_attachment=True, download_name=filename.split('_', 1)[-1] if '_' in filename else filename)


@app.route('/lemonade_status')
def lemonade_status():
    try:
        from utils import LEMONADE_BASE_URL
        from openai import OpenAI
        client = OpenAI(base_url=LEMONADE_BASE_URL, api_key="none", timeout=3)
        models = client.models.list()
        names = [m.id for m in models.data]
        return jsonify({'status': 'online', 'url': LEMONADE_BASE_URL, 'models': names})
    except Exception as exc:
        msg = str(exc)
        if "connection" in msg.lower() or "refused" in msg.lower() or "timeout" in msg.lower():
            friendly = "Lemonade is not running"
        else:
            friendly = msg[:120]
        return jsonify({'status': 'offline', 'error': friendly})


@app.route('/preview_categories', methods=['POST'])
def preview_categories():
    xlights_xml_file = request.files.get('xlights_xml')
    use_default      = request.form.get('use_default') == 'true'

    if use_default:
        xml_path = DEFAULT_VALUES['xlights_xml']
        if not os.path.exists(xml_path):
            return jsonify({'error': 'Default xlights XML not found.'}), 400
    elif xlights_xml_file and xlights_xml_file.filename:
        fname    = secure_filename(xlights_xml_file.filename)
        xml_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        xlights_xml_file.save(xml_path)
    else:
        return jsonify({'error': 'No XML file provided.'}), 400

    try:
        layout_tree   = ET.parse(xml_path)
        layout_root   = layout_tree.getroot()
        layout_models = layout_root.findall(".//model")
        layout_groups = layout_root.findall(".//modelGroup")

        from utils import categorize_models
        categories = categorize_models(layout_models, layout_groups)

        counts     = Counter(v for v in categories.values())
        skip_count = counts.pop('skip', 0)
        total      = len(categories)

        return jsonify({
            'total':       total,
            'skip':        skip_count,
            'by_category': dict(sorted(counts.items(), key=lambda x: -x[1])),
            'models':      [{'name': k, 'category': v}
                            for k, v in sorted(categories.items()) if v != 'skip'],
        })
    except ET.ParseError:
        return jsonify({'error': 'Could not parse XML. Ensure it is a valid xLights layout export.'}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/history')
def history():
    return jsonify(list(HISTORY))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
