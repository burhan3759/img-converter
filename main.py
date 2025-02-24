from flask import Flask, request, send_file, jsonify
from PIL import Image
import io
import os
import zipfile

app = Flask(__name__)

def remove_background(image):
    """
    If the image has transparency (an alpha channel), this function creates
    a white background and composites the image over it.
    """
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        # Create a white background image of the same size as the original
        background = Image.new("RGB", image.size, (255, 255, 255))
        # Paste the image onto the background using its alpha channel as mask
        background.paste(image, mask=image.split()[-1])
        return background
    else:
        # No transparency: just convert to RGB (if needed)
        return image.convert("RGB")

@app.route('/')
def index():
    # Simple HTML form for bulk uploading PNG files
    return '''
    <h1>Bulk PNG to JPEG Converter (Background Removed)</h1>
    <form method="post" action="/convert" enctype="multipart/form-data">
        <input type="file" name="files" accept="image/png" multiple>
        <input type="submit" value="Convert">
    </form>
    '''

@app.route('/convert', methods=['POST'])
def convert():
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files selected'}), 400

    # Create an in-memory ZIP archive to store the converted images
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file in files:
            if file.filename == '':
                continue

            try:
                image = Image.open(file)
                # Remove the background (if any)
                image_no_bg = remove_background(image)
                img_io = io.BytesIO()
                image_no_bg.save(img_io, format='JPEG', quality=95)
                img_io.seek(0)

                # Use the original file name (without extension) and add .jpg extension
                base_name = os.path.splitext(file.filename)[0]
                jpeg_filename = f"{base_name}.jpg"
                
                # Write the JPEG image to the ZIP archive
                zip_file.writestr(jpeg_filename, img_io.read())
            except Exception as e:
                print(f"Error processing {file.filename}: {e}")
                continue

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        attachment_filename='converted_images.zip'
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # app.run(host='0.0.0.0', port=port)
