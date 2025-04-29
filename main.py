from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database configuration
DATABASE_CONFIG = {
    "host": "localhost",
    "user": "SeriousForge",
    "password": "1411Stud3nt!",
    "database": "TableDash"
}

def database_connect():
    return mysql.connector.connect(**DATABASE_CONFIG)

@app.route('/')
def splash():
    # Shows splash for 3 seconds, then redirects
    return render_template('splash.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = database_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user WHERE User_Email = %s AND User_Password = %s", (email, password))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            session['user'] = email
            flash('Successfully logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', email=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)