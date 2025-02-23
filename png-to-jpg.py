from flask import Flask, request, send_file, jsonify
from PIL import Image
import io
import os

app = Flask(__name__)

@app.route('/')
def index():
    # Simple HTML form for uploading a PNG image
    return '''
    <h1>PNG to JPEG Converter</h1>
    <form method="post" action="/convert" enctype="multipart/form-data">
        <input type="file" name="file" accept="image/png">
        <input type="submit" value="Convert">
    </form>
    '''

@app.route('/convert', methods=['POST'])
def convert():
    # Check if a file is provided
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Open the uploaded image and convert it to JPEG
        image = Image.open(file)
        rgb_im = image.convert('RGB')
        img_io = io.BytesIO()
        rgb_im.save(img_io, 'JPEG', quality=95)
        img_io.seek(0)
        return send_file(
            img_io,
            mimetype='image/jpeg',
            as_attachment=True,
            attachment_filename='converted.jpg'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Use the PORT environment variable if available (for cloud hosting)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
