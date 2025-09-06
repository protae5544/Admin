from flask import Flask, request, jsonify
import os
import tempfile
import pytesseract
from PIL import Image
import re
import logging
from datetime import datetime
import base64
from io import BytesIO

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

def call_tesseract_ocr(image_path):
    """
    ใช้ Tesseract OCR แทน Typhoon OCR
    """
    try:
        img = Image.open(image_path)
        # ใช้ทั้งภาษาไทยและอังกฤษ
        text = pytesseract.image_to_string(img, lang='eng+tha')
        return text
    except Exception as e:
        logger.error(f"Tesseract OCR Error: {str(e)}")
        raise Exception(f"OCR failed: {str(e)}")

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

                # ✅ เรียก Tesseract OCR แทน Typhoon OCR
                ocr_text = call_tesseract_ocr(tmp.name)
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

# สร้างโฟลเดอร์ static ทุกครั้ง
os.makedirs('static', exist_ok=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
