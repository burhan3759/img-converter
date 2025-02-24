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
    return '''
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8" />
        <title>Bulk PNG to JPEG Converter</title>
      </head>
      <body>
        <h1>Bulk PNG to JPEG Converter</h1>
        <p>Select your PNG files. Files will be grouped into batches of less than 30MB each.</p>
        <input type="file" id="fileInput" multiple accept="image/png" />
        <button id="uploadBtn">Convert</button>
        <div id="results"></div>
    
        <script>
          const MAX_BATCH_SIZE = 30 * 1024 * 1024;
    
          function splitFilesIntoBatches(files) {
            let batches = [];
            let currentBatch = [];
            let currentBatchSize = 0;
            
            for (let file of files) {
              if (file.size > MAX_BATCH_SIZE) {
                if (currentBatch.length > 0) {
                  batches.push(currentBatch);
                  currentBatch = [];
                  currentBatchSize = 0;
                }
                batches.push([file]);
              } else {
                if (currentBatchSize + file.size > MAX_BATCH_SIZE) {
                  batches.push(currentBatch);
                  currentBatch = [file];
                  currentBatchSize = file.size;
                } else {
                  currentBatch.push(file);
                  currentBatchSize += file.size;
                }
              }
            }
            if (currentBatch.length > 0) {
              batches.push(currentBatch);
            }
            return batches;
          }
    
          async function uploadBatch(batch, index) {
            const formData = new FormData();
            for (let file of batch) {
              formData.append('files', file);
            }
            try {
              const response = await fetch('/convert', {
                method: 'POST',
                body: formData
              });
              if (!response.ok) {
                throw new Error('Server responded with status ' + response.status);
              }
              const blob = await response.blob();
              const url = URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `converted_batch_${index}.zip`;
              link.textContent = `Download Batch ${index}`;
              document.getElementById('results').appendChild(link);
              document.getElementById('results').appendChild(document.createElement('br'));
            } catch (error) {
              console.error('Error uploading batch:', error);
              const errorMsg = document.createElement('p');
              errorMsg.textContent = `Error uploading batch ${index}: ${error}`;
              document.getElementById('results').appendChild(errorMsg);
            }
          }
    
          document.getElementById('uploadBtn').addEventListener('click', async () => {
            const input = document.getElementById('fileInput');
            const files = input.files;
            if (!files.length) {
              alert('Please select at least one file.');
              return;
            }
    
            const batches = splitFilesIntoBatches(files);
            document.getElementById('results').innerHTML = `<p>Uploading ${batches.length} batch(es)...</p>`;
            
            let index = 1;
            for (let batch of batches) {
              await uploadBatch(batch, index);
              index++;
            }
          });
        </script>
      </body>
    </html>
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
