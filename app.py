from flask import Flask, request, jsonify
import os
import tempfile
import requests
from PIL import Image
import re
import logging

# ==============================
# 🔑 วาง API Key ตรงนี้เลย (สำหรับใช้ส่วนตัว)
# ==============================
TYHOON_API_KEY = "sk-OZIFoH2FrnRh4QpRSrkt6CLcbuZZ3Scl62DnDf53asOFQiQX"
TYHOON_API_URL = "https://api.typhoon-ocr.com/v1/recognize"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)  # รวมช่องว่างซ้ำ
    return text.strip()

def extract_fields(text):
    """
    ดึงข้อมูลจากข้อความ OCR โดยใช้ Regex
    รองรับหลายรูปแบบ เช่น ENG_NAME: ..., ชื่อ: ..., DOB: ... ฯลฯ
    """
    patterns = {
        'engName': r'(?:ENG_NAME|English Name|Name \(EN\)|Name[:：])\s*(.*?)(?=\n|TH_NAME|DOB|SEQ|$)',
        'thName': r'(?:TH_NAME|Thai Name|ชื่อ \(ไทย\)|ชื่อ[:：])\s*(.*?)(?=\n|ENG_NAME|DOB|SEQ|$)',
        'dob': r'(?:DOB|Date of Birth|วันเกิด|Birth Date[:：])\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})',
        'seq': r'(?:SEQ|Sequence|ลำดับ|No[\.：:])\s*(\w+)',
    }

    results = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
        results[key] = match.group(1).strip() if match else ""

    return results

def call_typhoon_ocr(image_path):
    """
    เรียก Typhoon OCR API ด้วยไฟล์รูปภาพ
    """
    with open(image_path, 'rb') as image_file:
        files = {'file': image_file}
        headers = {
            'Authorization': f'Bearer {TYHOON_API_KEY}'
        }
        try:
            response = requests.post(TYHOON_API_URL, headers=headers, files=files, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get('text', '')  # ✅ ตรงกับเอกสาร Typhoon OCR
        except requests.exceptions.RequestException as e:
            logger.error(f"Typhoon OCR API Error: {str(e)}")
            raise Exception(f"OCR API failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in request'}), 400

    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected files'}), 400

    extracted_data = []

    for file in files:
        if not allowed_file(file.filename):
            logger.warning(f"Invalid file type: {file.filename}")
            continue

        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
                file.save(tmp.name)

                # ✅ เรียก Typhoon OCR
                ocr_text = call_typhoon_ocr(tmp.name)
                cleaned_text = clean_text(ocr_text)
                logger.info(f"OCR Output ({file.filename}): {cleaned_text}")

                # ดึงฟิลด์ที่ต้องการ
                fields = extract_fields(cleaned_text)

                extracted_data.append({
                    'engName': fields.get('engName', ''),
                    'thName': fields.get('thName', ''),
                    'dob': fields.get('dob', ''),
                    'seq': fields.get('seq', ''),
                    'sourceFile': file.filename
                })

                # ลบไฟล์ชั่วคราว
                os.unlink(tmp.name)

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {str(e)}")
            continue

    return jsonify(extracted_data)

@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
