import mysql.connector

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "SeriousForge",
    "password": "1411Stud3nt!",
    "database": "TableDash"
}

def test_login(email, password):
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()
        # Use backticks if your table is a reserved word; here assumed "users"
        cursor.execute("""
            SELECT * FROM user
            WHERE User_Email = %s AND User_Password = %s
        """, (email, password))
        row = cursor.fetchone()
        if row:
            print(f"Login Success! Welcome, {row[3]}")
        else:
            print("Login Failed: Incorrect email or password.")
    except mysql.connector.Error as err:
        print("Database error:", err)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

# Test with one of your existing users
test_login("harper.smith@email.com", "defaultpassword")