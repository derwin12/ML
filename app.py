from flask import Flask, render_template, request, jsonify, send_file
import os
import tempfile
import traceback
from werkzeug.utils import secure_filename

# Import your existing function
from main import create_xsq_from_template  # Replace with your actual import

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Default values from your Python code, updated with artist and song name
DEFAULT_VALUES = {
    'template_xsq': r"C:\Users\daryl\PycharmProjects\ML\training data\folder 1\Empty Sequence.xsq",
    'xlights_xml': r"C:\\Users\\daryl\\PycharmProjects\\ML\\training data\\folder 1\\xlights_rgbeffects.xml",
    'output_filename': "Generated_Sequence.xsq",
    'structure_json': r"C:\\Users\\daryl\\PycharmProjects\\ML\\training data\\templates\\xlights_template_structures.json",
    'audio_path': r"E:\2023\ShowFolder3D\Audio\Pretty Baby - Alex Sampson.mp3",
    'sequence_type': "Media",
    'artist_name': "Alex Sampson",
    'song_name': "Pretty Baby"
}

@app.route('/')
def index():
    return render_template('index.html', defaults=DEFAULT_VALUES)

@app.route('/get_defaults')
def get_defaults():
    """API endpoint to get default values"""
    return jsonify(DEFAULT_VALUES)

@app.route('/generate', methods=['POST'])
def generate_sequence():
    try:
        # Get form data
        xlights_xml = request.files.get('xlights_xml')
        audio_file = request.files.get('audio_path')

        # Get text inputs
        sequence_type = request.form.get('sequence_type', DEFAULT_VALUES['sequence_type'])
        artist_name = request.form.get('artist_name', DEFAULT_VALUES['artist_name'])
        song_name = request.form.get('song_name', DEFAULT_VALUES['song_name'])
        use_default_paths = request.form.get('use_default_paths') == 'true'

        # Handle file paths - ALWAYS use hardcoded template_xsq and structure_json
        template_xsq_path = DEFAULT_VALUES['template_xsq']
        structure_json_path = DEFAULT_VALUES['structure_json']

        # Save uploaded files if provided (only for xlights_xml and audio)
        def save_uploaded_file(file):
            if file and file.filename:
                filename = secure_filename(file.filename)
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(temp_path)
                return temp_path
            return None

        xlights_xml_path = save_uploaded_file(xlights_xml)
        audio_path = save_uploaded_file(audio_file)

        # If using default paths and no file was uploaded, use the default paths for xlights_xml and audio
        if use_default_paths:
            if not xlights_xml_path and os.path.exists(DEFAULT_VALUES['xlights_xml']):
                xlights_xml_path = DEFAULT_VALUES['xlights_xml']
            if not audio_path and os.path.exists(DEFAULT_VALUES['audio_path']):
                audio_path = DEFAULT_VALUES['audio_path']

        # Create output path
        output_filename = request.form.get('output_filename', DEFAULT_VALUES['output_filename'])
        output_xsq = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(output_filename))

        # Validate required files
        if not template_xsq_path or not os.path.exists(template_xsq_path):
            return jsonify({'error': 'Template XSQ file is required and could not be found at default path'}), 400

        if not xlights_xml_path:
            return jsonify({'error': 'Xlights XML file is required and could not be found at default path'}), 400

        # Call your function with new parameters
        create_xsq_from_template(
            template_xsq=template_xsq_path,
            xlights_xml=xlights_xml_path,
            output_xsq=output_xsq,
            structure_json=structure_json_path,
            audio_path=audio_path,
            sequence_type=sequence_type,
            artist_name=artist_name,
            song_name=song_name
        )

        # Check if output was created
        if os.path.exists(output_xsq):
            # Return download link
            return jsonify({
                'success': True,
                'message': 'Sequence generated successfully!',
                'download_url': f'/download/{os.path.basename(output_xsq)}',
                'used_defaults': use_default_paths
            })
        else:
            return jsonify({'error': 'Output file was not created'}), 500

    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)