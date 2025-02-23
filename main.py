from flask import Flask, request, send_file, jsonify
from PIL import Image
import io
import os
import zipfile

app = Flask(__name__)

@app.route('/')
def index():
    # HTML form for bulk image upload
    return '''
    <h1>Bulk PNG to JPEG Converter</h1>
    <form method="post" action="/convert" enctype="multipart/form-data">
        <input type="file" name="files" accept="image/png" multiple>
        <input type="submit" value="Convert">
    </form>
    '''

@app.route('/convert', methods=['POST'])
def convert():
    print('Enter converting PNG to JPEG function')
    # Check if files were provided
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files selected'}), 400

    # Create an in-memory ZIP archive
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        print('start loop')
        for file in files:
            if file.filename == '':
                continue  # Skip files with empty filenames

            try:
                # Open and convert the image
                print('start conversion')
                image = Image.open(file)
                rgb_image = image.convert('RGB')
                img_io = io.BytesIO()
                rgb_image.save(img_io, format='JPEG', quality=95)
                img_io.seek(0)

                # Use the original file name (without extension) and add .jpg extension
                base_name = os.path.splitext(file.filename)[0]
                jpeg_filename = f"{base_name}.jpg"
                
                # Write the JPEG image to the ZIP archive
                print('conversion success')
                zip_file.writestr(jpeg_filename, img_io.read())
            except Exception as e:
                # Log error for a file and continue with the next one
                print(f"Error processing {file.filename}: {e}")
                continue


    print('start zip')
    zip_buffer.seek(0)
    print('done zip')
    print('enjoy')
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        attachment_filename='converted_images.zip'
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # app.run(host='0.0.0.0', port=port)
