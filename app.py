import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'helpdesk-secret-key-change-in-production'
DATABASE = 'helpdesk.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT DEFAULT 'Open',
            resolution TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

@app.before_request
def before_request():
    init_db()

@app.route('/')
def index():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        hashed = generate_password_hash(password)
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
                         (name, email, hashed))
            conn.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == 'admin@helpdesk.com' and password == 'Admin@123':
            session['admin'] = True
            flash('Admin logged in.', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    tickets = conn.execute(
        'SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('user_dashboard.html', tickets=tickets)

@app.route('/raise', methods=['GET', 'POST'])
def raise_ticket():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        priority = request.form['priority']
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M')
        conn = get_db()
        conn.execute(
            'INSERT INTO tickets (user_id, title, description, category, priority, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (session['user_id'], title, description, category, priority, created_at)
        )
        conn.commit()
        conn.close()
        flash('Ticket raised successfully.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('raise_ticket.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    conn = get_db()
    tickets = conn.execute('''
        SELECT t.*, u.name as user_name, u.email as user_email
        FROM tickets t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_dashboard.html', tickets=tickets)

@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
def ticket_detail(ticket_id):
    conn = get_db()
    ticket = conn.execute('''
        SELECT t.*, u.name as user_name, u.email as user_email
        FROM tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.id = ?
    ''', (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        flash('Ticket not found.', 'error')
        return redirect(url_for('index'))
    
    if not session.get('admin') and session.get('user_id') != ticket['user_id']:
        conn.close()
        flash('Access denied.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST' and session.get('admin'):
        status = request.form['status']
        resolution = request.form['resolution']
        conn.execute(
            'UPDATE tickets SET status = ?, resolution = ? WHERE id = ?',
            (status, resolution, ticket_id)
        )
        conn.commit()
        flash('Ticket updated.', 'success')
        ticket = conn.execute('''
            SELECT t.*, u.name as user_name, u.email as user_email
            FROM tickets t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = ?
        ''', (ticket_id,)).fetchone()

    conn.close()
    return render_template('ticket_detail.html', ticket=ticket)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
