from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, hashlib, os

app = Flask(__name__)
app.secret_key = 'elearn_secret_2024'
DB = 'elearn.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'student'
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                author_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                order_num INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, course_id)
            );
        ''')
        # Create default admin
        pw = hashlib.sha256('admin123'.encode()).hexdigest()
        try:
            db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ('admin', pw, 'teacher'))
            db.commit()
        except:
            pass
        # Sample data
        try:
            db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ('student1', hashlib.sha256('student123'.encode()).hexdigest(), 'student'))
            cid = db.execute("INSERT INTO courses (title, description, author_id) VALUES (?, ?, ?)",
                ('Python для початківців', 'Курс з основ програмування на Python. Починаємо з нуля!', 1)).lastrowid
            db.execute("INSERT INTO lessons (course_id, title, content, order_num) VALUES (?, ?, ?, ?)",
                (cid, 'Вступ до Python', '# Що таке Python?\n\nPython — це мова програмування загального призначення...\n\nПервий код:\n```python\nprint("Привіт, світ!")\n```\n\nЦей рядок виводить текст на екран. Просто, правда?', 1))
            db.execute("INSERT INTO lessons (course_id, title, content, order_num) VALUES (?, ?, ?, ?)",
                (cid, 'Змінні та типи даних', '# Змінні\n\nЗмінна — це контейнер для зберігання даних.\n\n```python\nname = "Іван"\nage = 20\ngrade = 4.5\n```\n\nПython автоматично визначає тип даних!', 2))
            cid2 = db.execute("INSERT INTO courses (title, description, author_id) VALUES (?, ?, ?)",
                ('Веб-розробка: HTML та CSS', 'Створюйте красиві сайти з нуля. Практичний курс.', 1)).lastrowid
            db.execute("INSERT INTO lessons (course_id, title, content, order_num) VALUES (?, ?, ?, ?)",
                (cid2, 'Основи HTML', '# HTML — скелет сайту\n\nHTML (HyperText Markup Language) — це мова розмітки.\n\n```html\n<!DOCTYPE html>\n<html>\n  <head><title>Мій сайт</title></head>\n  <body>\n    <h1>Привіт!</h1>\n    <p>Це абзац тексту.</p>\n  </body>\n</html>\n```', 1))
            db.commit()
        except:
            pass

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def current_user():
    if 'user_id' not in session: return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()

# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()
    courses = db.execute('''
        SELECT c.*, u.username as author_name,
               COUNT(DISTINCT l.id) as lesson_count,
               COUNT(DISTINCT e.id) as student_count
        FROM courses c
        LEFT JOIN users u ON c.author_id = u.id
        LEFT JOIN lessons l ON l.course_id = c.id
        LEFT JOIN enrollments e ON e.course_id = c.id
        GROUP BY c.id ORDER BY c.created_at DESC
    ''').fetchall()
    user = current_user()
    enrolled = []
    if user and user['role'] == 'student':
        rows = db.execute("SELECT course_id FROM enrollments WHERE student_id=?", (user['id'],)).fetchall()
        enrolled = [r['course_id'] for r in rows]
    return render_template('index.html', courses=courses, user=user, enrolled=enrolled)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        u, p = request.form['username'].strip(), request.form['password']
        if not u or not p:
            flash('Заповніть усі поля', 'danger')
        else:
            try:
                get_db().execute("INSERT INTO users (username, password) VALUES (?,?)", (u, hash_pw(p)))
                get_db().commit()
                flash('Акаунт створено! Увійдіть.', 'success')
                return redirect(url_for('login'))
            except:
                flash('Логін вже зайнятий', 'danger')
    return render_template('register.html', user=None)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['username'].strip(), request.form['password']
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (u, hash_pw(p))).fetchone()
        if user:
            session['user_id'] = user['id']
            flash(f'Ласкаво просимо, {user["username"]}!', 'success')
            return redirect(url_for('index'))
        flash('Невірний логін або пароль', 'danger')
    return render_template('login.html', user=None)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/course/<int:cid>')
def course(cid):
    db = get_db()
    c = db.execute('SELECT c.*, u.username as author_name FROM courses c LEFT JOIN users u ON c.author_id=u.id WHERE c.id=?', (cid,)).fetchone()
    if not c: return redirect(url_for('index'))
    lessons = db.execute('SELECT * FROM lessons WHERE course_id=? ORDER BY order_num', (cid,)).fetchall()
    user = current_user()
    enrolled = False
    if user:
        enrolled = db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?", (user['id'], cid)).fetchone() is not None
    return render_template('course.html', course=c, lessons=lessons, user=user, enrolled=enrolled)

@app.route('/enroll/<int:cid>')
def enroll(cid):
    user = current_user()
    if not user: return redirect(url_for('login'))
    if user['role'] != 'student':
        flash('Записатись можуть лише студенти', 'warning')
        return redirect(url_for('course', cid=cid))
    try:
        db = get_db()
        db.execute("INSERT INTO enrollments (student_id, course_id) VALUES (?,?)", (user['id'], cid))
        db.commit()
        flash('Ви успішно записались на курс!', 'success')
    except:
        flash('Ви вже записані на цей курс', 'info')
    return redirect(url_for('course', cid=cid))

@app.route('/lesson/<int:lid>')
def lesson(lid):
    db = get_db()
    les = db.execute('SELECT * FROM lessons WHERE id=?', (lid,)).fetchone()
    if not les: return redirect(url_for('index'))
    c = db.execute('SELECT * FROM courses WHERE id=?', (les['course_id'],)).fetchone()
    user = current_user()
    if user and user['role'] == 'student':
        enrolled = db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?", (user['id'], c['id'])).fetchone()
        if not enrolled:
            flash('Спочатку запишіться на курс', 'warning')
            return redirect(url_for('course', cid=c['id']))
    all_lessons = db.execute('SELECT * FROM lessons WHERE course_id=? ORDER BY order_num', (c['id'],)).fetchall()
    return render_template('lesson.html', lesson=les, course=c, lessons=all_lessons, user=user)

@app.route('/teacher', methods=['GET','POST'])
def teacher():
    user = current_user()
    if not user or user['role'] != 'teacher':
        flash('Доступ лише для викладачів', 'danger')
        return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_course':
            title = request.form['title'].strip()
            desc = request.form['description'].strip()
            if title:
                db.execute("INSERT INTO courses (title, description, author_id) VALUES (?,?,?)", (title, desc, user['id']))
                db.commit()
                flash('Курс створено!', 'success')
        elif action == 'add_lesson':
            cid = request.form['course_id']
            ltitle = request.form['lesson_title'].strip()
            content = request.form['content'].strip()
            if cid and ltitle and content:
                max_order = db.execute("SELECT MAX(order_num) FROM lessons WHERE course_id=?", (cid,)).fetchone()[0] or 0
                db.execute("INSERT INTO lessons (course_id, title, content, order_num) VALUES (?,?,?,?)", (cid, ltitle, content, max_order+1))
                db.commit()
                flash('Лекцію додано!', 'success')
        elif action == 'delete_course':
            cid = request.form['course_id']
            db.execute("DELETE FROM lessons WHERE course_id=?", (cid,))
            db.execute("DELETE FROM enrollments WHERE course_id=?", (cid,))
            db.execute("DELETE FROM courses WHERE id=? AND author_id=?", (cid, user['id']))
            db.commit()
            flash('Курс видалено', 'info')
        return redirect(url_for('teacher'))
    courses = db.execute('SELECT c.*, COUNT(DISTINCT l.id) as lesson_count, COUNT(DISTINCT e.id) as student_count FROM courses c LEFT JOIN lessons l ON l.course_id=c.id LEFT JOIN enrollments e ON e.course_id=c.id WHERE c.author_id=? GROUP BY c.id', (user['id'],)).fetchall()
    all_courses = db.execute('SELECT * FROM courses WHERE author_id=?', (user['id'],)).fetchall()
    return render_template('teacher.html', user=user, courses=courses, all_courses=all_courses)

@app.route('/profile')
def profile():
    user = current_user()
    if not user: return redirect(url_for('login'))
    db = get_db()
    enrollments = db.execute('''
        SELECT c.*, COUNT(l.id) as lesson_count
        FROM enrollments e JOIN courses c ON e.course_id=c.id
        LEFT JOIN lessons l ON l.course_id=c.id
        WHERE e.student_id=? GROUP BY c.id
    ''', (user['id'],)).fetchall()
    return render_template('profile.html', user=user, enrollments=enrollments)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
