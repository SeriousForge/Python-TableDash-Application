from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "TableDash"
}

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

@app.route('/')
def splash():
    return render_template('splash.html')

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
            session['message'] = 'Invalid credentials'
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

@app.route('/order_history')
def order_history():
    user_id = session.get('user_id')
    conn = database_connect()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orderrequest WHERE C_Name = %s", ('C_Name')),
    orders = cursor.fetchall()
    history = []
    for order in orders:
        cursor.execute("SELECT * FROM `order` WHERE Order_ID = %s", (order['Order_ID'],))
        items = cursor.fetchall()
        item_list = []
        for i in items:
            item_list.append({
                'Item': i['Item'],
                'Price': float(i['Price']),
                'Quantity': i['Quantity'],
                'Subtotal': float(i['Price']) * i['Quantity']
            })
        history.append({
            'order_id': order['Order_ID'],
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
    restaurant_id = cart[0]['Restaurant_ID'] if cart else None
    restaurant_name = next((item['Restaurant_Name'] for item in cart if 'Restaurant_Name' in item), "Unknown")
    tip_input = request.form.get('tip', '0')

    try:
        tip = float(tip_input)
    except ValueError:
        tip = 0.0

    items_list = []
    restaurant_total = 0.0

    for item in cart:
        price = float(item['Price'])
        subtotal = price * item['Quantity']
        restaurant_total += subtotal
        items_list.append({
            'Item': item['Item'],
            'Price': price,
            'Quantity': item['Quantity'],
            'Subtotal': subtotal
        })

    # Insert into orderrequest without R_Address and C_Address
    conn = database_connect()
    cursor = conn.cursor()

    # Get customer name only
    c_name = session.get('user') or 'Unknown'


    for item in items_list:
        cursor.execute("""
            INSERT INTO orderrequest (Order_ID, R_name, C_Name, Timestamp, Fees, Tip, Order_R_Status, Order_D_Status)
            VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s)
        """, (
            random.randint(1000, 9999),     # Order_ID (can be improved later)
            restaurant_name,
            c_name,
            restaurant_total,
            tip,
            'requested',
            'Waiting For Assignment'
        ))

    conn.commit()
    cursor.close()
    conn.close()

    # Clear cart
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



@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

if __name__ == '__main__':
    app.run(debug=True)
