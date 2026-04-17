import json
import random
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
import pyotp
import qrcode
import io
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base64 import b64encode, b64decode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import RadialGradiantColorMask
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
import numpy as np

from werkzeug.utils import secure_filename
from qrcode import make
import base64
from io import BytesIO
from cryptography.fernet import Fernet
from pymongo import MongoClient
import datetime
from PIL import Image, ImageDraw
import os
from werkzeug.utils import secure_filename
import uuid
import cv2
import re
import smtplib

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

def write_to_arduino_serial(data):
    if not serial:
        return "pyserial not installed"
    try:
        ports = serial.tools.list_ports.comports()
        arduino_port = None
        for port in ports:
            desc = str(port.description).upper()
            if "CH340" in desc or "ARDUINO" in desc or "SERIAL" in desc or "CP210" in desc:
                arduino_port = port.device
                break
        
        if not arduino_port and ports:
            arduino_port = ports[0].device
            
        if arduino_port:
            import time
            ser = serial.Serial(arduino_port, 115200, timeout=1)
            ser.setDTR(False) # avoid reset
            time.sleep(2.5) # Wait for bootloader to finish resetting
            ser.write((data + '\n').encode('utf-8'))
            ser.close()
            return f"Data sent via {arduino_port}"
        return "No COM port found"
    except Exception as e:
        return f"COM Error: {str(e)}"

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

try:
    # Use local MongoDB as remote was blocking IP
    MONGO_URI = "mongodb://localhost:27017"
    client = MongoClient(MONGO_URI)
    db = client["medTrace"]
    collection = db["qrcodedata"]
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

app.config['UPLOAD_FOLDER'] = './uploads'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

KEY_FILE = 'secret.key'
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'rb') as f:
        key = f.read()
else:
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
cipher = Fernet(key)

raw_key = base64.urlsafe_b64decode(key)
aes_key = raw_key[:32] # 256-bit key for AES-256

def encrypt_rfid(shipment_id):
    # Padding the string to 16 bytes block size
    data = shipment_id.encode('utf-8')
    data_padded = pad(data, 16)
    cipher_aes = AES.new(aes_key, AES.MODE_ECB)
    encrypted_bytes = cipher_aes.encrypt(data_padded)
    return encrypted_bytes.hex()  # Hex representation of the 16 bytes

def decrypt_rfid(hex_string):
    encrypted_bytes = bytes.fromhex(hex_string)
    cipher_aes = AES.new(aes_key, AES.MODE_ECB)
    decrypted_padded = cipher_aes.decrypt(encrypted_bytes)
    return unpad(decrypted_padded, 16).decode('utf-8')

def send_email(to_email, otp, order_message):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login('forprojectuseemail@gmail.com', 'dykt kvbb gwzl llhw')
        message = f"Subject: OTP Verification and Order Details\n\nYour OTP is: {otp}\n\nOrder Message: {order_message}"
        server.sendmail('forprojectuseemail@gmail.com', to_email, message)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")
        
def create_circular_gradient_qr(data, size=500, dot_size=10, start_color=(0, 0, 255), end_color=(255, 0, 0)):
    # Generate QR code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=1, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    qr_size = qr.get_matrix()
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    num_modules = len(qr_size)
    module_size = size / num_modules
    for y in range(num_modules):
        for x in range(num_modules):
            if qr_size[y][x]:
                ratio = (x + y) / (2 * num_modules)
                r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
                g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
                b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
                color = (r, g, b)
                
                # Calculate position and draw circle
                top_left = (x * module_size, y * module_size)
                bottom_right = ((x + 1) * module_size, (y + 1) * module_size)
                draw.ellipse([top_left, bottom_right], fill=color)
    
    return img

@app.route("/")
def home():
    return render_template("home.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    return render_template('login.html')

@app.route('/mlogin', methods=['GET', 'POST'])
def mlogin():
    return render_template('mlogin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    return render_template('signup.html')

@app.route('/mdashboard', methods=['GET', 'POST'])
def mdashboard():
    return render_template('mdashboard.html')

@app.route('/mship', methods=['GET', 'POST'])
def mship():
    # Pass shipments from DB to render actual data
    shipments = list(db["mshipments"].find({}, {"_id": 0}))
    return render_template('mship.html', shipments=shipments)

@app.route('/m_generate_rfid', methods=['POST'])
def m_generate_rfid():
    try:
        data = request.json
        drugs = data.get('drugs', [])
        destination = data.get('destination', 'Unknown')
        shipment_date = data.get('shipmentDate', 'Unknown')
        email = data.get('email', 'Unknown')

        import random
        import datetime
        import hashlib
        short_id = f"MSH{random.randint(10000, 99999)}" 
        
        # Original drug details payload
        shipment_data = {
            "shipment_id": short_id,
            "drugs": drugs,
            "destination": destination,
            "email": email,
            "shipmentDate": shipment_date
        }
        
        # 1. Encrypt all shipment data using AES (Fernet securely wraps AES with HMAC)
        json_data = json.dumps(shipment_data).encode('utf-8')
        full_encrypted_data = cipher.encrypt(json_data).decode('utf-8')
        
        # 2. Output is converted into a fixed-length 16-character string (Hashing/Truncation)
        rfid_16_char = hashlib.sha256(full_encrypted_data.encode('utf-8')).hexdigest()[:16].upper()
        
        if len(drugs) == 1:
            product_name = drugs[0].get('drugName', 'Unknown')
            quantity = drugs[0].get('units', 'Unknown')
            batch_number = drugs[0].get('batchNumber', 'Unknown')
        elif len(drugs) > 1:
            product_name = f"Multiple ({len(drugs)} items)"
            quantity = "Variable"
            batch_number = "Multiple"
        else:
            product_name = "None"
            quantity = "0"
            batch_number = "N/A"

        # 3. Store both original data (optional admin) and encrypted 16-char code as primary ref
        db_shipment = {
            "shipment_id": short_id,
            "rfid_code": rfid_16_char,
            "encrypted_data": full_encrypted_data,
            # Optional admin backup fields:
            "product": product_name,
            "quantity": quantity,
            "batchNumber": batch_number,
            "destination": destination,
            "status": "Pending",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        db["mshipments"].insert_one(db_shipment.copy())
            
        arduino_msg = write_to_arduino_serial(rfid_16_char)
            
        return jsonify({
            'success': True, 
            'rfid_code': rfid_16_char, 
            'shipment_id': short_id,
            'arduino': arduino_msg
        })
    except Exception as e:
        print("m_generate_rfid error:", e)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/write_rfid', methods=['POST'])
def write_rfid():
    try:
        data = request.json
        rfid_code = data.get('rfid_code')
        if not rfid_code:
            return jsonify({'success': False, 'error': 'No RFID code provided'})
        
        status = write_to_arduino_serial(rfid_code)
        return jsonify({'success': True, 'arduino': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/scan_rfid', methods=['POST'])
def scan_rfid():
    try:
        data = request.json
        rfid_code = data.get('rfid_code')
        
        # 1. Fetch the 16-character encrypted code & Match it with database
        shipment = db["mshipments"].find_one({"rfid_code": rfid_code}, {"_id": 0})
        
        if shipment:
            # 2. Decrypt the code (Using the stored AES payload)
            encrypted_data = shipment.get("encrypted_data")
            try:
                # Reverse encryption securely using Secret Key
                decrypted_bytes = cipher.decrypt(encrypted_data.encode('utf-8'))
                original_data = json.loads(decrypted_bytes.decode('utf-8'))
                
                # Display original drug details & Store order entry effectively
                db["mshipments"].update_one(
                    {"rfid_code": rfid_code}, 
                    {"$set": {"status": "Received"}}
                )
                original_data['status'] = 'Received'
                
                return jsonify({
                    'success': True,
                    'shipment': original_data,
                    'message': 'Shipment securely verified and marked Received. Stored in Pharmacy portal.'
                })
            except Exception as e:
                # Security feature: Validation failing
                return jsonify({'success': False, 'message': 'Invalid or Tampered Code'})
        else:
            return jsonify({'success': False, 'message': 'Invalid or Tampered Code'})
            
    except Exception as e:
        print(f"INVALID RFID SCAN ALERT: Tampered or unrecognized code scanned: {e}")
        return jsonify({'success': False, 'message': 'Invalid or Tampered Code'})

@app.route('/rfid_scanner', methods=['GET'])
def rfid_scanner():
    return render_template('rfid_scanner.html')

@app.route('/mprofile', methods=['GET', 'POST'])
def mprofile():
    return render_template('mprofile.html')

@app.route('/mformulation', methods=['GET', 'POST'])
def mformulation():
    return render_template('mformulation.html')

@app.route('/mnotification', methods=['GET', 'POST'])
def mnotification():
    return render_template('mnotification.html')

@app.route('/lslogin', methods=['GET', 'POST'])
def lslogin():
    return render_template('lslogin.html')

@app.route('/lsdashboard', methods=['GET', 'POST'])
def lsdashboard():
    return render_template('lsdashboard.html')

@app.route('/lsinventory', methods=['GET', 'POST'])
def lsinventory():
    inventory_items = list(db["lsinventory"].find({}, {"_id": 0}))
    return render_template('lsinventory.html', inventory=inventory_items)

@app.route('/scan_to_lsinventory', methods=['POST'])
def scan_to_lsinventory():
    try:
        data = request.json
        rfid_code = data.get('rfid_code')
        if not rfid_code:
             return jsonify({'success': False, 'error': 'No RFID code provided'})
             
        shipment = db["mshipments"].find_one({"rfid_code": rfid_code})
        if not shipment:
             return jsonify({'success': False, 'error': 'Invalid or unknown Block ID'})

        encrypted_data = shipment.get("encrypted_data")
        decrypted_bytes = cipher.decrypt(encrypted_data.encode('utf-8'))
        original_data = json.loads(decrypted_bytes.decode('utf-8'))

        drugs = original_data.get('drugs', [])
        # Legacy support
        if not drugs and original_data.get('product'):
            drugs = [{"drugName": original_data['product'], "units": original_data.get('quantity', '100'), "batchNumber": original_data.get('batchNumber', 'N/A')}]

        for drug in drugs:
            d_name = drug.get('drugName', 'Unknown')
            d_units = drug.get('units', '0')
            d_batch = drug.get('batchNumber', 'N/A')
            try:
                qty = int(d_units)
            except:
                qty = 0

            existing = db["lsinventory"].find_one({"name": d_name})
            if existing:
                db["lsinventory"].update_one(
                    {"name": d_name}, 
                    {"$inc": {"stock": qty}}
                )
            else:
                db["lsinventory"].insert_one({
                    "name": d_name,
                    "stock": qty,
                    "batch": d_batch,
                    "price": 10 + (len(d_name) * 2), # Dummy price metric for visual UI
                    "expiry": "Dec 2025"
                })
                
        return jsonify({'success': True, 'message': f'Successfully synced {len(drugs)} items.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/lsnotification', methods=['GET', 'POST'])
def lsnotification():
    return render_template('lsnotification.html')

@app.route('/lsorder', methods=['GET', 'POST'])
def lsorder():
    return render_template('lsorder.html')

@app.route('/lsprofile', methods=['GET', 'POST'])
def lsprofile():
    return render_template('lsprofile.html')

@app.route('/dlogin', methods=['GET', 'POST'])
def dlogin():
    return render_template('dlogin.html')

@app.route('/ddashboard', methods=['GET', 'POST'])
def ddashboard():
    return render_template('ddashboard.html')

@app.route('/dprofile', methods=['GET', 'POST'])
def dprofile():
    return render_template('dprofile.html')

@app.route('/dinventory', methods=['GET', 'POST'])
def dinventory():
    return render_template('dinventory.html')

@app.route('/dnotification', methods=['GET', 'POST'])
def dnotification():
    return render_template('dnotification.html')

@app.route('/dorder', methods=['GET', 'POST'])
def dorder():
    return render_template('dorder.html')

@app.route('/dship', methods=['GET', 'POST'])
def dship():
    try:
        shipments = list(db["qrcodedata"].find({}, {"_id": 0}))
        shipments.reverse()
    except:
        shipments = []
    return render_template('dship.html', shipments=shipments)

@app.route('/slogin', methods=['GET', 'POST'])
def slogin():
    return render_template('slogin.html')

@app.route('/sdashboard', methods=['GET', 'POST'])
def sdashboard():
    try:
        inventory = list(db["sinventory"].find({}, {"_id": 0}))
    except Exception:
        inventory = []
    return render_template('sdashboard.html', inventory=inventory)

@app.route('/add_inventory', methods=['POST'])
def add_inventory():
    try:
        data = request.json
        drugs = data.get('drugs', [])
        
        # Legacy single-drug payload support
        drug_name = data.get('drugName')
        if drug_name and not drugs:
            drugs = [{"drugName": drug_name, "units": 100}]

        for drug in drugs:
            d_name = drug.get('drugName')
            qty_str = drug.get('units', '100')
            try:
                qty = int(qty_str)
            except:
                qty = 100

            if not d_name:
                continue
                
            existing = db["sinventory"].find_one({"name": d_name})
            if existing:
                db["sinventory"].update_one(
                    {"name": d_name}, 
                    {"$inc": {"initialStock": qty, "currentStock": qty}}
                )
            else:
                db["sinventory"].insert_one({
                    "name": d_name,
                    "initialStock": qty,
                    "currentStock": qty,
                    "soldToday": 0
                })
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/record_sale', methods=['POST'])
def record_sale():
    try:
        data = request.json
        name = data.get('name')
        quantity = data.get('quantity')
        if not name or not quantity:
            return jsonify({'success': False, 'error': 'Missing data'})
            
        existing = db["sinventory"].find_one({"name": {"$regex": f"^{name}$", "$options": "i"}})
        if existing:
            db["sinventory"].update_one(
                {"_id": existing['_id']},
                {"$inc": {"currentStock": -quantity, "soldToday": quantity}}
            )
        else:
            db["sinventory"].insert_one({
                "name": name,
                "initialStock": quantity * 2,
                "currentStock": quantity,
                "soldToday": quantity
            })
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/sinventory', methods=['GET', 'POST'])
def sinventory():
    return render_template('sinventory.html')

@app.route('/map', methods=['GET', 'POST'])
def map():
    return render_template('map.html')

@app.route('/sprofile', methods=['GET', 'POST'])
def sprofile():
    return render_template('sprofile.html')

@app.route('/snotification', methods=['GET', 'POST'])
def snotification():
    return render_template('snotification.html')

@app.route('/shipment-form')
def shipment_form():
    return render_template('shipment-form.html')

@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    if request.method == 'POST':
        if request.is_json:
            data = request.json
            pharmacy_name = data.get('pharmacyName', 'Unknown')
            email = data.get('email', 'Unknown')
            drugs = data.get('drugs', [])
        else:
            pharmacy_name = request.form.get('pharmacyName', 'Unknown')
            email = request.form.get('email', 'Unknown')
            drugs = [{
                'drugName': request.form.get('drugName', 'Unknown'),
                'drugId': request.form.get('drugId', f"DRG-{random.randint(100, 999)}"),
                'units': request.form.get('serialno', '1')
            }]

        shipment_id = f"SHP-{random.randint(1000, 9999)}"

        db_shipment_data = {
            "shipment_id": shipment_id,
            "pharmacyName": pharmacy_name,
            "email": email,
            "drugs": drugs,
            "status": "In Transit",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if len(drugs) == 1:
            db_shipment_data["drugName"] = drugs[0]["drugName"]
            db_shipment_data["drugId"] = drugs[0]["drugId"]
            db_shipment_data["serialno"] = drugs[0]["units"]
        else:
            db_shipment_data["drugName"] = f"Multiple ({len(drugs)} items)"
            db_shipment_data["drugId"] = "Multiple"
            db_shipment_data["serialno"] = "N/A"

        qr_data = {
            "pharmacyName": pharmacy_name,
            "email": email,
            "drugs": drugs
        }

        try:
            db["qrcodedata"].insert_one(db_shipment_data.copy())
        except Exception as e:
            print("DB Error:", e)

        qr_data_string = json.dumps(qr_data)
        encrypted_qr_data = cipher.encrypt(qr_data_string.encode('utf-8')).decode('utf-8')
        qr = qrcode.make(encrypted_qr_data)
        
        img_io = BytesIO()
        qr.save(img_io, 'PNG')
        img_io.seek(0)

        qr_file_path = os.path.join('static', 'shipment_qr.png')
        with open(qr_file_path, 'wb') as f:
            f.write(img_io.getvalue())

        return jsonify({'qr_image': qr_file_path})
    
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['qr-upload']

    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        result = decode_qr(filepath)

        return jsonify({'qr_data': result})

    return jsonify({'error': 'No file uploaded'})


def decode_qr(image_path):
    img = cv2.imread(image_path)
    detector = cv2.QRCodeDetector()
    data, bbox, straight_qrcode = detector.detectAndDecode(img)

    if data:
        return data
    else:
        return 'No QR code found'

@app.route('/encrypt_qr', methods=['POST'])
def encrypt_qr():
    try:
        data = request.json
        json_str = json.dumps(data)
        encrypted_data = cipher.encrypt(json_str.encode('utf-8')).decode('utf-8')
        return jsonify({'success': True, 'encrypted': encrypted_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/decrypt_qr', methods=['POST'])
def decrypt_qr():
    try:
        data = request.json
        encrypted_str = data.get("encrypted", "")
        decrypted_bytes = cipher.decrypt(encrypted_str.encode('utf-8'))
        decrypted_data = json.loads(decrypted_bytes.decode('utf-8'))
        return jsonify({'success': True, 'decrypted': decrypted_data})
    except Exception as e:
        return jsonify({'success': False, 'error': "Invalid or corrupted QR data."}), 400



if __name__ == "__main__":
    
    app.run(debug=True)

