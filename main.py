from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'


# Database configuration
DATABASE_CONFIG = {
    "host": "localhost",      # XAMPP uses localhost for MySQL
    "user": "root",           # Default MySQL username for XAMPP
    "password": "",           # Default password is empty for XAMPP
    "database": "TableDash"   # Name of the database you created/imported
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

from flask import Flask, render_template, session, redirect, url_for
from collections import defaultdict


@app.route('/business_dashboard',methods=['GET'])
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
        WHERE R_name = %s AND Order_Status = 'new'
    """, (restaurant_name,))
    order_count_result = cursor.fetchone()
    new_order_count = order_count_result['new_order_count'] if order_count_result else 0

    cursor.execute("""
        SELECT o.Order_ID, o.C_Name, ord.Item, ord.Quantity, ord.Price, o.Timestamp ,o.Order_Status
        FROM orderrequest o
        JOIN `order` ord ON o.Order_ID = ord.Order_ID
        WHERE o.R_name = %s AND o.Order_Status = 'new'
        LIMIT %s OFFSET %s
    """, (restaurant_name, orders_per_page, offset))

    rows= cursor.fetchall()

    has_next=len(rows)
    rows=rows[:orders_per_page]
    cursor.close()
    conn.close()

    # Group by Order_ID and calculate total price
    grouped_orders = defaultdict(lambda: {'items': [], 'total_price': 0})

    for row in rows:
        order_id = row['Order_ID']
        total_item_price = row['Quantity'] * row['Price']  # Calculate total price for this item
        grouped_orders[order_id]['Order_ID']=row['Order_ID']
        grouped_orders[order_id]['C_Name'] = row['C_Name']
        grouped_orders[order_id]['Timestamp'] = row['Timestamp']
        grouped_orders[order_id]['Order_Status'] = row['Order_Status']
        grouped_orders[order_id]['items'].append({
            'Item': row['Item'],
            'Quantity': row['Quantity'],
            'Price': row['Price'],
            'Total_Item_Price': total_item_price  # Add the total price for this item
        })
        grouped_orders[order_id]['total_price'] += total_item_price  # Sum the total price for all items in the order

    return render_template('business_dashboard.html', orders=grouped_orders, restaurant_name=restaurant_name,new_order_count=new_order_count,has_next=has_next,page=page)


@app.route('/accept_order/<int:order_id>', methods=['POST'])
def accept_order(order_id):
    if 'user' not in session or session.get('user_type') != 'business':
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = database_connect()
    cursor = conn.cursor()

    # Update the order status to 'accepted'
    cursor.execute("""
        UPDATE orderrequest SET Order_Status = 'accepted'
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
        UPDATE orderrequest SET Order_Status = 'rejected'
        WHERE Order_ID = %s
    """, (order_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Order Rejected")

    # Redirect based on where the reject came from
    if source == 'new_orders':
        return redirect(url_for('new_order_requests'))
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
        SET Order_Status = 'completed'
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
        WHERE r.R_name = %s AND r.Order_Status = 'new'

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
        WHERE o.R_name = %s AND o.Order_Status = 'accepted'
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

    # Fetch current restaurant details (address, hours, etc.)
    cursor.execute("""
        SELECT r.Restaurant_Name, r.Restaurant_Address, a.Day_of_Week, a.Start_Time, a.End_Time
        FROM restaurant r
        LEFT JOIN availability a ON r.User_ID = a.User_ID
        WHERE r.User_ID = %s
    """, (user_id,))
    
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    # Handle GET request - show current account details in form
    if request.method == 'GET':
        # Make sure the result isn't empty, and pass it to the template
        if result:
            restaurant_info = result[0]  # Assuming only one row for the restaurant
        else:
            restaurant_info = {}

        return render_template('edit_account.html', restaurant_info=restaurant_info)

    # Handle POST request - update the account details
    if request.method == 'POST':
        # Get the new data from the form
        new_address = request.form.get('address')
        new_hours = request.form.get('hours')

        # Update the restaurant's details
        conn = database_connect()
        cursor = conn.cursor()

        # Update address
        if new_address:
            cursor.execute("""
                UPDATE restaurant 
                SET Restaurant_Address = %s 
                WHERE User_ID = %s
            """, (new_address, user_id))

        # Update hours
        if new_hours:
            cursor.execute("""
                UPDATE availability 
                SET Day_of_Week = %s, Start_Time = %s, End_Time = %s 
                WHERE User_ID = %s
            """, (new_hours['day'], new_hours['start_time'], new_hours['end_time'], user_id))

        conn.commit()
        cursor.close()
        conn.close()

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
    WHERE orr.R_name = %s AND orr.Order_Status IN ('completed', 'rejected')
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
    SELECT o.Order_ID, o.Timestamp, o.Order_Status, o.Reject_Reason,
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
    session.pop('user', None)
    session.pop('user_type', None)
    session.pop('user_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)