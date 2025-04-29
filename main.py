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
        # SELECT both User_ID and User_Type!
        cursor.execute(
            "SELECT User_ID, User_Type FROM user WHERE User_Email = %s AND User_Password = %s",
            (email, password)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            user_id, user_type = result
            session['user'] = email
            session['user_type'] = user_type
            session['user_id'] = user_id
            if user_type == 'customer':
                return redirect(url_for('customer_dashboard'))
            elif user_type == 'driver':
                return redirect(url_for('driver_dashboard'))
            elif user_type == 'business':
                return redirect(url_for('business_dashboard'))
            else:
                flash('Unknown user type', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/customer_dashboard')
def customer_dashboard():
    if 'user' not in session or session.get('user_type') != 'customer':
        return redirect(url_for('login'))
    return render_template('customer_dashboard.html', email=session['user'])

@app.route('/driver_dashboard')
def driver_dashboard():
    if 'user' not in session or session.get('user_type') != 'driver':
        return redirect(url_for('login'))
    user_id = session.get('user_id')

    conn = database_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM driver WHERE User_ID = %s", (user_id,))
    driver_info = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('driver_dashboard.html', email=session['user'], driver=driver_info)

@app.route('/business_dashboard')
def business_dashboard():
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    return render_template('business_dashboard.html', email=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_type', None)
    session.pop('user_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)