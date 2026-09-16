from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "savings-project-secret-key"

DATABASE = "database.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()

    # =========================
    # USERS TABLE
    # =========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # PERSONAL SAVINGS TABLE
    # =========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS savings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # GROUPS TABLE
    # =========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # GROUP MEMBERS TABLE
    # =========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(group_id, user_id)
        )
    """)

    # =========================
    # GROUP SAVINGS TABLE
    # =========================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_savings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# =========================
# HOME
# =========================

@app.route("/")
def home():

    return render_template("index.html")


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        password = request.form["password"]

        if not name or not phone or not password:
            return "All fields are required.", 400

        password_hash = generate_password_hash(password)

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users (name, phone, password_hash)
                VALUES (?, ?, ?)
                """,
                (name, phone, password_hash)
            )

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return "This phone number is already registered.", 400

        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        phone = request.form["phone"].strip()
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone = ?
            """,
            (phone,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):
          session["user_id"] = user["id"]
          session["user_name"] = user["name"]

          return redirect(url_for("dashboard"))

        return "Incorrect phone number or password.", 401

    return render_template("login.html")


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    # Total savings
    total = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM savings
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()[0]

    # Number of transactions
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM savings
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()[0]

    # Recent transactions
    recent_transactions = conn.execute(
        """
        SELECT amount, created_at
        FROM savings
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        total=total,
        transaction_count=count,
        recent_transactions=recent_transactions
    )


# =========================
# PERSONAL SAVINGS
# =========================

@app.route("/savings", methods=["GET", "POST"])
def savings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":

        amount_text = request.form["amount"].strip()

        if not amount_text:

            conn.close()

            return "Please enter an amount.", 400

        valid_number = amount_text.replace(".", "", 1).isdigit()

        if not valid_number:

            conn.close()

            return "Please enter a valid number.", 400

        amount = float(amount_text)

        if amount <= 0:

            conn.close()

            return "Amount must be greater than 0.", 400

        conn.execute(
            """
            INSERT INTO savings (user_id, amount)
            VALUES (?, ?)
            """,
            (session["user_id"], amount)
        )

        conn.commit()

    records = conn.execute(
        """
        SELECT amount, created_at
        FROM savings
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    total = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM savings
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()[0]

    conn.close()

    return render_template(
        "savings.html",
        records=records,
        total=total
    )


# =========================
# GROUPS
# =========================

@app.route("/group", methods=["GET", "POST"])
def group():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":

        group_name = request.form["group_name"].strip()

        if not group_name:

            conn.close()

            return "Please enter a group name.", 400

        conn.execute(
            """
            INSERT INTO groups (name, owner_id)
            VALUES (?, ?)
            """,
            (group_name, session["user_id"])
        )

        conn.commit()

        conn.close()

        return redirect(url_for("group"))

    groups = conn.execute(
        """
        SELECT id, name, created_at
        FROM groups
        WHERE owner_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "group.html",
        groups=groups
    )


# =========================
# GROUP DETAILS
# =========================

# GROUP DETAILS
@app.route("/group/<int:group_id>")
def group_details(group_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    group = conn.execute(
        """
        SELECT *
        FROM groups
        WHERE id = ? AND owner_id = ?
        """,
        (group_id, session["user_id"])
    ).fetchone()

    if not group:
        conn.close()
        return "Group not found.", 404

    members = conn.execute(
        """
        SELECT
            users.id,
            users.name,
            users.phone,
            group_members.joined_at,
            COALESCE(
                (
                    SELECT SUM(group_savings.amount)
                    FROM group_savings
                    WHERE group_savings.group_id = ?
                    AND group_savings.user_id = users.id
                ),
                0
            ) AS total_savings
        FROM group_members
        JOIN users
        ON users.id = group_members.user_id
        WHERE group_members.group_id = ?
        ORDER BY group_members.joined_at ASC
        """,
        (group_id, group_id)
    ).fetchall()

    # TOTAL GROUP SAVINGS
    total_group_savings = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM group_savings
        WHERE group_id = ?
        """,
        (group_id,)
    ).fetchone()[0]

    # NUMBER OF MEMBERS
    member_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM group_members
        WHERE group_id = ?
        """,
        (group_id,)
    ).fetchone()[0]

    conn.close()

    return render_template(
        "group_details.html",
        group=group,
        members=members,
        total_group_savings=total_group_savings,
        member_count=member_count
    )


# =========================
# ADD MEMBER
# =========================

@app.route(
    "/group/<int:group_id>/add-member",
    methods=["POST"]
)
def add_member(group_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    phone = request.form["phone"].strip()

    conn = get_db()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE phone = ?
        """,
        (phone,)
    ).fetchone()

    if not user:

        conn.close()

        return "User with this phone number does not exist.", 404

    group = conn.execute(
        """
        SELECT id
        FROM groups
        WHERE id = ? AND owner_id = ?
        """,
        (group_id, session["user_id"])
    ).fetchone()

    if not group:

        conn.close()

        return "Group not found.", 404

    try:

        conn.execute(
            """
            INSERT INTO group_members
            (group_id, user_id)
            VALUES (?, ?)
            """,
            (group_id, user["id"])
        )

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()

        return "This user is already a member.", 400

    conn.close()

    return redirect(
        url_for(
            "group_details",
            group_id=group_id
        )
    )


# =========================
# REMOVE MEMBER
# =========================

@app.route(
    "/group/<int:group_id>/remove-member/<int:user_id>",
    methods=["POST"]
)
def remove_member(group_id, user_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    group = conn.execute(
        """
        SELECT id
        FROM groups
        WHERE id = ? AND owner_id = ?
        """,
        (group_id, session["user_id"])
    ).fetchone()

    if not group:

        conn.close()

        return "Group not found.", 404

    if user_id == session["user_id"]:

        conn.close()

        return "You cannot remove the group owner.", 400

    conn.execute(
        """
        DELETE FROM group_members
        WHERE group_id = ?
        AND user_id = ?
        """,
        (group_id, user_id)
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for(
            "group_details",
            group_id=group_id
        )
    )


# =========================
# MEMBER SAVINGS
# =========================

@app.route(
    "/group/<int:group_id>/member/<int:user_id>/savings",
    methods=["GET", "POST"]
)
def member_savings(group_id, user_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    group = conn.execute(
        """
        SELECT id, name
        FROM groups
        WHERE id = ? AND owner_id = ?
        """,
        (group_id, session["user_id"])
    ).fetchone()

    if not group:

        conn.close()

        return "Group not found.", 404

    member = conn.execute(
        """
        SELECT
            users.id,
            users.name,
            users.phone
        FROM group_members
        JOIN users
        ON users.id = group_members.user_id
        WHERE group_members.group_id = ?
        AND group_members.user_id = ?
        """,
        (group_id, user_id)
    ).fetchone()

    if not member:

        conn.close()
        return "Member not found.", 404

    if request.method == "POST":

        amount_text = request.form["amount"].strip()

        if not amount_text:

            conn.close()

            return "Please enter an amount.", 400

        valid_number = amount_text.replace(".", "", 1).isdigit()

        if not valid_number:

            conn.close()

            return "Please enter a valid number.", 400

        amount = float(amount_text)

        if amount <= 0:

            conn.close()

            return "Amount must be greater than 0.", 400

        conn.execute(
            """
            INSERT INTO group_savings
            (group_id, user_id, amount)
            VALUES (?, ?, ?)
            """,
            (group_id, user_id, amount)
        )

        conn.commit()

    records = conn.execute(
        """
        SELECT amount, created_at
        FROM group_savings
        WHERE group_id = ?
        AND user_id = ?
        ORDER BY created_at DESC
        """,
        (group_id, user_id)
    ).fetchall()

    total = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM group_savings
        WHERE group_id = ?
        AND user_id = ?
        """,
        (group_id, user_id)
    ).fetchone()[0]

    conn.close()

    return render_template(
        "member_savings.html",
        group=group,
        member=member,
        records=records,
        total=total
    )


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================
# RUN APP
# =========================

if __name__ == "__main__":

    init_db()

    app.run(host="0.0.0.0", port=5000, debug=True)