from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from datetime import date
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

DB_PATH = 'database.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT UNIQUE NOT NULL,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            course TEXT NOT NULL,
            course_level TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            address TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            posted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sitin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            purpose TEXT NOT NULL,
            lab TEXT NOT NULL,
            login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            logout_time DATETIME
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            purpose TEXT NOT NULL,
            lab TEXT NOT NULL,
            time_in TIME NOT NULL,
            date DATE NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)
    ''', ('admin', 'admin123'))

    conn.commit()
    conn.close()


# =============================================================
# STUDENT ROUTES
# =============================================================

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_number = request.form['id_number']
        password  = request.form['password']

        conn = get_db()

        admin = conn.execute(
            'SELECT * FROM admins WHERE username = ? AND password = ?',
            (id_number, password)
        ).fetchone()

        if admin:
            session['admin_id']   = admin['id']
            session['admin_user'] = admin['username']
            conn.close()
            return redirect(url_for('admin_dashboard'))

        student = conn.execute(
            'SELECT * FROM students WHERE id_number = ? AND password = ?',
            (id_number, password)
        ).fetchone()
        conn.close()

        if student:
            session['student_id']   = student['id_number']
            session['student_name'] = student['first_name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid ID number or password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        id_number       = request.form['id_number']
        last_name       = request.form['last_name']
        first_name      = request.form['first_name']
        middle_name     = request.form['middle_name']
        course          = request.form['course']
        course_level    = request.form['course_level']
        password        = request.form['password']
        repeat_password = request.form['repeat_password']
        email           = request.form['email']
        address         = request.form['address']

        if password != repeat_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))

        try:
            conn = get_db()
            conn.execute('''
                INSERT INTO students
                (id_number, last_name, first_name, middle_name, course, course_level, password, email, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id_number, last_name, first_name, middle_name, course, course_level, password, email, address))
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ID Number or Email already exists.', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    student = conn.execute(
        'SELECT * FROM students WHERE id_number = ?',
        (session['student_id'],)
    ).fetchone()

    # Only count completed (logged-out) sit-ins toward session deduction
    used_sessions = conn.execute(
        'SELECT COUNT(*) as count FROM sitin_records WHERE id_number = ? AND logout_time IS NOT NULL',
        (session['student_id'],)
    ).fetchone()['count']

    remaining = 30 - used_sessions

    announcements = conn.execute(
        'SELECT * FROM announcements ORDER BY posted_at DESC'
    ).fetchall()

    conn.close()

    return render_template('dashboard.html',
                           student=student,
                           announcements=announcements,
                           remaining=remaining)


@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    student = conn.execute(
        'SELECT * FROM students WHERE id_number = ?',
        (session['student_id'],)
    ).fetchone()

    photo_path = f"uploads/{session['student_id']}.png"
    has_photo  = os.path.exists(os.path.join('static', photo_path))

    if request.method == 'POST':
        last_name    = request.form['last_name']
        first_name   = request.form['first_name']
        middle_name  = request.form['middle_name']
        course_level = request.form['course_level']
        email        = request.form['email']
        course       = request.form['course']
        address      = request.form['address']

        conn.execute('''
            UPDATE students SET
                last_name = ?, first_name = ?, middle_name = ?,
                course_level = ?, email = ?, course = ?, address = ?
            WHERE id_number = ?
        ''', (last_name, first_name, middle_name, course_level, email, course, address, session['student_id']))
        conn.commit()
        conn.close()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('edit_profile'))

    conn.close()
    return render_template('edit_profile.html', student=student,
                           photo_path=photo_path, has_photo=has_photo)


@app.route('/upload-photo', methods=['POST'])
def upload_photo():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        filename = f"{session['student_id']}.png"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('Profile photo updated successfully!', 'success')
    else:
        flash('Invalid file. Please upload a JPG, PNG, or GIF.', 'error')
    return redirect(url_for('edit_profile'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/students')
def students():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('students.html', students=students)


# =============================================================
# RESERVATION ROUTES
# =============================================================

@app.route('/reservation', methods=['GET', 'POST'])
def reservation():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    student = conn.execute(
        'SELECT * FROM students WHERE id_number = ?',
        (session['student_id'],)
    ).fetchone()

    used_sessions = conn.execute(
        'SELECT COUNT(*) as count FROM sitin_records WHERE id_number = ? AND logout_time IS NOT NULL',
        (session['student_id'],)
    ).fetchone()['count']

    remaining = 30 - used_sessions

    if request.method == 'POST':
        purpose = request.form.get('purpose', '').strip()
        lab     = request.form.get('lab', '').strip()
        time_in = request.form.get('time_in', '').strip()
        date    = request.form.get('date', '').strip()

        if purpose and lab and time_in and date:
            if remaining <= 0:
                flash('You have no remaining sessions to reserve.', 'error')
            else:
                conn.execute('''
                    INSERT INTO reservations (id_number, purpose, lab, time_in, date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session['student_id'], purpose, lab, time_in, date))
                conn.commit()
                flash('Reservation submitted successfully! Please wait for admin approval.', 'success')
        else:
            flash('Please fill in all fields.', 'error')

        conn.close()
        return redirect(url_for('reservation'))

    reservations = conn.execute(
        'SELECT * FROM reservations WHERE id_number = ? ORDER BY created_at DESC',
        (session['student_id'],)
    ).fetchall()

    conn.close()
    return render_template('reservation.html',
                           student=student,
                           remaining=remaining,
                           reservations=reservations)


# =============================================================
# ADMIN ROUTES
# =============================================================

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    students       = conn.execute('SELECT * FROM students').fetchall()
    total_students = len(students)
    announcements  = conn.execute(
        'SELECT * FROM announcements ORDER BY posted_at DESC'
    ).fetchall()
    course_stats = [
        {"course": row["course"], "count": row["count"]}
        for row in conn.execute(
            'SELECT course, COUNT(*) as count FROM students GROUP BY course'
        ).fetchall()
    ]
    total_sitin   = conn.execute('SELECT COUNT(*) as c FROM sitin_records').fetchone()['c']
    current_sitin = conn.execute(
        'SELECT COUNT(*) as c FROM sitin_records WHERE logout_time IS NULL'
    ).fetchone()['c']
    conn.close()

    return render_template(
        'admin_dashboard.html',
        students=students,
        total_students=total_students,
        announcements=announcements,
        course_stats=course_stats,
        total_sitin=total_sitin,
        current_sitin=current_sitin,
        admin_user=session['admin_user']
    )


@app.route('/admin/announce', methods=['POST'])
def admin_announce():
    message = request.form['message']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO announcements (message, posted_at) VALUES (?, datetime('now'))", (message,))
    conn.commit()
    conn.close()

    flash("Announcement posted!", "success")
    return redirect('/admin/dashboard')


@app.route('/admin/delete-announcement/<int:ann_id>', methods=['POST'])
def delete_announcement(ann_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
    conn.commit()
    conn.close()
    flash('Announcement deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-student/<id_number>', methods=['POST'])
def delete_student(id_number):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM students WHERE id_number = ?', (id_number,))
    conn.commit()
    conn.close()
    flash(f'Student {id_number} deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin/get-student/<id_number>')
def get_student(id_number):
    if 'admin_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    conn = get_db()
    student = conn.execute(
        'SELECT * FROM students WHERE id_number = ?',
        (id_number,)
    ).fetchone()

    # Sessions are only deducted on logout, so count only completed sit-ins
    used_sessions = conn.execute(
        'SELECT COUNT(*) as c FROM sitin_records WHERE id_number = ? AND logout_time IS NOT NULL',
        (id_number,)
    ).fetchone()['c']

    remaining = 30 - used_sessions
    conn.close()

    if student:
        return jsonify({
            "success": True,
            "id_number": student['id_number'],
            "name": f"{student['first_name']} {student['last_name']}",
            "remaining": remaining
        })

    return jsonify({"success": False, "message": "Student not found"})


@app.route('/admin/sit-in', methods=['POST'])
def admin_sitin():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    id_number = request.form.get('id_number')
    purpose   = request.form.get('purpose')
    lab       = request.form.get('lab')

    if id_number and purpose and lab:
        conn = get_db()

        # Check if student already has an active (not logged out) sit-in
        existing = conn.execute(
            'SELECT id FROM sitin_records WHERE id_number = ? AND logout_time IS NULL',
            (id_number,)
        ).fetchone()

        if existing:
            conn.close()
            flash(f'Student {id_number} is already sitting in! Log them out first.', 'error')
            return redirect(url_for('admin_sitin_records'))

        conn.execute('''
            INSERT INTO sitin_records (id_number, purpose, lab)
            VALUES (?, ?, ?)
        ''', (id_number, purpose, lab))
        conn.commit()
        conn.close()
        flash(f'Student {id_number} successfully sat-in!', 'success')
    else:
        flash('Please complete all Sit-In fields.', 'error')

    return redirect(url_for('admin_sitin_records'))


# ── NEW: Admin Sit-in Records Page ──────────────────────────────────────────

@app.route('/admin/sitin-records')
def admin_sitin_records():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    today = date.today().isoformat()

    # Active sit-ins (not yet logged out) — join with student info
    active_records = conn.execute('''
        SELECT sr.id, sr.id_number, sr.purpose, sr.lab, sr.login_time,
               s.first_name, s.last_name, s.course, s.course_level
        FROM sitin_records sr
        JOIN students s ON sr.id_number = s.id_number
        WHERE sr.logout_time IS NULL
        ORDER BY sr.login_time ASC
    ''').fetchall()

    # Total sit-ins today (all, including logged out)
    total_sitin = conn.execute(
        "SELECT COUNT(*) as c FROM sitin_records WHERE DATE(login_time) = ?",
        (today,)
    ).fetchone()['c']

    # Total logged out today
    total_logout = conn.execute(
        "SELECT COUNT(*) as c FROM sitin_records WHERE DATE(logout_time) = ?",
        (today,)
    ).fetchone()['c']

    conn.close()

    return render_template(
        'admin_sitin_records.html',
        active_records=active_records,
        total_sitin=total_sitin,
        total_logout=total_logout,
        admin_user=session['admin_user']
    )


# ── NEW: Admin logs out a student from sit-in (deducts 1 session) ────────────

@app.route('/admin/sitin-logout/<int:record_id>', methods=['POST'])
def admin_sitin_logout(record_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    # Set logout_time — this is the moment the session gets "used"
    conn.execute('''
        UPDATE sitin_records
        SET logout_time = CURRENT_TIMESTAMP
        WHERE id = ? AND logout_time IS NULL
    ''', (record_id,))
    conn.commit()

    # Get student info for the flash message
    record = conn.execute(
        '''SELECT sr.id_number, s.first_name, s.last_name
           FROM sitin_records sr
           JOIN students s ON sr.id_number = s.id_number
           WHERE sr.id = ?''',
        (record_id,)
    ).fetchone()

    conn.close()

    if record:
        flash(
            f'{record["first_name"]} {record["last_name"]} ({record["id_number"]}) '
            f'has been logged out. 1 session deducted.',
            'success'
        )
    else:
        flash('Record not found or already logged out.', 'error')

    return redirect(url_for('admin_sitin_records'))


# ── ADMIN: View & manage reservations ────────────────────────────────────────

@app.route('/admin/reservations')
def admin_reservations():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    reservations = conn.execute('''
        SELECT r.*, s.first_name, s.last_name
        FROM reservations r
        JOIN students s ON r.id_number = s.id_number
        ORDER BY r.date ASC, r.time_in ASC
    ''').fetchall()
    conn.close()

    return render_template('admin_reservations.html',
                           reservations=reservations,
                           admin_user=session['admin_user'])


@app.route('/admin/reservation/approve/<int:res_id>', methods=['POST'])
def approve_reservation(res_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    res = conn.execute('SELECT * FROM reservations WHERE id = ?', (res_id,)).fetchone()

    conn.execute("UPDATE reservations SET status = 'Approved' WHERE id = ?", (res_id,))

    # 🔔 NOTIFICATION
    conn.execute('''
        INSERT INTO notifications (id_number, message)
        VALUES (?, ?)
    ''', (res['id_number'], "✅ Your reservation has been APPROVED"))

    conn.commit()
    conn.close()

    flash('Reservation approved.', 'success')
    return redirect(url_for('admin_reservations'))


@app.route('/admin/reservation/reject/<int:res_id>', methods=['POST'])
def reject_reservation(res_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    res = conn.execute('SELECT * FROM reservations WHERE id = ?', (res_id,)).fetchone()

    conn.execute("UPDATE reservations SET status = 'Rejected' WHERE id = ?", (res_id,))

    # 🔔 NOTIFICATION
    conn.execute('''
        INSERT INTO notifications (id_number, message)
        VALUES (?, ?)
    ''', (res['id_number'], "❌ Your reservation has been REJECTED"))

    conn.commit()
    conn.close()

    flash('Reservation rejected.', 'success')
    return redirect(url_for('admin_reservations'))


# ── NEW: Admin Students List ────────────────────────────────────────────────

@app.route('/admin/students')
def admin_students():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    students = conn.execute('SELECT * FROM students ORDER BY last_name, first_name').fetchall()
    total_students = len(students)
    conn.close()

    return render_template(
        'admin_students.html',
        students=students,
        total_students=total_students,
        admin_user=session['admin_user']
    )


# ── NEW: Admin Sit-in Reports ────────────────────────────────────────────────

@app.route('/admin/sitin-reports')
def admin_sitin_reports():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    
    # Get sit-in statistics
    total_sitin = conn.execute('SELECT COUNT(*) as c FROM sitin_records').fetchone()['c']
    total_completed = conn.execute(
        'SELECT COUNT(*) as c FROM sitin_records WHERE logout_time IS NOT NULL'
    ).fetchone()['c']
    
    # Get sit-in by purpose
    purpose_stats = conn.execute('''
        SELECT purpose, COUNT(*) as count 
        FROM sitin_records 
        GROUP BY purpose 
        ORDER BY count DESC
    ''').fetchall()
    
    # Get sit-in by lab
    lab_stats = conn.execute('''
        SELECT lab, COUNT(*) as count 
        FROM sitin_records 
        GROUP BY lab 
        ORDER BY count DESC
    ''').fetchall()
    
    conn.close()

    return render_template(
        'admin_sitin_reports.html',
        total_sitin=total_sitin,
        total_completed=total_completed,
        purpose_stats=purpose_stats,
        lab_stats=lab_stats,
        admin_user=session['admin_user']
    )


# ── NEW: Admin Feedback Reports ────────────────────────────────────────────────

@app.route('/admin/feedback-reports')
def admin_feedback_reports():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    
    # Get all feedback records with student info
    feedbacks = conn.execute('''
        SELECT sr.id, sr.id_number, sr.purpose, sr.lab, sr.login_time,
               sr.logout_time, sr.rating, sr.feedback,
               s.first_name, s.last_name, s.course
        FROM sitin_records sr
        JOIN students s ON sr.id_number = s.id_number
        WHERE sr.feedback IS NOT NULL
        ORDER BY sr.login_time DESC
    ''').fetchall()
    
    # Get average rating
    avg_rating = conn.execute('''
        SELECT AVG(rating) as avg_rating 
        FROM sitin_records 
        WHERE rating IS NOT NULL
    ''').fetchone()['avg_rating']
    
    total_feedbacks = len(feedbacks)
    
    conn.close()

    return render_template(
        'admin_feedback_reports.html',
        feedbacks=feedbacks,
        avg_rating=avg_rating,
        total_feedbacks=total_feedbacks,
        admin_user=session['admin_user']
    )


# ──────────────────────────────────────────────────────────────────────────────

@app.route('/history')
def history():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    records = conn.execute('''
        SELECT *
        FROM sitin_records
        WHERE id_number = ?
        ORDER BY login_time DESC
    ''', (session['student_id'],)).fetchall()

    conn.close()

    return render_template('history.html', records=records)

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    record_id = request.form.get('record_id')
    rating = request.form.get('rating')
    feedback = request.form.get('feedback', '').strip()

    if not record_id or not rating or not feedback:
        flash('Please complete the feedback form.', 'error')
        return redirect(url_for('history'))

    conn = get_db()

    # Make sure the sit-in record belongs to the logged-in student
    record = conn.execute('''
        SELECT * FROM sitin_records
        WHERE id = ? AND id_number = ?
    ''', (record_id, session['student_id'])).fetchone()

    if not record:
        conn.close()
        flash('Invalid sit-in record.', 'error')
        return redirect(url_for('history'))

    # Save feedback
    conn.execute('''
        UPDATE sitin_records
        SET rating = ?, feedback = ?
        WHERE id = ?
    ''', (rating, feedback, record_id))

    conn.commit()
    conn.close()

    flash('Feedback submitted successfully!', 'success')
    return redirect(url_for('history'))


@app.route('/admin/view-sitin-records')
def view_sitin_records():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    search_id = request.args.get('search_id', '')

    query = '''
        SELECT 
            sr.id,
            sr.id_number,
            sr.purpose,
            sr.lab,
            sr.login_time,
            sr.logout_time,
            s.first_name,
            s.last_name,
            s.course
        FROM sitin_records sr
        JOIN students s ON sr.id_number = s.id_number
    '''

    params = []

    if search_id:
        query += " WHERE sr.id_number LIKE ?"
        params.append(f"%{search_id}%")

    query += " ORDER BY sr.login_time DESC"

    records = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        'admin_view_sitin_records.html',
        records=records,
        admin_user=session['admin_user']
    )


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=1234, debug=True)