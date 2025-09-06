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
    """ลบช่องว่างซ้ำ + normalize"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def calculate_age(dob_str):
    """คำนวณอายุจาก DOB string"""
    try:
        dob = datetime.strptime(dob_str, '%d/%m/%Y')
        today = datetime.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    except Exception as e:
        logger.warning(f"Failed to parse DOB '{dob_str}': {e}")
        return None

def guess_prefix(name, age):
    """
    เดาคำนำหน้าจากชื่อและอายุ
    """
    if not name:
        return ""

    name_upper = name.upper()

    # ตรวจสอบคำนำหน้าภาษาอังกฤษ
    if "MR." in name_upper or "MR " in name_upper:
        return "นาย"
    if "MRS." in name_upper or "MRS " in name_upper:
        return "นาง"
    if "MISS" in name_upper:
        return "นางสาว"
    if "MS." in name_upper or "MS " in name_upper:
        return "นางสาว"

    # ถ้าไม่มี → ใช้การเดาจากอายุ
    if age is not None:
        if age >= 30:
            # เดาจากชื่อ — ถ้ามีคำว่า "BO", "MIN", "OO" → มักเป็นชาย
            if any(x in name_upper for x in ["BO", "MIN", "OO", "TIN", "HTAY"]):
                return "นาย"
            else:
                return "นาง"
        else:
            # อายุน้อย → ใช้ "นาย" หรือ "นางสาว"
            if any(x in name_upper for x in ["BO", "MIN", "OO", "TIN", "HTAY"]):
                return "นาย"
            else:
                return "นางสาว"

    # ถ้าเดาไม่ได้
    return ""

def extract_fields(text):
    """
    ดึงชื่อและ DOB จากข้อความ OCR — รองรับหลายรูปแบบ
    """
    if not text:
        return {"name": "", "dob": "", "age": None, "prefix": ""}

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    name = ""
    dob = ""

    # หาบรรทัดที่เป็น DOB
    for line in lines:
        if re.match(r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}$', line):
            dob = re.sub(r'[\.|-]', '/', line)  # แปลง . หรือ - เป็น /
            continue
        # ถ้าไม่ใช่ DOB → ถือว่าเป็นชื่อ
        if not name and line:  # เก็บบรรทัดแรกที่ไม่ใช่ DOB
            name = line

    # ถ้ายังไม่เจอ DOB → ลองดูบรรทัดสุดท้าย
    if not dob and len(lines) >= 2:
        last_line = lines[-1]
        if re.match(r'^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}$', last_line):
            dob = re.sub(r'[\.|-]', '/', last_line)
            name = lines[-2] if len(lines) > 1 else ""

    # คำนวณอายุ
    age = calculate_age(dob) if dob else None

    # เดาคำนำหน้า
    prefix = guess_prefix(name, age)

    return {
        'name': name,
        'dob': dob,
        'age': age,
        'prefix': prefix
    }

def create_thumbnail_base64(image_path, size=(60, 60)):
    """สร้าง thumbnail และแปลงเป็น base64"""
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
    """เรียก Tesseract OCR"""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='eng+tha')
        return text
    except Exception as e:
        logger.error(f"Tesseract OCR Error: {str(e)}")
        raise Exception(f"OCR failed: {str(e)}")

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
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

                    # สร้าง thumbnail
                    thumbnail_b64 = create_thumbnail_base64(tmp.name)

                    # OCR
                    ocr_text = call_tesseract_ocr(tmp.name)
                    cleaned_text = clean_text(ocr_text)
                    logger.info(f"OCR Output ({file.filename}): {cleaned_text}")

                    # ดึงข้อมูล
                    fields = extract_fields(cleaned_text)

                    extracted_data.append({
                        'name': fields.get('name', ''),
                        'prefix': fields.get('prefix', ''),
                        'dob': fields.get('dob', ''),
                        'age': fields.get('age', '—'),
                        'sourceFile': file.filename,
                        'thumbnail': thumbnail_b64
                    })

                    # ลบไฟล์ชั่วคราว
                    os.unlink(tmp.name)

            except Exception as e:
                logger.error(f"Error processing {file.filename}: {str(e)}")
                continue  # ข้ามไฟล์นี้ ไม่ให้ crash ทั้งระบบ

        return jsonify(extracted_data)

    except Exception as e:
        logger.error(f"Unexpected server error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/')
def index():
    return app.send_static_file('index.html')

# สร้างโฟลเดอร์ static ทุกครั้ง
os.makedirs('static', exist_ok=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)  # ← debug=False
