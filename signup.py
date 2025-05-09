from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "your_db_user",
    "password": "your_db_password",
    "database": "TableDash"
}

def database_connect():
    return mysql.connector.connect(**DATABASE_CONFIG)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm-password')
        user_type = request.form.get('user-type')

        # Check for empty fields
        if not email or not password or not confirm_password or not user_type:
            flash("All fields are required.", "error")
            return redirect(url_for('signup'))

        # Password confirmation check
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('signup'))

        try:
            conn = database_connect()
            cursor = conn.cursor()

            # Determine the next User_ID based on user_type
            if user_type == 'customer':
                cursor.execute("SELECT User_ID FROM user WHERE User_Type = 'customer' ORDER BY User_ID DESC LIMIT 1")
                result = cursor.fetchone()
                next_id = int(result[0][1:]) + 1 if result else 1
                user_id = f"C{next_id:04}"
            elif user_type == 'driver':
                cursor.execute("SELECT User_ID FROM user WHERE User_Type = 'driver' ORDER BY User_ID DESC LIMIT 1")
                result = cursor.fetchone()
                next_id = int(result[0][1:]) + 1 if result else 1
                user_id = f"D{next_id:04}"
            elif user_type == 'business':
                cursor.execute("SELECT User_ID FROM user WHERE User_Type = 'business' ORDER BY User_ID DESC LIMIT 1")
                result = cursor.fetchone()
                next_id = int(result[0][1:]) + 1 if result else 1
                user_id = f"R{next_id:04}"

            # Insert new user record (plaintext password)
            cursor.execute('''
                INSERT INTO user (User_ID, User_Email, User_Password, User_Name, User_Type)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, email, password, email.split('@')[0], user_type))

            conn.commit()
            flash("Account created successfully!", "success")
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f"An error occurred: {err}", "error")
        finally:
            cursor.close()
            conn.close()

    return render_template('signup.html')

if __name__ == '__main__':
    app.run(debug=True)