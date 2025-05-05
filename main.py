from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, date
from math import radians, sin, cos, sqrt, atan2

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
        ongoing_delivery=ongoing_delivery
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
    # Logic for processing and returning the order offer
    if 'user_id' not in session or session.get('user_type') != 'driver':
        return redirect(url_for('login'))

    try:
        conn = database_connect()
        cursor = conn.cursor(dictionary=True)
        
        # Fetch one order from orderrequest table
        cursor.execute("""
            SELECT * FROM orderrequest
            ORDER BY Timestamp LIMIT 1
        """)
        order = cursor.fetchone()

        if order:
            # Calculate the combined amount of fees and tip
            total_offer_amount = order['Fees'] + order['Tip']
        else:
            # Handle case when there are no orders
            return "<div style='text-align:center;margin-top:24px;'>No orders available at the moment.</div>"

        cursor.close()
        conn.close()

        return render_template('order_offer.html', order=order, total_offer_amount=total_offer_amount)

    except Exception as e:
        print("Failed to fetch order:", e)
        return "<div style='text-align:center;margin-top:24px;color:red;'>Error retrieving order.</div>"

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