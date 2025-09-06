from flask import Flask, render_template_string, request, jsonify
import os
import logging
from PIL import Image
import pytesseract

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create uploads directory
os.makedirs('uploads', exist_ok=True)

# Configure Tesseract path (for different environments)
try:
    # Try to find tesseract
    import subprocess
    tesseract_path = subprocess.check_output(['which', 'tesseract']).decode().strip()
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    logger.info(f"Tesseract found at: {tesseract_path}")
except Exception as e:
    logger.warning(f"Could not find tesseract automatically: {e}")
    # Common paths for different systems
    possible_paths = [
        '/usr/bin/tesseract',
        '/usr/local/bin/tesseract',
        'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            logger.info(f"Tesseract set to: {path}")
            break

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR Image Upload</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            width: 100%;
            backdrop-filter: blur(10px);
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 2.5rem;
            font-weight: 300;
        }
        
        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            transition: all 0.3s ease;
            margin-bottom: 20px;
            background: rgba(102, 126, 234, 0.05);
        }
        
        .upload-area:hover {
            border-color: #5a67d8;
            background: rgba(102, 126, 234, 0.1);
            transform: translateY(-2px);
        }
        
        .upload-area.dragover {
            border-color: #4c51bf;
            background: rgba(102, 126, 234, 0.15);
            transform: scale(1.02);
        }
        
        .upload-icon {
            font-size: 3rem;
            color: #667eea;
            margin-bottom: 15px;
        }
        
        .upload-text {
            font-size: 1.2rem;
            color: #666;
            margin-bottom: 15px;
        }
        
        .file-input {
            display: none;
        }
        
        .upload-btn {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 10px;
        }
        
        .upload-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .result {
            margin-top: 30px;
            padding: 20px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 10px;
            border-left: 5px solid #667eea;
        }
        
        .error {
            background: rgba(239, 68, 68, 0.1);
            border-left-color: #ef4444;
            color: #dc2626;
        }
        
        .success {
            background: rgba(34, 197, 94, 0.1);
            border-left-color: #22c55e;
            color: #16a34a;
        }
        
        .preview-container {
            margin: 20px 0;
            text-align: center;
        }
        
        .preview-image {
            max-width: 100%;
            max-height: 300px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        
        .ocr-result {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            color: #333;
            max-height: 200px;
            overflow-y: auto;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 20px;
                margin: 10px;
            }
            
            h1 {
                font-size: 2rem;
            }
            
            .upload-area {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📸 OCR Image Reader</h1>
        
        <div class="upload-area" id="uploadArea">
            <div class="upload-icon">📁</div>
            <div class="upload-text">วางไฟล์ภาพที่นี่ หรือ คลิกเพื่อเลือกไฟล์</div>
            <input type="file" class="file-input" id="fileInput" accept="image/*" multiple>
            <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                เลือกไฟล์ภาพ
            </button>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>กำลังประมวลผลภาพ...</p>
        </div>
        
        <div id="results"></div>
    </div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const loading = document.getElementById('loading');
        const results = document.getElementById('results');

        // Drag and drop functionality
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            handleFiles(files);
        });

        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });

        function handleFiles(files) {
            if (files.length === 0) return;
            
            loading.style.display = 'block';
            results.innerHTML = '';
            
            const formData = new FormData();
            
            for (let file of files) {
                if (file.type.startsWith('image/')) {
                    formData.append('files', file);
                }
            }
            
            if (formData.get('files')) {
                uploadFiles(formData);
            } else {
                showError('กรุณาเลือกไฟล์ภาพที่ถูกต้อง');
                loading.style.display = 'none';
            }
        }

        async function uploadFiles(formData) {
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                loading.style.display = 'none';
                
                if (result.success) {
                    showResults(result.data);
                } else {
                    showError(result.message || 'เกิดข้อผิดพลาดในการประมวลผล');
                }
            } catch (error) {
                loading.style.display = 'none';
                showError('เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + error.message);
            }
        }

        function showResults(data) {
            let html = '<div class="result success">';
            html += '<h3>✅ ผลลัพธ์การอ่านข้อความจากภาพ</h3>';
            
            data.forEach((item, index) => {
                html += '<div class="preview-container">';
                html += `<h4>📄 ไฟล์: ${item.filename}</h4>`;
                if (item.success) {
                    if (item.text.trim()) {
                        html += '<div class="ocr-result">' + escapeHtml(item.text) + '</div>';
                    } else {
                        html += '<div class="ocr-result">ไม่พบข้อความในภาพนี้</div>';
                    }
                } else {
                    html += '<div class="error">❌ ' + escapeHtml(item.error) + '</div>';
                }
                html += '</div>';
            });
            
            html += '</div>';
            results.innerHTML = html;
        }

        function showError(message) {
            results.innerHTML = `<div class="result error">
                <h3>❌ เกิดข้อผิดพลาด</h3>
                <p>${escapeHtml(message)}</p>
            </div>`;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': 'ไม่พบไฟล์ที่อัปโหลด'})
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'success': False, 'message': 'ไม่ได้เลือกไฟล์'})
        
        results = []
        
        for file in files:
            if file and file.filename:
                try:
                    # Save uploaded file
                    filename = file.filename
                    filepath = os.path.join('uploads', filename)
                    file.save(filepath)
                    
                    # Process OCR
                    text = perform_ocr(filepath)
                    
                    results.append({
                        'filename': filename,
                        'success': True,
                        'text': text
                    })
                    
                    # Clean up
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        
                except Exception as e:
                    logger.error(f"Error processing {file.filename}: {e}")
                    results.append({
                        'filename': file.filename,
                        'success': False,
                        'error': str(e)
                    })
        
        return jsonify({'success': True, 'data': results})
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'success': False, 'message': f'เกิดข้อผิดพลาด: {str(e)}'})

def perform_ocr(image_path):
    """Perform OCR on image file"""
    try:
        # Test if Tesseract is available
        test_result = pytesseract.get_tesseract_version()
        logger.info(f"Tesseract version: {test_result}")
        
        # Open and process image
        image = Image.open(image_path)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Perform OCR with Thai and English language support
        text = pytesseract.image_to_string(
            image, 
            lang='tha+eng',  # Support both Thai and English
            config='--oem 3 --psm 6'  # Use LSTM OCR Engine with uniform text block
        )
        
        return text.strip()
        
    except pytesseract.TesseractNotFoundError as e:
        logger.error(f"Tesseract OCR Error: {e}")
        raise Exception(f"OCR failed: {str(e)}")
    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        raise Exception(f"การประมวลผลภาพผิดพลาด: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
