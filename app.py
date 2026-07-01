from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash, make_response, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import os, csv, io, random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'ultimate_enterprise_key'
app.config['UPLOAD_FOLDER'] = 'uploads/'
os.makedirs('uploads', exist_ok=True)

db = SQLAlchemy(app)

SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = generate_password_hash("admin123")

class JobRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    required_skills = db.Column(db.String(500))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_role = db.Column(db.String(100))
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    education = db.Column(db.String(200))
    address = db.Column(db.String(300))
    skills = db.Column(db.String(200))
    experience = db.Column(db.String(200))
    bio = db.Column(db.String(500))
    resume_filename = db.Column(db.String(200)) 
    status = db.Column(db.String(50), default="Pending") 
    ats_score = db.Column(db.Integer, default=0)
    interview_type = db.Column(db.String(50), nullable=True)
    interview_date = db.Column(db.String(50), nullable=True) 
    interview_time = db.Column(db.String(50), nullable=True) 
    interview_location = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    if JobRole.query.count() == 0:
        db.session.add(JobRole(name="Software Developer", required_skills="python, java, c++, react, sql, javascript"))
        db.session.add(JobRole(name="HR Manager", required_skills="recruitment, communication, management, payroll"))
        db.session.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"TechCorp HR <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"⚠️ Email warning (Ignore if testing locally): {e}")
        return False

# --- FIXED OTP LOGIC ---
otp_storage = {}

@app.route('/api/send_otp', methods=['POST'])
def send_otp():
    email = request.json.get('email')
    otp = str(random.randint(100000, 999999))
    otp_storage[email] = otp
    print(f"\n🔑 [CRITICAL] OTP for {email} is: {otp}\n") 
    send_email(email, "Your Application OTP", f"<h3>Your OTP is: <b>{otp}</b></h3>")
    
    # Yahan otp frontend par bhejenge popup ke liye
    return jsonify({"success": True, "otp": otp})

@app.route('/api/verify_otp', methods=['POST'])
def verify_otp():
    data = request.json
    if otp_storage.get(data['email']) == data['otp']: 
        # Yahan sirf success True bhejenge, Error 500 nahi aayega ab
        return jsonify({"success": True})
    return jsonify({"success": False})

def calculate_ats(role_name, user_skills):
    role = JobRole.query.filter_by(name=role_name).first()
    if not role or not role.required_skills: return 0
    req_skills =[s.strip().lower() for s in role.required_skills.split(',')]
    u_skills =[s.strip().lower() for s in user_skills.split(',')]
    match_count = 0
    for rs in req_skills:
        if any(rs in us for us in u_skills) or any(us in rs for us in u_skills):
            match_count += 1
    score = int((match_count / len(req_skills)) * 100)
    return min(score, 100)

@app.route('/', methods=['GET', 'POST'])
def index():
    roles = JobRole.query.all()
    if request.method == 'POST':
        resume_file = request.files.get('resume')
        filename = None
        if resume_file and resume_file.filename != '':
            filename = secure_filename(resume_file.filename)
            resume_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        role = request.form.get('job_role', 'Software Developer')
        user_skills = request.form.get('skills', '')
        score = calculate_ats(role, user_skills)
        
        new_user = User(
            job_role=role, name=request.form.get('name', ''), email=request.form.get('email', ''),
            phone=request.form.get('phone', ''), education=request.form.get('education', ''),
            address=request.form.get('address', ''), skills=user_skills, experience=request.form.get('experience', ''),
            bio=request.form.get('bio', ''), resume_filename=filename, ats_score=score
        )
        db.session.add(new_user)
        db.session.commit()
        send_email(new_user.email, "Application Received", f"Hi {new_user.name}, your App ID is #{new_user.id}.")
        return redirect(url_for('thanks', app_id=new_user.id))
    return render_template('index.html', roles=roles)

@app.route('/thanks')
def thanks():
    app_id = request.args.get('app_id', 'Unknown')
    return render_template('thanks.html', app_id=app_id)

@app.route('/api/track', methods=['POST'])
def track_status():
    data = request.get_json()
    user = User.query.filter_by(id=data.get('app_id'), email=data.get('email')).first()
    if user:
        resp = {"success": True, "name": user.name, "status": user.status, "role": user.job_role}
        if user.status == 'Shortlisted':
            resp.update({
                "date": user.interview_date, "time": user.interview_time,
                "i_type": user.interview_type, "loc": user.interview_location
            })
        return jsonify(resp)
    return jsonify({"success": False, "message": "Invalid Details!"})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, request.form.get('password')):
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        flash('Invalid Credentials!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin():
    users = User.query.order_by(User.id.desc()).all()
    roles = JobRole.query.all()
    stats = {
        'total': len(users),
        'pending': User.query.filter_by(status='Pending').count(),
        'shortlisted': User.query.filter_by(status='Shortlisted').count(),
        'rejected': User.query.filter_by(status='Rejected').count()
    }
    return render_template('admin.html', users=users, stats=stats, roles=roles)

@app.route('/add_role', methods=['POST'])
@login_required
def add_role():
    name = request.form.get('role_name')
    skills = request.form.get('required_skills')
    if name and skills:
        db.session.add(JobRole(name=name, required_skills=skills))
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete_role/<int:id>', methods=['POST'])
@login_required
def delete_role(id):
    role = JobRole.query.get(id)
    if role:
        db.session.delete(role)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/update_status/<int:id>', methods=['POST'])
@login_required
def update_status(id):
    user = User.query.get_or_404(id)
    new_status = request.form.get('status')
    user.status = new_status
    if new_status == 'Shortlisted':
        user.interview_type = request.form.get('i_type')
        user.interview_date = request.form.get('i_date')
        user.interview_time = request.form.get('i_time')
        user.interview_location = request.form.get('i_loc')
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/download_resume/<filename>')
@login_required
def download_resume(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
