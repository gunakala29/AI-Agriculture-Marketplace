from flask import Flask, render_template, request, redirect, session
import sqlite3
import joblib
import os

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static"
)

app.secret_key = "agriculture-marketplace-secret-key"

DATABASE = os.path.join(
    os.path.dirname(__file__),
    "../data/agriculture.db"
)


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity TEXT NOT NULL,
            location TEXT NOT NULL,
            farmer_id INTEGER NOT NULL,
            FOREIGN KEY (farmer_id)
            REFERENCES farmers(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            farmer_id INTEGER NOT NULL,
            buyer_name TEXT NOT NULL,
            buyer_email TEXT NOT NULL,
            buyer_phone TEXT NOT NULL,
            quantity TEXT NOT NULL,
            delivery_address TEXT NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (farmer_id) REFERENCES farmers(id)
        )
    """)

    connection.commit()
    connection.close()


create_database()


model_path = os.path.join(
    os.path.dirname(__file__),
    "../models/crop_model.pkl"
)

model = joblib.load(model_path)


# ---------------------------------------------------------
# HOME / MARKETPLACE
# ---------------------------------------------------------

@app.route("/")
def home():

    search = request.args.get("search", "").strip()
    location = request.args.get("location", "").strip()

    connection = get_db_connection()

    query = """
        SELECT
            products.*,
            farmers.name AS farmer_name,
            farmers.email AS farmer_email,
            farmers.phone AS farmer_phone
        FROM products
        JOIN farmers
        ON products.farmer_id = farmers.id
        WHERE 1 = 1
    """

    parameters = []

    if search:

        query += """
            AND (
                products.name LIKE ?
                OR products.location LIKE ?
            )
        """

        search_value = "%" + search + "%"

        parameters.append(search_value)
        parameters.append(search_value)

    if location:

        query += """
            AND products.location LIKE ?
        """

        parameters.append("%" + location + "%")

    query += """
        ORDER BY products.id DESC
    """

    products = connection.execute(
        query,
        parameters
    ).fetchall()

    locations = connection.execute("""
        SELECT DISTINCT location
        FROM products
        ORDER BY location
    """).fetchall()

    connection.close()

    return render_template(
        "index.html",
        products=products,
        locations=locations,
        search=search,
        selected_location=location
    )


# ---------------------------------------------------------
# PRODUCT DETAILS
# ---------------------------------------------------------

@app.route("/product/<int:product_id>")
def product_details(product_id):

    connection = get_db_connection()

    product = connection.execute("""
        SELECT
            products.*,
            farmers.name AS farmer_name,
            farmers.email AS farmer_email,
            farmers.phone AS farmer_phone
        FROM products
        JOIN farmers
        ON products.farmer_id = farmers.id
        WHERE products.id = ?
    """, (
        product_id,
    )).fetchone()

    connection.close()

    if product is None:
        return "Product not found.", 404

    return render_template(
        "product_details.html",
        product=product
    )


# ---------------------------------------------------------
# PURCHASE REQUEST
# ---------------------------------------------------------

@app.route("/purchase-request/<int:product_id>")
def purchase_request(product_id):

    connection = get_db_connection()

    product = connection.execute("""
        SELECT
            products.*,
            farmers.name AS farmer_name
        FROM products
        JOIN farmers
        ON products.farmer_id = farmers.id
        WHERE products.id = ?
    """, (
        product_id,
    )).fetchone()

    connection.close()

    if product is None:
        return "Product not found.", 404

    return render_template(
        "purchase_request.html",
        product=product
    )


@app.route("/submit-purchase-request/<int:product_id>", methods=["POST"])
def submit_purchase_request(product_id):

    buyer_name = request.form["buyer_name"].strip()
    buyer_email = request.form["buyer_email"].strip().lower()
    buyer_phone = request.form["buyer_phone"].strip()
    quantity = request.form["quantity"].strip()
    delivery_address = request.form["delivery_address"].strip()
    message = request.form.get("message", "").strip()

    if not buyer_name or not buyer_email or not buyer_phone:
        return "Please fill all required buyer details.", 400

    if not quantity or not delivery_address:
        return "Please enter quantity and delivery address.", 400

    if not buyer_phone.isdigit() or len(buyer_phone) != 10:
        return "Please enter a valid 10-digit phone number.", 400

    connection = get_db_connection()

    product = connection.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (
        product_id,
    )).fetchone()

    if product is None:
        connection.close()
        return "Product not found.", 404

    connection.execute("""
        INSERT INTO purchase_requests
        (
            product_id,
            farmer_id,
            buyer_name,
            buyer_email,
            buyer_phone,
            quantity,
            delivery_address,
            message,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        product_id,
        product["farmer_id"],
        buyer_name,
        buyer_email,
        buyer_phone,
        quantity,
        delivery_address,
        message,
        "Pending"
    ))

    connection.commit()
    connection.close()

    return render_template(
        "purchase_success.html",
        product=product
    )


# ---------------------------------------------------------
# FARMER REGISTRATION
# ---------------------------------------------------------

@app.route("/register")
def register():

    return render_template(
        "register.html"
    )


@app.route("/register", methods=["POST"])
def register_farmer():

    name = request.form["name"].strip()
    email = request.form["email"].strip().lower()
    phone = request.form["phone"].strip()
    password = request.form["password"]

    if not name or not email or not phone or not password:

        return render_template(
            "register.html",
            error="Please fill all the fields."
        )

    if not phone.isdigit() or len(phone) != 10:

        return render_template(
            "register.html",
            error="Please enter a valid 10-digit phone number."
        )

    hashed_password = generate_password_hash(
        password
    )

    connection = get_db_connection()

    existing_farmer = connection.execute("""
        SELECT *
        FROM farmers
        WHERE email = ?
    """, (
        email,
    )).fetchone()

    if existing_farmer:

        connection.close()

        return render_template(
            "register.html",
            error="Email already registered. Please login."
        )

    connection.execute("""
        INSERT INTO farmers
        (
            name,
            email,
            phone,
            password
        )
        VALUES (?, ?, ?, ?)
    """, (
        name,
        email,
        phone,
        hashed_password
    ))

    connection.commit()
    connection.close()

    return redirect("/login")


# ---------------------------------------------------------
# FARMER LOGIN
# ---------------------------------------------------------

@app.route("/login")
def login():

    return render_template(
        "login.html"
    )


@app.route("/login", methods=["POST"])
def login_farmer():

    email = request.form["email"].strip().lower()
    password = request.form["password"]

    connection = get_db_connection()

    farmer = connection.execute("""
        SELECT *
        FROM farmers
        WHERE email = ?
    """, (
        email,
    )).fetchone()

    connection.close()

    if farmer is None:

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    if not check_password_hash(
        farmer["password"],
        password
    ):

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    session["farmer_id"] = farmer["id"]
    session["farmer_name"] = farmer["name"]

    return redirect("/dashboard")


# ---------------------------------------------------------
# FARMER DASHBOARD
# ---------------------------------------------------------

@app.route("/dashboard")
def dashboard():

    if "farmer_id" not in session:

        return redirect("/login")

    farmer_id = session["farmer_id"]

    connection = get_db_connection()

    products = connection.execute("""
        SELECT *
        FROM products
        WHERE farmer_id = ?
        ORDER BY id DESC
    """, (
        farmer_id,
    )).fetchall()

    purchase_requests = connection.execute("""
        SELECT
            purchase_requests.*,
            products.name AS product_name,
            products.price AS product_price
        FROM purchase_requests
        JOIN products
        ON purchase_requests.product_id = products.id
        WHERE purchase_requests.farmer_id = ?
        ORDER BY purchase_requests.id DESC
    """, (
        farmer_id,
    )).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        products=products,
        purchase_requests=purchase_requests,
        farmer_name=session["farmer_name"]
    )


# ---------------------------------------------------------
# ADD PRODUCT
# ---------------------------------------------------------

@app.route("/add-product", methods=["POST"])
def add_product():

    if "farmer_id" not in session:

        return redirect("/login")

    name = request.form["name"].strip()
    price = request.form["price"]
    quantity = request.form["quantity"].strip()
    location = request.form["location"].strip()

    farmer_id = session["farmer_id"]

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO products
        (
            name,
            price,
            quantity,
            location,
            farmer_id
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        name,
        price,
        quantity,
        location,
        farmer_id
    ))

    connection.commit()
    connection.close()

    return redirect("/dashboard")


# ---------------------------------------------------------
# EDIT PRODUCT
# ---------------------------------------------------------

@app.route("/edit-product/<int:product_id>")
def edit_product(product_id):

    if "farmer_id" not in session:

        return redirect("/login")

    connection = get_db_connection()

    product = connection.execute("""
        SELECT *
        FROM products
        WHERE id = ?
        AND farmer_id = ?
    """, (
        product_id,
        session["farmer_id"]
    )).fetchone()

    connection.close()

    if product is None:

        return "Product not found or access denied.", 404

    return render_template(
        "edit_product.html",
        product=product
    )


# ---------------------------------------------------------
# UPDATE PRODUCT
# ---------------------------------------------------------

@app.route("/update-product/<int:product_id>", methods=["POST"])
def update_product(product_id):

    if "farmer_id" not in session:

        return redirect("/login")

    name = request.form["name"].strip()
    price = request.form["price"]
    quantity = request.form["quantity"].strip()
    location = request.form["location"].strip()

    connection = get_db_connection()

    connection.execute("""
        UPDATE products
        SET
            name = ?,
            price = ?,
            quantity = ?,
            location = ?
        WHERE id = ?
        AND farmer_id = ?
    """, (
        name,
        price,
        quantity,
        location,
        product_id,
        session["farmer_id"]
    ))

    connection.commit()
    connection.close()

    return redirect("/dashboard")


# ---------------------------------------------------------
# DELETE PRODUCT
# ---------------------------------------------------------

@app.route("/delete-product/<int:product_id>", methods=["POST"])
def delete_product(product_id):

    if "farmer_id" not in session:

        return redirect("/login")

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM products
        WHERE id = ?
        AND farmer_id = ?
    """, (
        product_id,
        session["farmer_id"]
    ))

    connection.commit()
    connection.close()

    return redirect("/dashboard")


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ---------------------------------------------------------
# AI CROP ASSISTANCE
# ---------------------------------------------------------

@app.route("/crop-assistance")
def crop_assistance():

    return render_template(
        "crop_assistance.html"
    )


@app.route("/predict", methods=["POST"])
def predict():

    try:

        temperature = float(
            request.form["temperature"]
        )

        humidity = float(
            request.form["humidity"]
        )

        rainfall = float(
            request.form["rainfall"]
        )

        prediction = model.predict([
            [
                temperature,
                humidity,
                rainfall
            ]
        ])[0]

        return render_template(
            "crop_assistance.html",
            prediction=prediction
        )

    except (ValueError, KeyError):

        return render_template(
            "crop_assistance.html",
            error="Please enter valid numbers."
        )


# ---------------------------------------------------------
# RUN APPLICATION
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True
    )
