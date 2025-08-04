from flask import Flask, render_template, request, session, url_for, redirect, flash
import sqlite3
from werkzeug.utils import secure_filename
import os

app = Flask(__name__,  template_folder='.', static_folder='static')
app.secret_key = "f2g10337"

ufolder = 'static'
app.config['UPLOAD_FOLDER'] = ufolder
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])
ext = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ext

def connect_db():
    conn = sqlite3.connect('fy.db',timeout=5)
    return conn

@app.before_request
def set_default_session():
    if "user" not in session:
        session["user"] = None
    if "usertype" not in session:
        session["usertype"] = None
    if "return" not in session:
        session["return"] = None

@app.route("/", methods=["GET","POST"])
def home():
    return render_template("home.html")

@app.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if request.method == "POST":
        email = request.form["email"]
        passwd = request.form["password"]
        user_type = request.form["signinUserType"]

        conn = connect_db()
        cursor = conn.cursor()

        if user_type == "customer":
            cursor.execute("SELECT customer_id FROM customers WHERE email=? AND password=?", (email, passwd))
        elif user_type == "farmer":
            cursor.execute("SELECT farmer_id FROM farmers WHERE email=? AND password=?", (email, passwd))
        else:
            return "Invalid user type", 400

        result = cursor.fetchone()
        conn.close()

        if result:
            session["user"] = result[0]
            session["usertype"] = user_type
            return redirect(session.get("return", "/"))  
        else:
            return "Invalid credentials", 401  

    return "Invalid request method", 405


@app.route("/sign-up",methods=["GET","POST"])
def sign_up():
    email = request.form["email"]
    passwd = request.form["password"]
    type = request.form["signupUserType"]
    name = request.form["name"]
    return render_template("compro.html",email=email,passwd=passwd,user_type=type,name=name)

@app.route("/complete_profile", methods=["GET", "POST"])
def complete_profile():
    if request.method == "POST":
        user_type = request.form["user_type"]
        name = request.form["name"]
        email = request.form["email"]
        passwd = request.form["passwd"]
        add1 = request.form["address_line1"]
        add2 = request.form.get("address_line2", "")
        city = request.form["city"]
        state = request.form["state"]
        pin = request.form["pincode"]

        conn = connect_db()
        cursor = conn.cursor()

        if user_type == "farmer":
            farm_name = request.form["farm_name"]
            est = request.form.get("established_date", None)
            about = request.form.get("about", "")

            cursor.execute("""
                INSERT INTO farmers (
                    farmer_name, email, password,
                    farm_name, address_line1, address_line2,
                    city, state, pincode,
                    about, established_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, email, passwd,
                farm_name, add1, add2,
                city, state, pin,
                about, est
            ))
            session["usertype"] = "farmer"
            session["user"] = cursor.lastrowid

        else:  # customer
            phone = request.form.get("phone_number", "")

            cursor.execute("""
                INSERT INTO customers (
                    full_name, email, password,
                    phone_number, address_line1, address_line2,
                    city, state, pincode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, email, passwd,
                phone, add1, add2,
                city, state, pin
            ))
            session["usertype"] = "customer"
            session["user"] = cursor.lastrowid

    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/user",methods=["GET","POST"])
def user():
    if session["user"] is None:
        session["return"] = "/user"
        return render_template("signin.html")
    
    if session["usertype"]=="farmer":
        return redirect("/farmer-dashboard")
    else:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE customer_id=?",(session["user"],))
        result = cursor.fetchone()
        cursor.execute("SELECT * FROM orders WHERE user_id = ?", (session["user"],))
        orders = cursor.fetchall()
        conn.close()
        return render_template("user.html",user=result, orders = orders)
    

@app.route("/farmer-dashboard", methods=["GET","POST"])
def farmer_dashboard():
    if session["user"] is None:
        session["return"] = "/farmer-dashboard"
        return render_template("signin.html")
    elif session["usertype"] == "Customer":
        return redirect("/user")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM farmers WHERE farmer_id=?",(session["user"],))
    farmer = cursor.fetchone()
    cursor.execute("SELECT * FROM products WHERE farmer_id=?",(session["user"],))
    products = cursor.fetchall()
    cursor.execute("""
        SELECT order_items.*, products.*
        FROM order_items
        JOIN products ON order_items.product_id = products.product_id
        WHERE products.farmer_id = ?
    """, (session["user"],))

    orders = cursor.fetchall()

    conn.close()
    return render_template("farmer_dash.html", farmer=farmer, products=products, orders=orders)

@app.route("/add-product",methods=["GET","POST"])
def add_product():
    id = request.form["id"]
    name = request.form['name']
    desc = request.form['description']
    price = request.form['price']
    stock = request.form['stock_quantity']
    category_id = request.form['category']
    image = request.files['image']
    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO products(farmer_id, name, description, price, stock_quantity, category, image_url)
            VALUES (?,?,?,?,?,?,?)''',(id,name,desc,price, stock, category_id, f"static/{filename}")
        )
        conn.commit()
        conn.close()

        flash('Category added successfully!', 'success')
    else:
        flash('Invalid image format. Please upload a PNG or JPG.', 'danger')

    return redirect("/farmer-dashboard")




@app.route("/products",methods=["GET","POST"])
def products():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return render_template("products.html", products=products)

@app.route("/add-to-cart",methods=["GET","POST"])
def add_to_cart():
    product_id = request.args.get('product_id')
    quantity = request.args.get('quantity', default=1, type=int)
    if session["user"] is None:
        session["return"] = "/add-to-cart"
        return redirect("/sign-in")
    conn = connect_db()
    cursor = conn.cursor()
    print(product_id, quantity)
    cursor.execute("INSERT INTO wishlist(user_id, product_id, quantity) VALUES (?,?,?)",(session["user"],product_id ,quantity))
    conn.commit()
    conn.close()
    return redirect("/products")

@app.route("/cart",methods=["GET","POST"])
def cart():
    if session["user"] is None:
        session["return"] = "/cart"
        return redirect("/sign-in")
    conn = connect_db()
    cursor = conn.cursor() 
    cursor.execute("SELECT W.wishlist_id, W.product_id, P.price, P.name, P.image_url, W.quantity FROM wishlist W JOIN products P ON W.product_id = P.product_id WHERE W.user_id = ?", (session["user"],))
    items = cursor.fetchall() 
    return render_template("cart.html", items = items)

@app.route("/remove_from_cart",methods=["GET","POST"])
def remove_from_cart():
    id = request.form["item_id"]
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wishlist WHERE wishlist_id = ?",(id,))
    conn.commit()
    conn.close()
    print(id)
    return redirect("/cart")

@app.route("/checkout",methods=["GET","POST"])
def checkout():
    total = request.form["total_price"]
    subtotal = request.form["subtotal"]
    tax = request.form["tax"]
    shipping = request.form["shipping"]
    items = request.form["total_items"]
    return render_template("checkout.html",total=total, subtotal=subtotal, tax=tax, shipping=shipping)

@app.route("/order",methods=["GET","POST"])
def order():
    first_name = request.args.get("first-name")
    last_name = request.args.get("last-name")
    email = request.args.get("email")
    address = request.args.get("address")
    city = request.args.get("city")
    state = request.args.get("state")
    postal = request.args.get("postal-code")
    country = request.args.get("country")
    phone = request.args.get("phone")
    payment = request.args.get("payment")
    amount = request.args.get("amount")
    tid = None
    if payment == 'upi':
        tid = request.args.get("tid")
    
    conn = connect_db()
    cursor = conn.cursor()
    if payment=='upi':
        cursor.execute('''INSERT INTO orders (user_id, first_name, last_name, email, address, city, state, postal, country, phone, pay_method, pay_status, amount, t_id, order_date)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,DATE('now'))''',
                    (session["user"], first_name,last_name,email,address,city,state,postal,country,phone,payment,"Pending",amount,tid))
        conn.commit() 
    else:
        cursor.execute('''INSERT INTO orders (user_id, first_name, last_name, email, address, city, state, postal, country, phone, pay_method, pay_status, amount)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (session["user"], first_name,last_name,email,address,city,state,postal,country,phone,payment,"Pending",amount))
        conn.commit()
    cursor.execute("SELECT order_id FROM orders ORDER BY order_id DESC LIMIT 1")
    order_id = cursor.fetchone()[0]
    cursor.execute("SELECT * from wishlist WHERE user_id=?",(session["user"],))
    items = cursor.fetchall()
    for i in items:
        print(i)
        cursor.execute("INSERT INTO order_items VALUES (?,?,?)",(order_id,i[2],i[3]))
        conn.commit()
    cursor.execute("DELETE FROM wishlist WHERE user_id=?",(session["user"],))
    conn.commit()
    conn.close()
    return render_template("confirmation.html")

@app.route("/order-details",methods=["GET","POST"])
def order_details():
    id = request.args.get("order_id") if request.method == "GET" else request.form.get("order_id")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT O.product_id, P.name, P.image_url, O.quantity FROM order_items O JOIN products P ON P.product_id = O.product_id WHERE order_id=?",(id,))
    items = cursor.fetchall()
    cursor.execute("SELECT * FROM orders WHERE order_id=?",(id,))
    details = cursor.fetchone()
    conn.close()
    return render_template("orders.html",items=items, details=details)


@app.route("/send_issue", methods=["GET", "POST"])
def send_issue():
    id = request.form["order_id"]
    message = request.form["message"]
    
    conn = connect_db()
    cursor = conn.cursor()
    
    # Save the issue here (optional):
    cursor.execute("INSERT INTO issues (user_id, order_id, issue) VALUES (?, ?, ?)", (session["user"], id, message))  # Replace user_id as needed
    conn.commit()
    conn.close()

    # Redirect with order_id as a query parameter
    return redirect(url_for("order_details", order_id=id))

@app.route("/logout",methods=["GET","POST"])
def logout():
    session["user"] = None
    session["usertype"] = None
    return redirect("/")

@app.route("/change_pass", methods=["GET","POST"])
def change_pass():
    password = request.form["new_password"]
    conn = connect_db() 
    cursor = conn.cursor() 
    cursor.execute("UPDATE customers SET password = ? WHERE customer_id = ?",(password,session["user"]))
    conn.commit()
    conn.close() 
    return redirect("/user")

@app.route("/remove-product", methods=["GET","POST"])
def remove_product():
    id = request.form["id"]
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE product_id=?",(id,))
    conn.commit()
    conn.close()
    return redirect("/farmer-dashboard")



if __name__ == "__main__":
    app.run(debug=True)
