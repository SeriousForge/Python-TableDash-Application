from flask import Flask, request, render_template, redirect, url_for
import mysql.connector
from werkzeug.security import generate_password_hash

app = Flask(__name__)

def create_database_connection():
    # Replace with your actual database credentials
    return mysql.connector.connect(
        host="localhost",
        user="your_db_user",
        password="your_db_password",
        database="your_db_name"
    )

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        user_type = request.form['user-type']

        if password != confirm_password:
            return "Passwords do not match!", 400

        # You need to hash the password before storing it
        hashed_password = generate_password_hash(password, method='sha256')

        try:
            conn = create_database_connection()
            cursor = conn.cursor()

            # Insert user data into the user table
            cursor.execute('''
                INSERT INTO user (User_ID, User_Email, User_Password, User_Name, User_Type)
                VALUES (UUID(), %s, %s, %s, %s)
            ''', (email, hashed_password, email, user_type))
            
            user_id = cursor.lastrowid

            # If user is a customer, insert into the customer table
            if user_type == 'customer':
                cursor.execute('''
                    INSERT INTO customer (Customer_Fname, Customer_LName, Customer_Member, Customer_Phone_Number, User_ID)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (None, None, 0, None, user_id))

            # If user is a driver, insert into the driver table (add other fields as necessary)
            elif user_type == 'driver':
                cursor.execute('''
                    INSERT INTO driver (Driver_Name, Driver_Address, User_ID)
                    VALUES (%s, %s, %s)
                ''', (None, None, user_id))

            conn.commit()
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            return f"Error: {err}", 500
        finally:
            cursor.close()
            conn.close()
    
    return render_template('signup.html')


@app.route('/login')
def login():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)