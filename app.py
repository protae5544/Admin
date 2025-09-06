from flask import Flask, render_template_string, request, jsonify
import os
import logging
import subprocess
import sys
from PIL import Image

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create uploads directory
os.makedirs('uploads', exist_ok=True)

# Global variable to store tesseract availability
TESSERACT_AVAILABLE = False
pytesseract = None

def check_tesseract():
    """Check if Tesseract is installed and import pytesseract"""
    global TESSERACT_AVAILABLE, pytesseract
    
    try:
        # First check if tesseract command exists
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"Tesseract found: {result.stdout.split()[1] if result.stdout else 'Unknown version'}")
            
            # Try to import pytesseract
            try:
                import pytesseract as pt
                pytesseract = pt
                
                # Test if we can get languages
                langs = pytesseract.get_languages()
                logger.info(f"Available languages: {langs}")
                
                TESSERACT_AVAILABLE = True
                logger.info("✅ Tesseract OCR is ready!")
                return True
                
            except Exception as e:
                logger.error(f"Error importing pytesseract: {e}")
                
        else:
            logger.error("Tesseract command failed")
            
    except FileNotFoundError:
        logger.error("Tesseract command not found")
    except subprocess.TimeoutExpired:
        logger.error("Tesseract command timeout")
    except Exception as e:
        logger.error(f"Error checking tesseract: {e}")
    
    logger.error("❌ Tesseract OCR is not available")
    return False

# Check tesseract on startup
check_tesseract()

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
        
        .status-banner {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: bold;
        }
        
        .status-error {
            background: rgba(239, 68, 68, 0.1);
            border: 2px solid #ef4444;
            color: #dc2626;
        }
        
        .status-success {
            background: rgba(34, 197, 94, 0.1);
            border: 2px solid #22c55e;
            color: #16a34a;
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
        
        .upload-area:hover:not(.disabled) {
            border-color: #5a67d8;
            background: rgba(102, 126, 234, 0.1);
            transform: translateY(-2px);
        }
        
        .upload-area.disabled {
            opacity: 0.5;
            cursor: not-allowed;
            border-color: #ccc;
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
        
        .upload-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .upload-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
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
        
        .system-info {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            color: #666;
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
        
        <div class="system-info">
            <strong>System Status:</strong><br>
            Python: {{ python_version }}<br>
            Tesseract: {{ tesseract_status }}
        </div>
        
        {% if not tesseract_available %}
        <div class="status-banner status-error">
            ⚠️ OCR ไม่พร้อมใช้งาน: ต้องติดตั้ง Tesseract OCR ในระบบ
        </div>
        {% else %}
        <div class="status-banner status-success">
            ✅ OCR พร้อมใช้งาน
        </div>
        {% endif %}
        
        <div class="upload-area {% if not tesseract_available %}disabled{% endif %}" id="uploadArea">
            <div class="upload-icon">📁</div>
            <div class="upload-text">
                {% if tesseract_available %}
                    วางไฟล์ภาพที่นี่ หรือ คลิกเพื่อเลือกไฟล์
                {% else %}
                    ฟีเจอร์ OCR ไม่พร้อมใช้งานขณะนี้
                {% endif %}
            </div>
            <input type="file" class="file-input" id="fileInput" accept="image/*" multiple {% if not tesseract_available %}disabled{% endif %}>
            <button class="upload-btn" onclick="selectFiles()" {% if not tesseract_available %}disabled{% endif %}>
                {% if tesseract_available %}เลือกไฟล์ภาพ{% else %}ไม่พร้อมใช้งาน{% endif %}
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
        const tesseractAvailable = {{ tesseract_available|tojson }};

        function selectFiles() {
            if (tesseractAvailable) {
                fileInput.click();
            }
        }

        if (tesseractAvailable) {
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
                handleFiles(e.dataTransfer.files);
            });

            fileInput.addEventListener('change', (e) => {
                handleFiles(e.target.files);
            });
        }

        function handleFiles(files) {
            if (!tesseractAvailable) {
                showError('OCR ไม่พร้อมใช้งาน');
                return;
            }
            
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
                    if (item.text && item.text.trim()) {
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
    return render_template_string(HTML_TEMPLATE, 
                                tesseract_available=TESSERACT_AVAILABLE,
                                python_version=sys.version.split()[0],
                                tesseract_status="Available" if TESSERACT_AVAILABLE else "Not installed")

@app.route('/status')
def status():
    """Detailed status endpoint"""
    try:
        tesseract_version = subprocess.run(['tesseract', '--version'], 
                                         capture_output=True, text=True, timeout=5)
        tesseract_info = tesseract_version.stdout if tesseract_version.returncode == 0 else "Not found"
    except:
        tesseract_info = "Command failed"
    
    status_info = {
        'status': 'running',
        'tesseract_available': TESSERACT_AVAILABLE,
        'python_version': sys.version,
        'tesseract_command_output': tesseract_info,
        'path': os.environ.get('PATH', ''),
        'cwd': os.getcwd()
    }
    
    return jsonify(status_info)

@app.route('/upload', methods=['POST'])
def upload_files():
    if not TESSERACT_AVAILABLE:
        return jsonify({
            'success': False, 
            'message': 'OCR ไม่พร้อมใช้งาน: Tesseract ไม่ได้ติดตั้งในระบบ'
        })
    
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
                    filename = file.filename
                    filepath = os.path.join('uploads', filename)
                    file.save(filepath)
                    
                    text = perform_ocr(filepath)
                    
                    results.append({
                        'filename': filename,
                        'success': True,
                        'text': text
                    })
                    
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
    if not TESSERACT_AVAILABLE or not pytesseract:
        raise Exception("Tesseract OCR ไม่พร้อมใช้งาน")
    
    try:
        image = Image.open(image_path)
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Try with different language combinations
        try:
            text = pytesseract.image_to_string(image, lang='tha+eng', config='--oem 3 --psm 6')
        except:
            try:
                text = pytesseract.image_to_string(image, lang='eng', config='--oem 3 --psm 6')
            except:
                text = pytesseract.image_to_string(image)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        raise Exception(f"การประมวลผลภาพผิดพลาด: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
