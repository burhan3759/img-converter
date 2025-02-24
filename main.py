from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import io
import os
import zipfile
import time

# Google Drive API libraries
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)
CORS(app)

# Configuration for Google Drive API
SERVICE_ACCOUNT_FILE = '/credentials/credentials.json'  # Path to your service account JSON
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def upload_to_drive(file_buffer, filename, folder_id, max_retries=5):
    """
    Uploads the file to Google Drive in the specified folder using resumable uploads.
    Uses an exponential backoff strategy for retries.
    Returns the uploaded file's ID.
    """
    attempt = 0
    delay = 1  # initial delay in seconds
    while attempt < max_retries:
        try:
            # Reset buffer position before each attempt.
            file_buffer.seek(0)
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            drive_service = build('drive', 'v3', credentials=credentials)
            
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            # Use resumable upload by setting resumable=True.
            media = MediaIoBaseUpload(file_buffer, mimetype='image/jpeg', resumable=True)
            request_drive = drive_service.files().create(
                body=file_metadata, media_body=media, fields='id'
            )
            
            response = None
            # Upload in chunks until the entire file is uploaded.
            while response is None:
                status, response = request_drive.next_chunk()
                if status:
                    print("Upload progress: %d%%." % int(status.progress() * 100))
            return response.get('id')
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                raise e
            print(f"Upload failed (attempt {attempt}/{max_retries}). Retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff: double the delay

def remove_background(image):
    """
    Removes transparency by compositing the image onto a white background.
    """
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        return background
    else:
        return image.convert("RGB")

@app.route('/')
def index():
    # Simple HTML form for testing
    return '''
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <title>Bulk PNG to JPEG Converter with Drive Upload (Batched)</title>
        </head>
        <body>
          <h1>Bulk PNG to JPEG Converter with Google Drive Upload</h1>
          <p>
            Enter your Google Drive Folder ID and select PNG files.
            Files will be automatically batched (each batch &lt; 30MB) and uploaded.
          </p>
          <label for="folder_id">Google Drive Folder ID:</label>
          <input type="text" id="folder_id" required>
          <br><br>
          <input type="file" id="fileInput" accept="image/png" multiple required>
          <br><br>
          <button id="uploadBtn">Convert and Upload</button>
          <div id="results"></div>

          <script>
            const MAX_BATCH_SIZE = 30 * 1024 * 1024; // 30 MB

            // Split the FileList into batches so that each batch's total size is <= MAX_BATCH_SIZE
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
                  // File is larger than max; push it as its own batch
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

            // Upload one batch by sending a FormData payload to /convert
            async function uploadBatch(batch, batchIndex, folderId) {
              const formData = new FormData();
              formData.append("folder_id", folderId);
              for (let file of batch) {
                formData.append("files", file);
              }
              try {
                const response = await fetch("/convert", {
                  method: "POST",
                  body: formData
                });
                if (!response.ok) {
                  throw new Error("Server responded with status " + response.status);
                }
                const result = await response.json();
                displayBatchResults(result, batchIndex);
              } catch (error) {
                console.error("Error uploading batch " + batchIndex + ":", error);
                const errorElem = document.createElement("p");
                errorElem.textContent = "Error uploading batch " + batchIndex + ": " + error;
                document.getElementById("results").appendChild(errorElem);
              }
            }

            // Display the results from each batch
            function displayBatchResults(result, batchIndex) {
              const resultsDiv = document.getElementById("results");
              const header = document.createElement("h3");
              header.textContent = "Results for Batch " + batchIndex;
              resultsDiv.appendChild(header);
              if (result.results && result.results.length > 0) {
                result.results.forEach(res => {
                  const p = document.createElement("p");
                  if (res.error) {
                    p.textContent = "Error processing " + res.original_filename + ": " + res.error;
                  } else {
                    p.innerHTML = "Converted " + res.original_filename + " to " + res.converted_filename +
                      " - <a href='" + res.drive_file_link + "' target='_blank'>View on Drive</a>";
                  }
                  resultsDiv.appendChild(p);
                });
              } else {
                const p = document.createElement("p");
                p.textContent = "No files processed in batch " + batchIndex;
                resultsDiv.appendChild(p);
              }
            }

            document.getElementById("uploadBtn").addEventListener("click", async () => {
              const folderId = document.getElementById("folder_id").value.trim();
              if (!folderId) {
                alert("Please enter a Google Drive Folder ID.");
                return;
              }
              const fileInput = document.getElementById("fileInput");
              if (!fileInput.files.length) {
                alert("Please select at least one file.");
                return;
              }
              const batches = splitFilesIntoBatches(fileInput.files);
              document.getElementById("results").innerHTML = `<p>Uploading ${batches.length} batch(es)...</p>`;
              let batchIndex = 1;
              for (const batch of batches) {
                await uploadBatch(batch, batchIndex, folderId);
                batchIndex++;
              }
            });
          </script>
        </body>
      </html>
    '''

@app.route('/convert', methods=['POST'])
def convert():
    folder_id = request.form.get('folder_id')
    if not folder_id:
        return jsonify({'error': 'Google Drive Folder ID is required'}), 400

    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files selected'}), 400

    results = []
    for file in files:
        if file.filename == '':
            continue
        try:
            # Open the uploaded PNG file
            image = Image.open(file)
            # Remove transparency (if any) by compositing on white
            image_no_bg = remove_background(image)
            img_io = io.BytesIO()
            image_no_bg.save(img_io, format='JPEG', quality=95)
            # Construct a new filename with .jpg extension
            base_name = os.path.splitext(file.filename)[0]
            jpeg_filename = f"{base_name}.jpg"
            # Upload the converted image to Google Drive
            drive_file_id = upload_to_drive(img_io, jpeg_filename, folder_id)
            drive_file_link = f"https://drive.google.com/file/d/{drive_file_id}/view?usp=sharing"
            results.append({
                'original_filename': file.filename,
                'converted_filename': jpeg_filename,
                'drive_file_id': drive_file_id,
                'drive_file_link': drive_file_link
            })
        except Exception as e:
            results.append({
                'original_filename': file.filename,
                'error': str(e)
            })
    return jsonify({
        'message': 'Conversion and upload complete.',
        'results': results
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
