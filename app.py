from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from zeroconf import Zeroconf, ServiceInfo  # Added for mDNS
import socket  # Added for mDNS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///staff.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

# mDNS Setup
zeroconf = Zeroconf()
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
service_info = ServiceInfo(
    "_http._tcp.local.",
    "HospitalServer._http._tcp.local.",
    addresses=[socket.inet_aton(local_ip)],
    port=5000,
    properties={},
)
zeroconf.register_service(service_info)
print(f"Server advertising as HospitalServer._http._tcp.local. at {local_ip}:5000")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    rfid = db.Column(db.BigInteger, unique=True)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    rfid = db.Column(db.BigInteger, unique=True)
    doctor_authorization = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

### Routes (unchanged unless noted):
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        rfid = request.form.get('rfid')
        if rfid and int(rfid) == 3821713683:
            session['admin'] = True
            flash('Admin login successful')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin RFID')
    return render_template('admin_login.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('admin', None)
    session.pop('user_id', None)
    flash('You have been logged out')
    return redirect(url_for('admin_login'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin'):
        flash('Access denied')
        return redirect(url_for('admin_login'))
    staff = User.query.all()
    return render_template('admin_dashboard.html', staff=staff)

@app.route('/add_staff', methods=['POST'])
def add_staff():
    full_name = request.form['full_name']
    email = request.form['email']
    phone = request.form['phone']
    role = request.form['role']
    rfid = request.form['rfid']
    new_staff = User(full_name=full_name, email=email, phone=phone, role=role, rfid=rfid)
    db.session.add(new_staff)
    db.session.commit()
    flash('Staff added successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/remove_staff/<int:user_id>', methods=['POST'])
def remove_staff(user_id):
    if not session.get('admin'):
        flash('Access denied')
        return redirect(url_for('admin_login'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'Staff {user.full_name} removed successfully')
    return redirect(url_for('admin_dashboard'))

@app.route('/', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        rfid = request.form['rfid']
        staff_member = User.query.filter_by(rfid=rfid).first()
        if staff_member and staff_member.role != 'admin':
            session['user_id'] = staff_member.id
            session['role'] = staff_member.role
            if staff_member.role == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            elif staff_member.role == 'nurse':
                return redirect(url_for('nurse_dashboard'))
            elif staff_member.role == 'pharmacist':
                return redirect(url_for('pharmacist_dashboard'))
            elif staff_member.role == 'receptionist':
                return redirect(url_for('receptionist_dashboard'))
            else:
                flash('Access Denied: Unauthorized role', 'error')
                return redirect(url_for('staff_login'))
        else:
            flash('Invalid RFID or access restricted for Admin', 'error')
            return redirect(url_for('staff_login'))
    return render_template('login.html')

@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'role' not in session or session['role'] != 'doctor':
        flash('Unauthorized access', 'error')
        return redirect(url_for('staff_login'))
    return render_template('doctor_dashboard.html')

@app.route('/nurse_dashboard')
def nurse_dashboard():
    return render_template('nurse_dashboard.html')

@app.route('/pharmacist_dashboard')
def pharmacist_dashboard():
    return render_template('pharmacist_dashboard.html')

@app.route('/receptionist_dashboard')
def receptionist_dashboard():
    return render_template('receptionist_dashboard.html')

@app.route('/patients', methods=['GET'])
def patients():
    if session.get('admin') and not any(patient.doctor_authorization for patient in Patient.query.all()):
        flash('You do not have permission to view patient data')
        return redirect(url_for('admin_dashboard'))
    patients = Patient.query.all()
    return render_template('patients.html', patients=patients)

@app.route('/authorize_patient/<int:patient_id>', methods=['POST'])
def authorize_patient(patient_id):
    if not session.get('admin'):
        flash('You do not have permission to authorize patients')
        return redirect(url_for('admin_dashboard'))
    patient = Patient.query.get_or_404(patient_id)
    patient.doctor_authorization = True
    db.session.commit()
    flash(f'Patient {patient.name} authorized for admin access')
    return redirect(url_for('patients'))

@app.route('/rfid_scan', methods=['POST'])
def rfid_scan_http():
    rfid = request.form.get('rfid')
    if rfid:
        socketio.emit('rfid_response', {'rfid': rfid}, namespace='/')
        return jsonify({"status": "success", "rfid": rfid})
    return jsonify({"status": "error", "message": "Invalid RFID"}), 400

@socketio.on('rfid_scan')
def handle_rfid_scan(data):
    rfid = data.get('rfid')
    if rfid:
        emit('rfid_response', {'rfid': rfid}, broadcast=False)
    else:
        emit('rfid_response', {'error': 'Invalid RFID'}, broadcast=False)

@app.route('/register_patient', methods=['POST'])
def register_patient():
    if 'role' not in session or session['role'] != 'receptionist':
        flash('Unauthorized access', 'error')
        return redirect(url_for('staff_login'))
    
    try:
        full_name = request.form['full_name'].strip()
        dob = request.form['dob'].strip()
        gender = request.form['gender'].strip()
        phone = request.form['phone'].strip()
        address = request.form['address'].strip()
        rfid = int(request.form['rfid'])

        # Validate all fields are non-empty
        if not all([full_name, dob, gender, phone, address]):
            flash('All fields are required!', 'error')
            return redirect(url_for('receptionist_dashboard'))

        existing_patient = Patient.query.filter_by(rfid=rfid).first()
        if existing_patient:
            flash('Patient with this RFID already exists!', 'error')
            return redirect(url_for('receptionist_dashboard'))

        new_patient = Patient(
            name=full_name,
            dob=dob,
            gender=gender,
            phone=phone,
            address=address,
            rfid=rfid
        )
        db.session.add(new_patient)
        db.session.commit()

        flash('Patient registered successfully!', 'success')
    except ValueError:
        flash('Invalid RFID format!', 'error')
    except KeyError as e:
        flash(f'Missing field: {e.args[0]}', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('receptionist_dashboard'))

if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    finally:
        zeroconf.unregister_service(service_info)  # Cleanup mDNS on shutdown
        zeroconf.close()