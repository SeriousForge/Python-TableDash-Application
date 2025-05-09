from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import mysql.connector
import random
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, date
from math import radians, sin, cos, sqrt, atan2
from collections import defaultdict
from urllib.parse import urlparse
import os

url = urlparse(os.environ.get('JAWSDB_URL'))

DATABASE_CONFIG = {
    "host": url.hostname,
    "user": url.username,
    "password": url.password,
    "database": url.path[1:],  # Omit the leading '/'
    "port": url.port or 3306
}

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def database_connect():
    return mysql.connector.connect(**DATABASE_CONFIG)
def create_orders_table():
    conn = database_connect()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS confirmed_orders (
            order_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50),
            item VARCHAR(100),
            quantity INT,
            price DECIMAL(10,2),
            tip DECIMAL(10,2),
            total DECIMAL(10,2),
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

create_orders_table()
def clean_past_availabilities_for_driver(user_id):
    today = date.today().isoformat()
    try:
        conn = database_connect()
        cursor = conn.cursor()
        # Delete only entries for the current driver in session
        cursor.execute("""
            DELETE FROM availability
            WHERE Date < %s AND User_ID = %s
        """, (today, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Past availabilities cleaned up for driver {user_id}.")
    except Exception as e:
        print("Failed to clean past availabilities:", e)


def schedule_cleanup_for_driver(user_id):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=lambda: clean_past_availabilities_for_driver(user_id), trigger='cron', day_of_week='sun', hour=0)
    scheduler.start()

@app.route('/')
def splash():
    return render_template('splash.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        user_type = request.form['user-type']

        # Common Data Validation
        if not email or not password or not confirm_password or not user_type:
            flash("All fields are required.", "error")
            return redirect(url_for('signup'))

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('signup'))

        # Retrieve shared address fields
        street_address = request.form['street-address']
        suite_number = request.form['suite-number']
        gate_number = request.form['gate-number']
        city = request.form['city']
        state = request.form['state']
        zip_code = request.form['zip-code']

        try:
            conn = database_connect()
            cursor = conn.cursor()

            # Generate User_ID
            if user_type == 'customer':
                cursor.execute("SELECT User_ID FROM user WHERE User_Type = 'customer' ORDER BY User_ID DESC LIMIT 1")
                result = cursor.fetchone()
                next_id = int(result[0][1:]) + 1 if result else 1
                user_id = f"C{next_id:04}"
                
                # Retrieve Customer-specific fields
                customer_fname = request.form['customer-fname']
                customer_lname = request.form['customer-lname']
                customer_phone = request.form['customer-phone']
                
                # Insert into user table
                cursor.execute('''
                    INSERT INTO user (User_ID, User_Email, User_Password, User_Name, User_Type)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, email, password, email.split('@')[0], user_type))
                
                # Insert into customer table
                cursor.execute('''
                    INSERT INTO customer (Customer_Fname, Customer_LName, Customer_Member, Customer_Phone_Number, User_ID)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (customer_fname, customer_lname, 0, customer_phone, user_id))

            elif user_type == 'driver':
                cursor.execute("SELECT User_ID FROM user WHERE User_Type = 'driver' ORDER BY User_ID DESC LIMIT 1")
                result = cursor.fetchone()
                next_id = int(result[0][1:]) + 1 if result else 1
                user_id = f"D{next_id:04}"

                # Retrieve Driver-specific fields
                driver_name = request.form['driver-name']
                vehicle = request.form['vehicle']
                make = request.form['make']
                model = request.form['model']
                license_num = request.form['license-num']
                vehicle_color = request.form['vehicle-color']
                
                # Insert into user table
                cursor.execute('''
                    INSERT INTO user (User_ID, User_Email, User_Password, User_Name, User_Type)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, email, password, email.split('@')[0], user_type))
                
                # Insert into driver table
                cursor.execute('''
                    INSERT INTO driver (Driver_Name, Driver_Address, Vehicle, Make, Model, License_Num, Vehicle_Color, User_ID)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (driver_name, street_address, vehicle, make, model, license_num, vehicle_color, user_id))

            # Insert into address table for both user types
            cursor.execute('''
                INSERT INTO address (Street_Address, Suite_Number, Gate_Number, City, State, ZIP_Code, User_ID, Address_Type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'home')
            ''', (street_address, suite_number, gate_number, city, state, zip_code, user_id))

            conn.commit()
            flash("Account created successfully!", "success")
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f"An error occurred: {err}", "error")
        finally:
            cursor.close()
            conn.close()

    return render_template('signup.html')
  
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = database_connect()
        cursor = conn.cursor()
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
            session.pop('cart', None)
            session.pop('history', None)
            if user_type == 'customer':
                return redirect(url_for('customer_dashboard'))
            elif user_type == 'driver':
                return redirect(url_for('driver_dashboard'))
            elif user_type == 'business':
                return redirect(url_for('business_dashboard'))
            else:
                session['message'] = 'Unknown user type'
                return redirect(url_for('login'))
        else:
                flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/customer_dashboard')
def customer_dashboard():
    user_name = session.get('user') or 'Customer'
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT Restaurant_ID as id, Restaurant_Name as name, Restaurant_Rating as rating FROM restaurant")
    restaurants = cursor.fetchall()

    for r in restaurants:
        r['delivery_time'] = random.randint(20, 60)

    favorites = session.get('favorites', [])
    cart = session.get('cart', [])
    cart_count = len(cart)

    show_favorites = request.args.get('show_favorites')
    if show_favorites:
        restaurants = [r for r in restaurants if r['id'] in favorites]

    cursor.close()
    conn.close()
    
    return render_template('customer_dashboard.html',
        user_name=user_name,
        featured_restaurants=restaurants,
        cart_count=cart_count,
        favorites=favorites,
        show_favorites=bool(show_favorites),
        last_ordered_restaurant=session.get('last_ordered_restaurant')
    )

@app.route('/driver_dashboard')
def driver_dashboard():
    if 'user' not in session or session.get('user_type') != 'driver':
        return redirect(url_for('login'))
    user_id = session.get('user_id')

    # Schedule cleanup job specifically for logged-in driver
    # schedule_cleanup_for_driver(user_id)  # As discussed previously

    tab = request.args.get('tab', 'delivery')

    # Calculate calendar for this week (Sunday ... Saturday)
    today = datetime.today()
    weekday_idx = (today.weekday() + 1) % 7  # Sunday=0, ..., Saturday=6
    week_start = today - timedelta(days=weekday_idx)
    week_dates = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        week_dates.append({
            'short': d.strftime('%a'),      # Sun, Mon, Tue, etc.
            'date': d.day,                  # Day of month (30, 1, ...)
            'iso': d.strftime('%Y-%m-%d'),  # full ISO date for POST
            'long': d.strftime('%A'),       # Full day-of-week for db
            'month': d.strftime('%b')       # 'May', etc.
        })

    selected_idx = request.args.get('selected_idx')
    if selected_idx is None:
        selected_idx = weekday_idx
    else:
        selected_idx = int(selected_idx)

    # Check for ongoing delivery
    ongoing_delivery = session.get('delivery_active', False)

    conn = database_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM driver WHERE User_ID = %s", (user_id,))
    driver_info = cursor.fetchone()

    cursor.execute("""
        SELECT Driver_Fee, Driver_Tip, Customer_Name, Restaurant_Name
        FROM order_fulfilled
        WHERE Driver_Name = %s
    """, (driver_info['Driver_Name'],))
    earnings_records = cursor.fetchall()
    # Calculate total earnings
    total_earnings = sum(record['Driver_Fee'] + record['Driver_Tip'] for record in earnings_records)
    cursor.execute("""
        SELECT * FROM address
        WHERE User_ID = %s AND Address_Type = 'home'
    """, (user_id,))
    address_info = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        'driver_dashboard.html',
        email=session['user'],
        driver=driver_info,
        address=address_info,
        active_tab=tab,
        week_dates=week_dates,
        selected_idx=selected_idx,
        ongoing_delivery=ongoing_delivery,
        earnings_records=earnings_records,
        total_earnings=total_earnings
    )
def haversine(lon1, lat1, lon2, lat2):
    R = 6371
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

@app.route('/start_delivery')
def start_delivery():
    session['delivery_active'] = True
    return redirect(url_for('deliver_page'))

@app.route('/end_delivery', methods=['POST'])
def end_delivery():
    session.pop('delivery_active', None)
    return jsonify({'success': True})

@app.route('/deliver_page')
def deliver_page():
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return redirect(url_for('login'))

    return render_template('deliver_page.html')

@app.route('/order_offer')
def order_offer():
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    if 'order_index' not in session:
        session['order_index'] = 0

    if 'declined_orders' not in session:
        session['declined_orders'] = []

    declined_orders = set(session['declined_orders'])  # Use a set for faster lookup

    try:
        conn = database_connect()
        cursor = conn.cursor(dictionary=True)

        # Fetch all available orders
        cursor.execute("""
            SELECT OrderR_ID, Order_ID, R_name, R_Address, R_City, R_Zip,
                   C_Name, C_Address, C_City, C_Zip, Fees, Tip
            FROM orderrequest
            WHERE Order_R_Status != 'rejected'
              AND Order_D_Status = 'Waiting For Assignment'
        """)
        
        orders = cursor.fetchall()
        cursor.close()
        conn.close()

        total_orders = len(orders)

        # If no orders are available, return a failure message
        if total_orders == 0:
            return jsonify({'success': False, 'message': 'No orders available'})

        # Find the next valid order after current index
        for _ in range(total_orders):
            current_idx = session['order_index'] % total_orders
            current_order = orders[current_idx]

            session['order_index'] = (session['order_index'] + 1) % total_orders  # Move to next order, wrap direction

            if current_order['OrderR_ID'] not in declined_orders:
                total_offer_amount = float(current_order['Fees'] + current_order['Tip'])
                return jsonify({
                    'success': True,
                    'order': current_order,
                    'total_offer_amount': total_offer_amount
                })

        # If all orders have been declined, reset the index and return a failure message
        session['order_index'] = 0
        session['declined_orders'].clear()
        return jsonify({'success': False, 'message': 'All orders declined, restarting queue...'})

    except Exception as e:
        print("Failed to fetch order:", e)
        return jsonify({'success': False, 'message': f'Error retrieving order: {e}'}), 500
    
@app.route('/fetch_order_details', methods=['POST'])
def fetch_order_details():
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    try:
        order_id = request.json.get('order_id')

        # Correct the table name with backticks
        conn = database_connect()
        cursor = conn.cursor(dictionary=True)

        # Correct SQL syntax by escaping tables
        cursor.execute("""
            SELECT o.Customer_name, o.Item, o.Quantity, r.R_name AS RestaurantName
            FROM `order` AS o  -- Use backticks to escape 'order'
            JOIN orderrequest AS r ON o.Order_ID = r.Order_ID
            WHERE o.Order_ID = %s
        """, (order_id,))
        
        order_details = cursor.fetchall()
        cursor.close()
        conn.close()

        if order_details:
            return jsonify({'success': True, 'order_details': order_details})
        else:
            return jsonify({'success': False, 'message': 'No order details found'}), 404

    except Exception as e:
        print("Failed to fetch order details:", e)
        return jsonify({'success': False, 'message': f'Error retrieving order details: {e}'}), 500
    
@app.route('/complete_delivery', methods=['POST'])
def complete_delivery():
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    try:
        order_id = request.json.get('order_id')
        # Remove earnings since it's not part of any table 

        # Connect to the database
        conn = database_connect()
        cursor = conn.cursor(dictionary=True)

        # Fetch necessary details for fulfillment logging
        cursor.execute("""
            SELECT r.R_name, o.Customer_name, r.Fees, r.Tip 
            FROM orderrequest r
            JOIN `order` o ON r.Order_ID = o.Order_ID
            WHERE r.Order_ID = %s
        """, (order_id,))
        order_info = cursor.fetchone()

        # Fetch driver name from the session's user ID
        cursor.execute("""
            SELECT Driver_Name 
            FROM driver 
            WHERE User_ID = %s
        """, (session['user_id'],))
        driver_info = cursor.fetchone()

        # Update the order's status to 'Delivered'
        cursor.execute("""
            UPDATE orderrequest 
            SET Order_D_Status = 'Delivered'
            WHERE Order_ID = %s
        """, (order_id,))

        # Insert a record into order_fulfilled table
        cursor.execute("""
            INSERT INTO order_fulfilled (OrderR_ID, Customer_Name, 
                                         Driver_Fee, Driver_Tip, Restaurant_Name, Driver_Name)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            order_id,
            order_info['Customer_name'],
            order_info['Fees'],
            order_info['Tip'],
            order_info['R_name'],
            driver_info['Driver_Name'],
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Delivery completed and recorded.'})

    except mysql.connector.Error as err:
        print("Database Error: ", err)
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    except Exception as e:
        print("General Error: ", e)
        return jsonify({'success': False, 'message': f'Error updating order status: {e}'}), 500
    
@app.route('/update_order_status', methods=['POST'])
def update_order_status():
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    try:
        order_id = request.json.get('order_id')

        conn = database_connect()
        cursor  = conn.cursor()

        # Update the order's delivery status
        cursor.execute("""
            UPDATE orderrequest 
            SET Order_D_Status = 'Picked Up'
            WHERE Order_ID = %s
        """, (order_id,))
        conn.commit()
        
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Order status updated successfully.'})
    
    except mysql.connector.Error as err:
        print("Database Error: ", err)
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    except Exception as e:
        print("General Error: ", e)
        return jsonify({'success': False, 'message': f'Error updating order status: {e}'}), 500
    
@app.route('/order_decline', methods=['POST'])
def order_decline():
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    declined_order_id = request.form.get('order_id')
    if declined_order_id:
        declined_orders = session.get('declined_orders', [])
        declined_orders.append(declined_order_id)
        session['declined_orders'] = declined_orders
        
        # Optionally update the order's status back to available after a lock period ends
        # cursor.execute("UPDATE orderrequest SET Order_D_Status = 'Waiting For Assignment' WHERE OrderR_ID = %s", (declined_order_id,))
        # conn.commit()
    
    return jsonify({'success': True})
@app.route('/nearby_cities', methods=['POST'])
def nearby_cities():
    data = request.get_json()
    user_lat = float(data['lat'])
    user_lon = float(data['lon'])
    # List at least 5 cities, feel free to add more for full coverage!
    cities = [
        {'name': 'McAllen', 'lat': 26.2034, 'lon': -98.2300},
        {'name': 'Edinburg', 'lat': 26.3017, 'lon': -98.1633},
        {'name': 'Pharr', 'lat': 26.1948, 'lon': -98.1836},
        {'name': 'Mission', 'lat': 26.2159, 'lon': -98.3253},
        {'name': 'San Juan', 'lat': 26.1892, 'lon': -98.1553},
        {'name': 'Donna', 'lat': 26.1706, 'lon': -98.0528},
        {'name': 'Weslaco', 'lat': 26.1595, 'lon': -97.9908}
        # ... add as many as needed!
    ]
    for city in cities:
        km = haversine(user_lon, user_lat, city['lon'], city['lat'])
        mi = km * 0.621371      # Convert kilometers to miles
        city['distance'] = mi
    cities.sort(key=lambda x: x['distance'])
    html = ""
    shown = 0
    for city in cities:
        html += f"""<div class="city-slot" data-city="{city['name']}"><b>{city['name']}</b> ({city['distance']:.1f} miles away)</div>"""
        shown += 1
        if shown >= 5:
            break
    return html
@app.route('/user_scheduled_times', methods=['POST'])
def user_scheduled_times():
    if 'user_id' not in session:
        return '', 401

    user_id = session['user_id']
    req = request.get_json()
    selected_date = req['dateiso']    # ISO string, e.g. 2024-05-20

    conn = database_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT Start_Time, End_Time, Notes
        FROM availability
        WHERE User_ID = %s AND Date = %s
        ORDER BY Start_Time
    """, (user_id, selected_date))
    slots = cursor.fetchall()
    cursor.close()
    conn.close()

    def time_to_str(val):
        if hasattr(val, 'strftime'):
            # It's a time object
            return val.strftime('%I:%M %p').lstrip('0')
        elif isinstance(val, timedelta):
            # Convert to time and then use strftime
            total_seconds = int(val.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            fake_time = datetime(1900, 1, 1, hours, minutes)
            return fake_time.strftime('%I:%M %p').lstrip('0')
        elif isinstance(val, str):
            # fallback: naive slice string
            # (optional: parse string to time for am/pm, but this covers most cases)
            parsed = datetime.strptime(val[:5], '%H:%M')
            return parsed.strftime('%I:%M %p').lstrip('0')
        else:
            return str(val)

    html = ""
    if not slots:
        html = "<div style='text-align:center;color:#999;margin-top:24px;'>No scheduled times for this day.</div>"
    else:
        for s in slots:
            html += f"""
            <div class="scheduled-slot">
                <b>{s['Notes']}</b><br>
                {time_to_str(s['Start_Time'])} - {time_to_str(s['End_Time'])}
            </div>"""
    return html
@app.route('/save_availability', methods=['POST'])
def save_availability():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401

    user_id = session['user_id']
    city = request.form['city']
    dateiso = request.form['dateiso']    # yyyy-mm-dd
    day_of_week = request.form['day_of_week']  # "Monday", ...
    start_time = request.form['start_time']    # HH:MM
    end_time = request.form['end_time']

    # Optional: save city in Notes column
    notes = city

    # Block past dates
    if dateiso < date.today().isoformat():
        return jsonify({'success': False, 'message': 'Cannot schedule in the past.'}), 400

    try:
        conn = database_connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO availability (User_ID, Date, Day_of_Week, Start_Time, End_Time, Notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, dateiso, day_of_week, start_time, end_time, notes))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Delivery Time Saved'})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': 'Failed to Save'}), 500
    
@app.route('/update_account', methods=['POST'])
def update_account():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401

    user_id = session['user_id']
    
    # Gather form data
    street_address = request.form['street_address']
    suite_number = request.form['suite_number']
    gate_number = request.form['gate_number']
    city = request.form['city']
    state = request.form['state']
    zip_code = request.form['zip_code']
    
    vehicle = request.form['vehicle']
    make = request.form['make']
    model = request.form['model']
    vehicle_color = request.form['vehicle_color']

    try:
        conn = database_connect()
        cursor = conn.cursor()

        # Update driver details
        cursor.execute("""
            UPDATE driver SET Vehicle = %s, Make = %s, Model = %s, Vehicle_Color = %s
            WHERE User_ID = %s
        """, (vehicle, make, model, vehicle_color, user_id))
        
        # Update address details
        cursor.execute("""
            UPDATE address SET Street_Address = %s, Suite_Number = %s, Gate_Number = %s,
            City = %s, State = %s, ZIP_Code = %s
            WHERE User_ID = %s AND Address_Type = 'home'
        """, (street_address, suite_number, gate_number, city, state, zip_code, user_id))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Account updated successfully.'})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': 'Failed to update account.'}), 500
    
@app.route('/earnings')
def earnings():
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    try:
        conn = database_connect()
        cursor = conn.cursor(dictionary=True)
        
        # Fetch earnings for the driver
        cursor.execute("""
            SELECT Driver_Fee, Driver_Tip, Customer_Name, Restaurant_Name
            FROM order_fulfilled
            WHERE Driver_Name = (SELECT Driver_Name FROM driver WHERE User_ID = %s)
        """, (user_id,))
        earnings_records = cursor.fetchall()

        # Calculate total earnings
        total_earnings = sum(record['Driver_Fee'] + record['Driver_Tip'] for record in earnings_records)

        cursor.close()
        conn.close()

        return render_template(
            'driver_dashboard.html',
            total_earnings=total_earnings,
            earnings_records=earnings_records,
            active_tab='earnings'
        )

    except mysql.connector.Error as err:
        print("Database Error: ", err)
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    except Exception as e:
        print("General Error: ", e)
        return jsonify({'success': False, 'message': f'Error fetching earnings: {e}'}), 500
    
@app.route('/business_dashboard')
def business_dashboard():
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM restaurant WHERE User_ID = %s", (user_id,))
    result = cursor.fetchone()
    restaurant_name = result['Restaurant_Name'] if result else 'Your Restaurant'

    # Get the page number from the URL, default to 1 if not provided
    page = request.args.get('page', 1, type=int)
    orders_per_page = 5
    offset = (page - 1) * orders_per_page

    # Count new orders
    cursor.execute("""
        SELECT COUNT(*) AS new_order_count
        FROM orderrequest
        WHERE R_name = %s AND Order_R_Status = 'new'
    """, (restaurant_name,))
    order_count_result = cursor.fetchone()
    new_order_count = order_count_result['new_order_count'] if order_count_result else 0

    cursor.execute("""
        SELECT o.Order_ID, o.C_Name, ord.Item, ord.Quantity, ord.Price, o.Timestamp ,o.Order_R_Status
        FROM orderrequest o
        JOIN `order` ord ON o.Order_ID = ord.Order_ID
        WHERE o.R_name = %s AND o.Order_R_Status = 'new'
        LIMIT %s OFFSET %s
    """, (restaurant_name, orders_per_page, offset))

    rows= cursor.fetchall()

    has_next=len(rows)
    rows=rows[:orders_per_page]
    cursor.close()
    conn.close()

    # Group by Order_ID and calculate total price
    grouped_orders = defaultdict(lambda: {'items': [], 'total_price': 0, 'C_Name': '', 'Timestamp': '', 'Order_R_Status': '', 'Order_ID': ''})

    for row in rows:
        order_id = row['Order_ID']
        total_item_price = row['Quantity'] * row['Price']  # Calculate total price for this item

        # Add/Append order details for this order
        grouped_orders[order_id]['Order_ID'] = row['Order_ID']
        grouped_orders[order_id]['C_Name'] = row['C_Name']
        grouped_orders[order_id]['Timestamp'] = row['Timestamp']
        grouped_orders[order_id]['Order_R_Status'] = row['Order_R_Status']
        
        # Add items for this order
        grouped_orders[order_id]['items'].append({
            'Item': row['Item'],
            'Quantity': row['Quantity'],
            'Price': row['Price'],
            'Total_Item_Price': total_item_price  # Add the total price for this item
        })

        # Sum the total price for all items in the order
        grouped_orders[order_id]['total_price'] += total_item_price

    return render_template('business_dashboard.html', orders=grouped_orders, restaurant_name=restaurant_name, new_order_count=new_order_count, has_next=has_next, page=page)


@app.route('/accept_order/<int:order_id>', methods=['POST'])
def accept_order(order_id):
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = database_connect()
    cursor = conn.cursor()

    # Update the order status to 'accepted'
    cursor.execute("""
        UPDATE orderrequest SET Order_R_Status = 'accepted'
        WHERE Order_ID = %s
    """, (order_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Order accepted successfully!")
    page=request.args.get('page',1,type=int)
    return redirect(url_for('business_dashboard',page=page))

@app.route('/reject_order/<int:order_id>', methods=['POST'])
def reject_order(order_id):
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    source = request.form.get('source', 'dashboard')  # Default fallback

    conn = database_connect()
    cursor = conn.cursor()

    # Update the order status to 'rejected'
    cursor.execute("""
        UPDATE orderrequest SET Order_R_Status = 'rejected'
        WHERE Order_ID = %s
    """, (order_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Order Rejected")

    # Redirect based on where the reject came from
    if source == 'new_orders':
        return redirect(url_for('business_dashboard'))
    elif source == 'accepted_orders':
        return redirect(url_for('view_accepted_orders'))
    else:
        return redirect(url_for('business_dashboard'))

@app.route('/mark_as_complete/<int:order_id>', methods=['POST'])
def mark_as_complete(order_id):
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    # Connect to the database and update the order's status
    conn = database_connect()
    cursor = conn.cursor()

    # Update the order's status to "completed"
    cursor.execute("""
        UPDATE orderrequest
        SET Order_R_Status = 'fulfilled'
        WHERE Order_ID = %s
    """, (order_id,))
    
    conn.commit()
    cursor.close()
    conn.close()

    flash('Order marked as complete!', 'success')
    return redirect(url_for('view_accepted_orders'))

@app.route('/new_orders')
def view_new_orders():
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    # Get restaurant name associated with the business user
    cursor.execute("SELECT Restaurant_Name FROM restaurant WHERE User_ID = %s", (user_id,))
    result = cursor.fetchone()
    restaurant_name = result['Restaurant_Name'] if result else None

    if not restaurant_name:
        flash('No restaurant found for this user.', 'danger')
        return redirect(url_for('business_dashboard'))

    # Get new orders from orderrequest table
    cursor.execute("""
        SELECT ord.Order_ID, r.C_Name AS C_Name, ord.Item, ord.Quantity, ord.Price, ord.Timestamp,
        r.C_Address, r.C_City, r.C_Zip
        FROM orderrequest r
        JOIN `order` ord ON ord.Order_ID = r.Order_ID
        WHERE r.R_name = %s AND r.Order_R_Status = 'new'

    """, (restaurant_name,))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('view_orders.html', orders=orders, restaurant_name=restaurant_name)

@app.route('/accepted_orders')
def view_accepted_orders():
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    # Get restaurant name associated with the business user
    cursor.execute("SELECT Restaurant_Name FROM restaurant WHERE User_ID = %s", (user_id,))
    result = cursor.fetchone()
    restaurant_name = result['Restaurant_Name'] if result else None

    if not restaurant_name:
        flash('No restaurant found for this user.', 'danger')
        return redirect(url_for('business_dashboard'))

    # Get accepted orders from orderrequest table
    cursor.execute("""
        SELECT o.Order_ID, o.C_Name, ord.Item, ord.Quantity, ord.Price, o.Timestamp,
            o.C_Address, o.C_City, o.C_Zip
        FROM orderrequest o
        JOIN `order` ord ON ord.Order_ID = o.Order_ID
        LEFT JOIN restaurant r ON o.R_name = r.Restaurant_Name
        WHERE o.R_name = %s AND o.Order_R_Status = 'accepted'
    """, (restaurant_name,))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('accepted_orders.html', orders=orders, restaurant_name=restaurant_name)

@app.route('/edit_account', methods=['GET', 'POST'])
def edit_account():
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    # Fetch current restaurant and address details
    cursor.execute("""
        SELECT r.Restaurant_Name, r.Restaurant_Address, a.Street_Address, a.Suite_Number, a.Gate_Number, a.City, a.State, a.ZIP_Code
        FROM restaurant r
        LEFT JOIN address a ON r.User_ID = a.User_ID
        WHERE r.User_ID = %s
    """, (user_id,))
    result = cursor.fetchone()

    # Fetch availability details for each day of the week
    cursor.execute("""
        SELECT Day_of_Week, Start_Time, End_Time
        FROM availability
        WHERE User_ID = %s
    """, (user_id,))
    availability_results = cursor.fetchall()
    
    cursor.close()
    conn.close()

    # Create a dictionary to store weekly hours
    weekly_hours = {day: {} for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']}
    for availability in availability_results:
        day = availability['Day_of_Week']
        if day:
            weekly_hours[day] = {
                'start_time': availability['Start_Time'],
                'end_time': availability['End_Time']
            }
    
    # Handle GET request - show current account details in form
    if request.method == 'GET':
        if result:
            address_info = {
                'Street_Address': result['Street_Address'],
                'Suite_Number': result['Suite_Number'],
                'Gate_Number': result['Gate_Number'],
                'City': result['City'],
                'State': result['State'],
                'ZIP_Code': result['ZIP_Code'],
            }
            restaurant_info = result
        else:
            address_info = {}
            restaurant_info = {}

        return render_template('edit_account.html', restaurant_info=restaurant_info, address_info=address_info, weekly_hours=weekly_hours)

    # Handle POST request for updating account details
    if request.method == 'POST':
        # Process form submissions for updates here

        # Example update logic (similar to what was defined previously)
        
        # Redirect after successful update
        flash('Account updated successfully!', 'success')
        return redirect(url_for('edit_account'))

@app.route('/past_orders')
def past_orders():
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    # Retrieve the restaurant's name
    cursor.execute("SELECT Restaurant_Name FROM restaurant WHERE User_ID = %s", (user_id,))
    result = cursor.fetchone()
    restaurant_name = result['Restaurant_Name'] if result else 'Your Restaurant'

    # Query for past orders (orders that have been completed or rejected)
    query = """
    SELECT 
        orr.Order_ID, 
        orr.C_Name, 
        ord.Item, 
        ord.Quantity, 
        ord.Price, 
        orr.Timestamp,
        orr.Reject_Reason
    FROM orderrequest orr
    JOIN `order` ord ON orr.Order_ID = ord.Order_ID
    WHERE orr.R_name = %s AND orr.Order_R_Status IN ('fulfilled', 'rejected','')
    """

    cursor.execute(query, (restaurant_name,))
    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('past_orders.html', orders=orders, restaurant_name=restaurant_name)

@app.route('/order_details/<int:order_id>')
def order_details(order_id):
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    # Fetch order details by Order_ID
    cursor.execute("""
    SELECT o.Order_ID, o.Timestamp, o.Order_R_Status, o.Reject_Reason,
    d.Item, d.Quantity, d.Price,
    r.C_Address, r.C_City, r.C_Zip
    FROM orderrequest o
    JOIN `order` d ON o.Order_ID = d.Order_ID
    LEFT JOIN restaurant r ON o.R_name = r.Restaurant_Name
    WHERE o.Order_ID = %s

    """, (order_id,))
    
    order_details = cursor.fetchone()
    
    cursor.close()
    conn.close()

    if order_details:
        return render_template('order_details.html', order=order_details)
    else:
        flash("Order not found.", "danger")
        return redirect(url_for('view_new_orders'))

@app.route('/logout')
def logout():
    session.clear()
    session['message'] = 'Logged out.'
    return redirect(url_for('login'))

@app.route('/restaurants')
def view_restaurants():
    if 'user' not in session or session.get('user_type') != 'customer':
        return redirect(url_for('login'))
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM restaurant")
    restaurants = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('view_restaurants.html', restaurants=restaurants)

@app.route('/menu/<int:restaurant_id>')
def view_menu(restaurant_id):
    if 'user' not in session or session.get('user_type') != 'customer':
        return redirect(url_for('login'))
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT Restaurant_Name FROM restaurant WHERE Restaurant_ID = %s", (restaurant_id,))
    restaurant = cursor.fetchone()
    cursor.execute("SELECT * FROM menu WHERE Restaurant_ID = %s", (restaurant_id,))
    rows = cursor.fetchall()
    unique_items = []
    seen_items = set()
    for row in rows:
        if row['Item'] not in seen_items:
            unique_items.append(row)
            seen_items.add(row['Item'])
    cursor.close()
    conn.close()
    restaurant_name = restaurant['Restaurant_Name'] if restaurant else "Unknown Restaurant"
    return render_template('view_menu.html', restaurant=restaurant, restaurant_name=restaurant_name, menu_items=unique_items, restaurant_id=restaurant_id)

@app.route('/add_to_cart/<int:restaurant_id>', methods=['POST'])
def add_to_cart(restaurant_id):
    selected_items = request.form.getlist('selected_items')
    cart = session.get('cart', [])
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    # ✅ Fetch restaurant name once
    cursor.execute("SELECT Restaurant_Name FROM restaurant WHERE Restaurant_ID = %s", (restaurant_id,))
    restaurant_row = cursor.fetchone()
    restaurant_name = restaurant_row['Restaurant_Name'] if restaurant_row else "Unknown"

    for item_id in selected_items:
        quantity = int(request.form.get(f'quantity_{item_id}', 1))
        cursor.execute("SELECT * FROM menu WHERE menu_ID = %s", (item_id,))
        item = cursor.fetchone()
        if item:
            cart.append({
                'menu_ID': item['menu_ID'],
                'Item': item['Item'],
                'Price': item['Price'],
                'Quantity': quantity,
                'Restaurant_ID': restaurant_id,
                'Restaurant_Name': restaurant_name  # ✅ add restaurant name into cart
            })

    cursor.close()
    conn.close()
    session['cart'] = cart
    session['message'] = f"Added {len(selected_items)} items to cart!"
    return redirect(url_for('checkout'))

@app.route('/reset_history')
def reset_history():
    session.pop('history', None)
    return "Session history cleared!"


@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    menu_ID = request.form.get('menu_ID')
    restaurant_ID = int(request.form.get('restaurant_ID'))
    cart = session.get('cart', [])
    updated_cart = [item for item in cart if not (item['menu_ID'] == menu_ID and item['Restaurant_ID'] == restaurant_ID)]
    session['cart'] = updated_cart
    session.modified = True
    session['message'] = 'Item removed from cart.'
    return redirect(url_for('view_cart'))

   
@app.route('/toggle_favorite/<int:restaurant_id>', methods=['POST'])
def toggle_favorite(restaurant_id):
    favorites = session.get('favorites', [])
    if restaurant_id in favorites:
        favorites.remove(restaurant_id)
    else:
        favorites.append(restaurant_id)
    session['favorites'] = favorites
    return {'is_favorite': restaurant_id in favorites}

@app.route('/order_again/<int:restaurant_id>', methods=['POST'])
def order_again(restaurant_id):
    history = session.get('history', [])
    cart = session.get('cart', [])
    for order in history:
        if order.get('Restaurant_Name') and order.get('Restaurant_ID') == restaurant_id:
            for item in order['Items']:
                cart.append({
                    'menu_ID': None,
                    'Item': item['Item'],
                    'Price': item['Price'],
                    'Quantity': item['Quantity'],
                    'Restaurant_ID': restaurant_id
                })
    session['cart'] = cart
    session['message'] = 'Previous order added to cart!'
    return redirect(url_for('checkout'))


@app.route('/update_quantity', methods=['POST'])
def update_quantity():
    menu_ID = request.form.get('menu_ID')
    restaurant_ID = int(request.form.get('restaurant_ID'))
    new_quantity = int(request.form.get('quantity'))
    cart = session.get('cart', [])
    for item in cart:
        if item['menu_ID'] == menu_ID and item['Restaurant_ID'] == restaurant_ID:
            item['Quantity'] = new_quantity
            break
    session['cart'] = cart
    session.modified = True
    session['message'] = 'Quantity updated.'
    return redirect(url_for('view_cart'))

@app.route('/checkout')
def checkout():
    cart = session.get('cart', [])
    if not cart:
        session['message'] = 'Your cart is empty.'
        return redirect(url_for('customer_dashboard'))  # or 'order_history'
    total = sum(float(item['Price']) * item['Quantity'] for item in cart)
    restaurant_name = cart[0]['Restaurant_Name'] if cart else "Unknown"
    return render_template('checkout.html', cart=cart, total=total, restaurant_name=restaurant_name)



@app.route('/place_order', methods=['POST'])
def place_order():
    cart = session.get('cart', [])
    if not cart:
        session['message'] = 'Your cart is empty.'
        return redirect(url_for('customer_dashboard'))

    restaurant_id = cart[0]['Restaurant_ID']
    tip_input = request.form.get('tip', '0')

    try:
        tip = float(tip_input)
    except ValueError:
        tip = 0.0

    # Calculate total for the restaurant
    restaurant_total = sum(float(item['Price']) * item['Quantity'] for item in cart)

    conn = database_connect()
    cursor = conn.cursor(dictionary=True)

    # Fetch customer and restaurant information with addresses
    user_id = session.get('user_id')

    # Customer info with address
    cursor.execute("""
        SELECT c.Customer_Fname, c.Customer_LName, c.Customer_ID, 
               ca.Street_Address AS C_Street_Address, ca.City AS C_City, ca.ZIP_Code AS C_Zip
        FROM customer c
        JOIN address ca ON c.User_ID = ca.User_ID
        WHERE c.User_ID = %s
    """, (user_id,))
    customer_data = cursor.fetchone()

    if not customer_data:
        session['message'] = 'Unable to fetch customer information.'
        cursor.close()
        conn.close()
        return redirect(url_for('customer_dashboard'))

    c_name = f"{customer_data['Customer_Fname']} {customer_data['Customer_LName']}"
    customer_id = customer_data['Customer_ID']

    # Restaurant info with address
    cursor.execute("""
        SELECT r.Restaurant_Name, a.Street_Address AS R_Street_Address, a.City AS R_City, a.ZIP_Code AS R_Zip
        FROM restaurant r
        JOIN address a ON r.User_ID = a.User_ID
        WHERE r.Restaurant_ID = %s
    """, (restaurant_id,))
    restaurant_data = cursor.fetchone()

    if not restaurant_data:
        session['message'] = 'Unable to fetch restaurant information.'
        cursor.close()
        conn.close()
        return redirect(url_for('customer_dashboard'))

    r_name = restaurant_data['Restaurant_Name']

    # Insert each item into the `order` table
    for item in cart:
        cursor.execute("""
            INSERT INTO `order` (Customer_name, Restaurant_ID, Customer_ID, Item, Item_ID, Price, Quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            c_name,
            restaurant_id,
            customer_id,
            item['Item'],
            item['menu_ID'],  # Assuming menu_ID maps to Item_ID
            item['Price'],
            item['Quantity']
        ))

    conn.commit()

    # Use the last inserted Order_ID to reference in orderrequest
    cursor.execute("SELECT LAST_INSERT_ID();")
    order_id = cursor.fetchone()['LAST_INSERT_ID()']

    # Insert into orderrequest using the obtained Order_ID
    cursor.execute("""
        INSERT INTO orderrequest (Order_ID, R_name, R_Address, R_City, R_Zip, C_Name, C_Address, C_City, C_Zip, Fees, Tip, Order_R_Status, Order_D_Status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        order_id,
        r_name,
        restaurant_data['R_Street_Address'],
        restaurant_data['R_City'],
        restaurant_data['R_Zip'],
        c_name,
        customer_data['C_Street_Address'],
        customer_data['C_City'],
        customer_data['C_Zip'],
        restaurant_total,
        tip,
        'new',
        'Waiting For Assignment'
    ))

    conn.commit()
    cursor.close()
    conn.close()

    # Clear cart after successfully placing the order
    session.pop('cart', None)

    return redirect(url_for('order_history'))


@app.route('/confirm_order', methods=['POST'])
def confirm_order():
    action = request.form['action']
    if action == 'place':
        tip_str = request.form.get('tip', '0.00')
        return place_order()
    elif action == 'cancel':
        session.pop('cart', None)  # ✅ clear cart
        session['message'] = 'Order canceled successfully.'
        return redirect(url_for('order_history'))


@app.route('/cancel_order', methods=['POST'])
def cancel_order():
    session.pop('order', None)
    session['message'] = 'Order was canceled.'
    return redirect(url_for('customer_dashboard'))

@app.route('/fulfill_order/<int:order_id>', methods=['POST'])
def fulfill_order(order_id):
    conn = database_connect()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orderrequest SET Order_R_Status = 'fulfilled' WHERE Order_ID = %s
    """, (order_id,))
    conn.commit()
    cursor.close()
    conn.close()

    session['message'] = f"Order {order_id} marked as fulfilled."
    return redirect(url_for('order_history'))


@app.route('/order_history')
def order_history():
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)
    
    # Use User_ID to cross-reference orders instead of name for more reliable identification
    user_id = session.get('user_id')

    # Ensure all relevant orders for the logged-in customer are fetched
    cursor.execute("""
        SELECT *
        FROM orderrequest
        WHERE C_Name = (SELECT CONCAT(Customer_Fname, ' ', Customer_LName) FROM customer WHERE User_ID = %s)
    """, (user_id,))
    orders = cursor.fetchall()

    history = []

    for order in orders:
        order_id = order['Order_ID']  # Use Order_ID to match with items in the `order` table

        # Query items linked to this order using the correct Order_ID
        cursor.execute("""
            SELECT Item, Price, Quantity
            FROM `order`
            WHERE Order_ID = %s
        """, (order_id,))
        items = cursor.fetchall()

        item_list = []
        for i in items:
            item_list.append({
                'Item': i['Item'],
                'Price': float(i['Price']),
                'Quantity': i['Quantity'],
                'Subtotal': float(i['Price']) * i['Quantity']
            })

        # Collect and calculate the total for display
        history.append({
            'order_id': order_id,
            'Restaurant_Name': order['R_name'],
            'Tip': float(order['Tip']),
            'Total': float(order['Fees']) + float(order['Tip']),
            'Request_Status': order['Order_R_Status'],
            'Driver_Status': order['Order_D_Status'],
            'Items': item_list
        })

    cursor.close()
    conn.close()

    return render_template('order_history.html', history=history)

@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

if __name__ == '__main__':
    app.run(debug=True)
