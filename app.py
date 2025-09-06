from flask import Flask, request, jsonify
import os
import tempfile
import requests
from PIL import Image
import re
import logging
from datetime import datetime
import base64
from io import BytesIO

# ==============================
# 🔑 Typhoon OCR API Key (สำหรับใช้ส่วนตัว)
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
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def calculate_age(dob_str):
    try:
        dob = datetime.strptime(dob_str, '%d/%m/%Y')
        today = datetime.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    except:
        return None

def extract_fields(text):
    patterns = {
        'engName': r'(?:ENG_NAME|English Name|Name \(EN\)|Name[:：])\s*((?:Mr\.|Mrs\.|Ms\.|Miss|Dr\.|Prof\.)?\s*[A-Za-z\s\.]+?)(?=\n|TH_NAME|DOB|$)',
        'thName': r'(?:TH_NAME|Thai Name|ชื่อ \(ไทย\)|ชื่อ[:：])\s*((?:นาย|นาง|นางสาว|ดญ\.|ดช\.|ดร\.|ศาสตราจารย์)?\s*[\u0E00-\u0E7F\s]+?)(?=\n|ENG_NAME|DOB|$)',
        'dob': r'(?:DOB|Date of Birth|วันเกิด|Birth Date[:：])\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})',
    }

    results = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
        results[key] = match.group(1).strip() if match else ""

    if results.get('dob'):
        dob_clean = re.sub(r'[\.|-]', '/', results['dob'])
        results['dob'] = dob_clean
        results['age'] = calculate_age(dob_clean)
    else:
        results['age'] = None

    return results

def create_thumbnail_base64(image_path, size=(60, 60)):
    try:
        img = Image.open(image_path)
        img.thumbnail(size)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error creating thumbnail: {e}")
        return ""

def call_typhoon_ocr(image_path):
    with open(image_path, 'rb') as image_file:
        files = {'file': image_file}
        headers = {
            'Authorization': f'Bearer {TYHOON_API_KEY}'
        }
        try:
            response = requests.post(TYHOON_API_URL, headers=headers, files=files, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get('text', '')
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
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
                file.save(tmp.name)

                thumbnail_b64 = create_thumbnail_base64(tmp.name)
                ocr_text = call_typhoon_ocr(tmp.name)
                cleaned_text = clean_text(ocr_text)
                logger.info(f"OCR Output ({file.filename}): {cleaned_text}")

                fields = extract_fields(cleaned_text)

                extracted_data.append({
                    'engName': fields.get('engName', ''),
                    'thName': fields.get('thName', ''),
                    'dob': fields.get('dob', ''),
                    'age': fields.get('age', '—'),
                    'sourceFile': file.filename,
                    'thumbnail': thumbnail_b64
                })

                os.unlink(tmp.name)

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {str(e)}")
            continue

    return jsonify(extracted_data)

@app.route('/')
def index():
    return app.send_static_file('index.html')

# ✅ สร้างโฟลเดอร์ static ทุกครั้งก่อนรัน app — สำคัญมากสำหรับ deploy!
os.makedirs('static', exist_ok=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
