from flask import (
    Flask, request, redirect, render_template_string,
    flash, session, send_file, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
from pathlib import Path
from io import BytesIO
import os
import html
import shutil
import urllib.parse

# ============================================================
# R.K JEWELERS - COMPLETE SINGLE FILE VERSION
# Developer: KRISHNA
# ============================================================

APP_DIR = Path(__file__).resolve().parent
DB = APP_DIR / "rk_jewellers.db"
BACKUP_DIR = APP_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "RK_SECRET_KEY",
    "rk-jewellers-krishna-secret-key-2026"
)

# ============================================================
# LOGIN
# ============================================================

ADMIN_USER = os.environ.get("RK_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("RK_ADMIN_PASSWORD", "1234")

ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)


# ============================================================
# DATABASE
# ============================================================

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def add_column_if_missing(con, table, column, definition):
    existing = {
        row["name"]
        for row in con.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in existing:
        con.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def setup():

    con = db()

    # --------------------------------------------------------
    # CUSTOMERS
    # --------------------------------------------------------

    con.execute("""
        CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT DEFAULT '',
            address TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------
    # JOBS
    # --------------------------------------------------------

    con.execute("""
        CREATE TABLE IF NOT EXISTS jobs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            jewellery TEXT NOT NULL,
            work TEXT NOT NULL DEFAULT 'Other',
            status TEXT NOT NULL DEFAULT 'Pending',

            maal_aaya TEXT DEFAULT '',
            maal_diyaa TEXT DEFAULT '',

            gross_weight REAL DEFAULT 0,
            nag_weight REAL DEFAULT 0,
            total_weight REAL DEFAULT 0,
            loss REAL DEFAULT 0,
            final_weight REAL DEFAULT 0,

            stone_weight REAL DEFAULT 0,
            net_weight REAL DEFAULT 0,

            taanch REAL DEFAULT 0,
            quantity INTEGER DEFAULT 1,

            work_amount REAL DEFAULT 0,
            notes TEXT DEFAULT '',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(customer_id)
                REFERENCES customers(id)
                ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # PAYMENTS
    # --------------------------------------------------------

    con.execute("""
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            mode TEXT NOT NULL DEFAULT 'Cash',
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(customer_id)
                REFERENCES customers(id)
                ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # OLD DATABASE UPGRADE
    # --------------------------------------------------------

    customer_columns = {
        "mobile": "TEXT DEFAULT ''",
        "address": "TEXT DEFAULT ''",
        "notes": "TEXT DEFAULT ''",
        "active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT"
    }

    for col, definition in customer_columns.items():
        add_column_if_missing(
            con,
            "customers",
            col,
            definition
        )

    job_columns = {
        "customer_id": "INTEGER",
        "date": "TEXT",
        "jewellery": "TEXT",
        "work": "TEXT DEFAULT 'Other'",
        "status": "TEXT DEFAULT 'Pending'",
        "maal_aaya": "TEXT DEFAULT ''",
        "maal_diyaa": "TEXT DEFAULT ''",
        "gross_weight": "REAL DEFAULT 0",
        "nag_weight": "REAL DEFAULT 0",
        "total_weight": "REAL DEFAULT 0",
        "loss": "REAL DEFAULT 0",
        "final_weight": "REAL DEFAULT 0",
        "stone_weight": "REAL DEFAULT 0",
        "net_weight": "REAL DEFAULT 0",
        "taanch": "REAL DEFAULT 0",
        "quantity": "INTEGER DEFAULT 1",
        "work_amount": "REAL DEFAULT 0",
        "notes": "TEXT DEFAULT ''",
        "created_at": "TEXT"
    }

    for col, definition in job_columns.items():
        add_column_if_missing(
            con,
            "jobs",
            col,
            definition
        )

    payment_columns = {
        "customer_id": "INTEGER",
        "date": "TEXT",
        "amount": "REAL DEFAULT 0",
        "mode": "TEXT DEFAULT 'Cash'",
        "note": "TEXT DEFAULT ''",
        "created_at": "TEXT"
    }

    for col, definition in payment_columns.items():
        add_column_if_missing(
            con,
            "payments",
            col,
            definition
        )

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------

    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_customer
        ON jobs(customer_id)
    """)

    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_date
        ON jobs(date)
    """)

    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_payments_customer
        ON payments(customer_id)
    """)

    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_payments_date
        ON payments(date)
    """)

    con.commit()
    con.close()


# ============================================================
# HELPERS
# ============================================================

def money(value):
    return "₹ {:,.2f}".format(float(value or 0))


def esc(value):
    return html.escape(
        "" if value is None else str(value)
    )


def parse_float(name, default=0.0):

    raw = request.form.get(name, "").strip()

    if raw == "":
        return default

    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"{name} me valid number dalo."
        )


def parse_int(name, default=1):

    raw = request.form.get(name, "").strip()

    if raw == "":
        return default

    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"{name} me valid number dalo."
        )


def login_required(view):

    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("logged_in"):
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped


# ============================================================
# BASE HTML
# ============================================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="hi">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>{{ title }} - R.K JEWELERS</title>

<style>

*{
    box-sizing:border-box;
}

body{
    margin:0;
    font-family:Arial,Helvetica,sans-serif;
    background:
        radial-gradient(circle at top left,#fff8d9,transparent 35%),
        linear-gradient(135deg,#fffaf0,#ead19a);
    color:#2d1b0e;
}

header{
    background:
        linear-gradient(135deg,#1c0e05,#633713,#241006);
    color:white;
    padding:20px;
    text-align:center;
    border-bottom:5px solid #f2c94c;
    box-shadow:0 5px 25px #0005;
}

header h1{
    margin:0;
    color:#ffe58a;
    font-size:34px;
    letter-spacing:2px;
}

header p{
    margin:6px 0 0;
    color:#fff5d1;
}

.layout{
    display:flex;
    min-height:calc(100vh - 110px);
}

nav{
    width:250px;
    background:
        linear-gradient(180deg,#241107,#3b1d0b);
    padding:15px;
    flex:none;
}

nav a{
    display:block;
    text-decoration:none;
    color:white;
    padding:13px;
    margin:7px 0;
    border-radius:11px;
    font-weight:bold;
    transition:.2s;
}

nav a:hover{
    background:linear-gradient(90deg,#f2c94c,#d99b18);
    color:#241107;
    transform:translateX(3px);
}

.userbox{
    color:#ffe58a;
    padding:10px;
    border-bottom:1px solid #77512d;
    margin-bottom:10px;
    font-size:13px;
}

main{
    flex:1;
    padding:22px;
    max-width:1800px;
}

.mobile-menu{
    display:none;
    background:#241107;
    padding:10px;
    text-align:center;
}

.mobile-menu button{
    width:100%;
}

.cardbox{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:16px;
}

.card{
    background:white;
    padding:20px;
    border-radius:17px;
    box-shadow:0 10px 30px #76501f33;
    border-top:5px solid #d6a52e;
}

.card h3{
    margin:0;
    color:#777;
    font-size:13px;
}

.card b{
    display:block;
    font-size:25px;
    margin-top:8px;
}

.panel{
    background:#fff;
    padding:20px;
    margin:18px 0;
    border-radius:17px;
    box-shadow:0 10px 30px #76501f33;
}

.form{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:13px;
}

.form-group{
    margin-bottom:15px;
}

.form-grid{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:14px;
}

.full-width{
    grid-column:1/-1;
}

input,
select,
textarea{
    width:100%;
    padding:12px;
    border:1px solid #d9c39b;
    border-radius:10px;
    font-size:15px;
    background:#fffdf8;
    outline:none;
}

input:focus,
select:focus,
textarea:focus{
    border-color:#d4a52e;
    box-shadow:0 0 0 3px #d4a52e22;
}

textarea{
    min-height:85px;
    resize:vertical;
}

label{
    display:block;
    font-weight:bold;
    font-size:13px;
    margin-bottom:5px;
}

button,
.btn{
    border:0;
    padding:11px 15px;
    border-radius:10px;
    background:#d6a52e;
    color:#241309;
    font-weight:bold;
    cursor:pointer;
    text-decoration:none;
    display:inline-block;
}

button:hover,
.btn:hover{
    opacity:.9;
    transform:translateY(-1px);
}

.green{
    background:#198754 !important;
    color:white !important;
}

.red{
    background:#c52f3c !important;
    color:white !important;
}

.blue{
    background:#2864c7 !important;
    color:white !important;
}

.whatsapp{
    background:#25D366 !important;
    color:white !important;
}

.gray{
    background:#6c757d !important;
    color:white !important;
}

.purple{
    background:#7436c8 !important;
    color:white !important;
}

.small{
    padding:8px 10px;
    font-size:12px;
}

.msg{
    background:#dff5e7;
    color:#17663c;
    padding:13px;
    border-radius:11px;
    margin-bottom:15px;
    font-weight:bold;
}

.err{
    background:#ffe1e4;
    color:#8b1e2b;
    padding:13px;
    border-radius:11px;
    margin-bottom:15px;
    font-weight:bold;
}

.table{
    overflow-x:auto;
}

table{
    width:100%;
    border-collapse:collapse;
    min-width:850px;
}

th{
    background:#45240f;
    color:#ffe58a;
    padding:12px;
    text-align:left;
}

td{
    padding:10px;
    border-bottom:1px solid #eee2c9;
    vertical-align:top;
}

tr:hover td{
    background:#fffaf0;
}

.badge{
    display:inline-block;
    padding:5px 9px;
    border-radius:999px;
    background:#eee;
    font-size:12px;
    font-weight:bold;
}

.badge.green{
    background:#dff3e6 !important;
    color:#17663c !important;
}

.badge.yellow{
    background:#fff1bf !important;
    color:#795c00 !important;
}

.badge.red{
    background:#ffe2e4 !important;
    color:#8b1e2b !important;
}

.muted{
    color:#777;
}

.balance{
    font-size:28px;
    font-weight:bold;
}

.debit{
    color:#b52d38;
    font-weight:bold;
}

.credit{
    color:#198754;
    font-weight:bold;
}

.actions{
    display:flex;
    gap:6px;
    flex-wrap:wrap;
}

.toolbar{
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    align-items:end;
}

.toolbar .field{
    min-width:180px;
}

.two{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:15px;
}

.login{
    max-width:430px;
    margin:70px auto;
}

.login .panel{
    padding:30px;
}

.hero{
    background:
        linear-gradient(135deg,#291308,#8b541e);
    color:white;
    border-radius:20px;
    padding:28px;
    box-shadow:0 15px 35px #0003;
}

.hero h2{
    color:#ffe58a;
    margin-top:0;
}

.weight-box{
    background:linear-gradient(135deg,#fff8d7,#fff);
    border:2px solid #e3bd4b;
    padding:16px;
    border-radius:15px;
}

.weight-result{
    font-weight:bold;
    background:#fff4bf;
}

.search-box{
    display:flex;
    gap:10px;
}

.search-box input{
    flex:1;
}

@media(max-width:1000px){

    .cardbox{
        grid-template-columns:repeat(2,1fr);
    }

    .form,
    .form-grid{
        grid-template-columns:repeat(2,1fr);
    }
}

@media(max-width:700px){

    .mobile-menu{
        display:block;
    }

    .layout{
        display:block;
    }

    nav{
        width:100%;
        display:none;
    }

    nav.show{
        display:block;
    }

    main{
        padding:10px;
    }

    .cardbox{
        grid-template-columns:repeat(2,1fr);
        gap:8px;
    }

    .card{
        padding:14px;
    }

    .card b{
        font-size:18px;
    }

    .form,
    .form-grid,
    .two{
        grid-template-columns:1fr;
    }

    .panel{
        padding:14px;
    }

    header h1{
        font-size:25px;
    }

    .toolbar .field{
        min-width:100%;
    }

    .search-box{
        flex-direction:column;
    }
}

@media print{

    header,
    nav,
    .mobile-menu,
    .no-print{
        display:none !important;
    }

    body{
        background:white;
    }

    main{
        max-width:none;
        padding:0;
    }

    .panel,
    .card{
        box-shadow:none;
    }
}

</style>

</head>

<body>

<header>

<h1>R.K JEWELERS</h1>

<p>
JEWELLERY JOB WORK • CUSTOMER LEDGER • PAYMENT
</p>

</header>

<div class="mobile-menu">

<button onclick="
document.getElementById('nav').classList.toggle('show')
">
☰ MENU
</button>

</div>

<div class="layout">

<nav id="nav">

{% if session.get('logged_in') %}

<div class="userbox">
Logged in as {{ session.get('user') }}
</div>

<a href="{{ url_for('home') }}">🏠 Dashboard</a>
<a href="{{ url_for('customers') }}">👥 Customers</a>
<a href="{{ url_for('jobs') }}">💎 Job Entry</a>
<a href="{{ url_for('payments') }}">💰 Payment Entry</a>
<a href="{{ url_for('ledger') }}">📒 Customer Ledger</a>
<a href="{{ url_for('search') }}">🔎 Customer Search</a>
<a href="{{ url_for('reports') }}">📊 Reports</a>
<a href="{{ url_for('backup') }}">💾 Backup Database</a>
<a href="{{ url_for('restore') }}">♻️ Restore Backup</a>
<a href="{{ url_for('about') }}">ℹ️ Shop Information</a>
<a href="{{ url_for('logout') }}">🚪 Logout</a>

{% endif %}

</nav>

<main>

{% with messages=get_flashed_messages(category_filter=['success']) %}

{% for m in messages %}

<div class="msg">
{{ m }}
</div>

{% endfor %}

{% endwith %}

{% with messages=get_flashed_messages(category_filter=['error']) %}

{% for m in messages %}

<div class="err">
{{ m }}
</div>

{% endfor %}

{% endwith %}

{{ body|safe }}

</main>

</div>

</body>

</html>
"""


def page(title, body):
    return render_template_string(
        BASE_HTML,
        title=title,
        body=body
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        user = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if (
            user == ADMIN_USER
            and check_password_hash(
                ADMIN_PASSWORD_HASH,
                password
            )
        ):

            session.clear()
            session["logged_in"] = True
            session["user"] = user

            return redirect(
                url_for("home")
            )

        flash(
            "Wrong username ya password.",
            "error"
        )

    body = """
    <div class="login">

        <div class="panel">

            <h2>🔐 R.K JEWELERS LOGIN</h2>

            <p class="muted">
                Secure Jewellery Management System
            </p>

            <form method="post">

                <label>Username</label>

                <input
                    name="username"
                    required
                    autocomplete="username"
                >

                <br><br>

                <label>Password / PIN</label>

                <input
                    type="password"
                    name="password"
                    required
                    autocomplete="current-password"
                >

                <br><br>

                <button class="green" type="submit">
                    🔐 LOGIN
                </button>

            </form>

        </div>

    </div>
    """

    return page("Login", body)


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
@login_required
def home():

    con = db()

    customers_count = con.execute("""
        SELECT COUNT(*) c
        FROM customers
        WHERE active=1
    """).fetchone()["c"]

    jobs_count = con.execute("""
        SELECT COUNT(*) c
        FROM jobs
    """).fetchone()["c"]

    total_work = con.execute("""
        SELECT COALESCE(SUM(work_amount),0) c
        FROM jobs
    """).fetchone()["c"]

    total_paid = con.execute("""
        SELECT COALESCE(SUM(amount),0) c
        FROM payments
    """).fetchone()["c"]

    pending = con.execute("""
        SELECT COUNT(*) c
        FROM jobs
        WHERE status != 'Delivered'
    """).fetchone()["c"]

    con.close()

    balance = total_work - total_paid

    body = f"""
    <div class="hero">

        <h2>💎 R.K JEWELERS MANAGEMENT</h2>

        <p>
            Jewellery Job Work • Nag Setting • Kachi Jadai • Chilai
        </p>

        <p>
            <b>Developer: KRISHNA</b>
        </p>

    </div>

    <br>

    <div class="cardbox">

        <div class="card">
            <h3>👥 ACTIVE CUSTOMERS</h3>
            <b>{customers_count}</b>
        </div>

        <div class="card">
            <h3>💎 TOTAL JOBS</h3>
            <b>{jobs_count}</b>
        </div>

        <div class="card">
            <h3>💰 TOTAL KAAM</h3>
            <b>{money(total_work)}</b>
        </div>

        <div class="card">
            <h3>💵 TOTAL PAID</h3>
            <b class="credit">{money(total_paid)}</b>
        </div>

    </div>

    <div class="cardbox" style="margin-top:16px;">

        <div class="card">
            <h3>📌 PENDING JOBS</h3>
            <b>{pending}</b>
        </div>

        <div class="card">
            <h3>📒 TOTAL BAAKI</h3>
            <b class="debit">{money(balance)}</b>
        </div>

        <div class="card">
            <h3>📱 WHATSAPP</h3>
            <b>READY</b>
        </div>

        <div class="card">
            <h3>📄 PDF</h3>
            <b>READY</b>
        </div>

    </div>

    <div class="panel">

        <h3>⚡ Quick Actions</h3>

        <div class="actions">

            <a class="btn green"
               href="{url_for('customers')}">
               ➕ Customer
            </a>

            <a class="btn"
               href="{url_for('jobs')}">
               💎 New Job
            </a>

            <a class="btn blue"
               href="{url_for('payments')}">
               💰 Payment
            </a>

            <a class="btn purple"
               href="{url_for('reports')}">
               📊 Reports
            </a>

        </div>

    </div>
    """

    return page("Dashboard", body)


# ============================================================
# CUSTOMERS
# ============================================================

@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():

    con = db()

    if request.method == "POST":

        action = request.form.get(
            "action", ""
        )

        try:

            if action == "add":

                name = request.form.get(
                    "name", ""
                ).strip()

                mobile = request.form.get(
                    "mobile", ""
                ).strip()

                address = request.form.get(
                    "address", ""
                ).strip()

                notes = request.form.get(
                    "notes", ""
                ).strip()

                if not name:
                    raise ValueError(
                        "Customer name zaroori hai."
                    )

                con.execute("""
                    INSERT INTO customers(
                        name,
                        mobile,
                        address,
                        notes
                    )
                    VALUES(?,?,?,?)
                """, (
                    name,
                    mobile,
                    address,
                    notes
                ))

                con.commit()

                flash(
                    "Customer successfully add ho gaya.",
                    "success"
                )

            elif action == "delete":

                cid = int(
                    request.form.get(
                        "customer_id",
                        "0"
                    )
                )

                con.execute("""
                    UPDATE customers
                    SET active=0
                    WHERE id=?
                """, (cid,))

                con.commit()

                flash(
                    "Customer remove ho gaya.",
                    "success"
                )

        except Exception as e:

            con.rollback()

            flash(
                str(e),
                "error"
            )

        con.close()

        return redirect(
            url_for("customers")
        )

    rows = con.execute("""
        SELECT
            c.*,

            (
                SELECT COALESCE(SUM(j.work_amount),0)
                FROM jobs j
                WHERE j.customer_id=c.id
            ) AS total_work,

            (
                SELECT COALESCE(SUM(p.amount),0)
                FROM payments p
                WHERE p.customer_id=c.id
            ) AS total_paid,

            (
                SELECT COUNT(*)
                FROM jobs j2
                WHERE j2.customer_id=c.id
            ) AS jobs_count

        FROM customers c

        WHERE c.active=1

        ORDER BY c.name
    """).fetchall()

    con.close()

    body = """
    <h2>👥 Customers</h2>

    <div class="panel">

        <h3>➕ Add Customer</h3>

        <form method="post">

            <input
                type="hidden"
                name="action"
                value="add"
            >

            <div class="form">

                <div>
                    <label>Customer Name</label>
                    <input
                        name="name"
                        required
                        placeholder="Customer name"
                    >
                </div>

                <div>
                    <label>Mobile</label>
                    <input
                        name="mobile"
                        placeholder="Mobile"
                    >
                </div>

                <div>
                    <label>Address</label>
                    <input
                        name="address"
                        placeholder="Address"
                    >
                </div>

                <div>
                    <label>Notes</label>
                    <input
                        name="notes"
                        placeholder="Notes"
                    >
                </div>

            </div>

            <br>

            <button class="green">
                💾 SAVE CUSTOMER
            </button>

        </form>

    </div>

    <div class="panel">

        <h3>📋 Customer List</h3>

        <div class="table">

            <table>

                <tr>
                    <th>Name</th>
                    <th>Mobile</th>
                    <th>Jobs</th>
                    <th>Total Kaam</th>
                    <th>Paid</th>
                    <th>Baaki</th>
                    <th>Actions</th>
                </tr>

                {% for r in rows %}

                <tr>

                    <td>
                        <b>{{ r["name"] }}</b>

                        {% if r["address"] %}
                        <br>
                        <span class="muted">
                            {{ r["address"] }}
                        </span>
                        {% endif %}
                    </td>

                    <td>{{ r["mobile"] }}</td>

                    <td>{{ r["jobs_count"] }}</td>

                    <td>{{ "%.2f"|format(r["total_work"] or 0) }}</td>

                    <td class="credit">
                        {{ "%.2f"|format(r["total_paid"] or 0) }}
                    </td>

                    <td class="debit">
                        {{ "%.2f"|format(
                            (r["total_work"] or 0)
                            -
                            (r["total_paid"] or 0)
                        ) }}
                    </td>

                    <td>

                        <div class="actions">

                            <a
                                class="btn small"
                                href="{{ url_for(
                                    'ledger',
                                    customer_id=r['id']
                                ) }}"
                            >
                                📒 Ledger
                            </a>

                            {% if r["mobile"] %}

                            <a
                                class="btn whatsapp small"
                                target="_blank"
                                href="https://wa.me/{{ r['mobile']|replace('+','')|replace(' ','') }}"
                            >
                                📱 WhatsApp
                            </a>

                            {% endif %}

                            <form
                                method="post"
                                style="display:inline"
                                onsubmit="return confirm('Customer remove kare?')"
                            >

                                <input
                                    type="hidden"
                                    name="action"
                                    value="delete"
                                >

                                <input
                                    type="hidden"
                                    name="customer_id"
                                    value="{{ r['id'] }}"
                                >

                                <button class="red small">
                                    DELETE
                                </button>

                            </form>

                        </div>

                    </td>

                </tr>

                {% else %}

                <tr>
                    <td colspan="7">
                        Abhi koi customer nahi hai.
                    </td>
                </tr>

                {% endfor %}

            </table>

        </div>

    </div>
    """

    return render_template_string(
        BASE_HTML,
        title="Customers",
        body=render_template_string(
            body,
            rows=rows
        )
    )


# ============================================================
# JOBS
# ============================================================

@app.route("/jobs", methods=["GET", "POST"])
@login_required
def jobs():

    con = db()

    edit_id = request.args.get(
        "edit",
        type=int
    )

    edit_job = None

    if edit_id:

        edit_job = con.execute("""
            SELECT *
            FROM jobs
            WHERE id=?
        """, (edit_id,)).fetchone()

    if request.method == "POST":

        try:

            action = request.form.get(
                "action",
                "save"
            )

            customer_id = int(
                request.form.get(
                    "customer_id",
                    "0"
                )
            )

            date_value = request.form.get(
                "date",
                ""
            ).strip()

            jewellery = request.form.get(
                "jewellery",
                ""
            ).strip()

            work = request.form.get(
                "work",
                "Other"
            ).strip()

            status = request.form.get(
                "status",
                "Pending"
            ).strip()

            maal_aaya = request.form.get(
                "maal_aaya",
                ""
            ).strip()

            maal_diyaa = request.form.get(
                "maal_diyaa",
                ""
            ).strip()

            gross_weight = parse_float(
                "gross_weight"
            )

            nag_weight = parse_float(
                "nag_weight"
            )

            loss = parse_float(
                "loss"
            )

            taanch = parse_float(
                "taanch"
            )

            quantity = parse_int(
                "quantity",
                1
            )

            work_amount = parse_float(
                "work_amount"
            )

            notes = request.form.get(
                "notes",
                ""
            ).strip()

            if not customer_id:
                raise ValueError(
                    "Customer select karo."
                )

            if not date_value:
                raise ValueError(
                    "Date zaroori hai."
                )

            if not jewellery:
                raise ValueError(
                    "Jewellery name zaroori hai."
                )

            if gross_weight < 0:
                raise ValueError(
                    "Weight negative nahi ho sakta."
                )

            if nag_weight < 0:
                raise ValueError(
                    "Nag weight negative nahi ho sakta."
                )

            if loss < 0:
                raise ValueError(
                    "Loss negative nahi ho sakta."
                )

            if quantity < 1:
                raise ValueError(
                    "Quantity kam se kam 1 honi chahiye."
                )

            if work_amount < 0:
                raise ValueError(
                    "Amount negative nahi ho sakta."
                )

            total_weight = (
                gross_weight + nag_weight
            )

            final_weight = (
                total_weight - loss
            )

            if final_weight < 0:
                raise ValueError(
                    "Final weight negative nahi ho sakta."
                )

            # ------------------------------------------------
            # IMPORTANT:
            # 20 SQL placeholders = EXACTLY 20 values
            # ------------------------------------------------

            values = (
                customer_id,
                date_value,
                jewellery,
                work,
                status,
                maal_aaya,
                maal_diyaa,
                gross_weight,
                nag_weight,
                total_weight,
                loss,
                final_weight,
                nag_weight,
                final_weight,
                taanch,
                quantity,
                work_amount,
                notes
            )

            if edit_id:

                con.execute("""
                    UPDATE jobs
                    SET
                        customer_id=?,
                        date=?,
                        jewellery=?,
                        work=?,
                        status=?,
                        maal_aaya=?,
                        maal_diyaa=?,
                        gross_weight=?,
                        nag_weight=?,
                        total_weight=?,
                        loss=?,
                        final_weight=?,
                        stone_weight=?,
                        net_weight=?,
                        taanch=?,
                        quantity=?,
                        work_amount=?,
                        notes=?
                    WHERE id=?
                """, values + (edit_id,))

                message = (
                    "Job entry update ho gayi."
                )

            else:

                con.execute("""
                    INSERT INTO jobs(
                        customer_id,
                        date,
                        jewellery,
                        work,
                        status,
                        maal_aaya,
                        maal_diyaa,
                        gross_weight,
                        nag_weight,
                        total_weight,
                        loss,
                        final_weight,
                        stone_weight,
                        net_weight,
                        taanch,
                        quantity,
                        work_amount,
                        notes
                    )
                    VALUES(
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?
                    )
                """, values)

                message = (
                    "Job entry save ho gayi."
                )

            con.commit()

            flash(
                message,
                "success"
            )

            con.close()

            return redirect(
                url_for("jobs")
            )

        except Exception as e:

            con.rollback()

            flash(
                str(e),
                "error"
            )

    customers_rows = con.execute("""
        SELECT id,name,mobile
        FROM customers
        WHERE active=1
        ORDER BY name
    """).fetchall()

    jobs_rows = con.execute("""
        SELECT
            j.*,
            c.name AS customer_name,
            c.mobile AS customer_mobile
        FROM jobs j
        JOIN customers c
            ON c.id=j.customer_id
        ORDER BY j.id DESC
    """).fetchall()

    con.close()

    if edit_job:

        selected_customer = str(
            edit_job["customer_id"]
        )

        form_date = edit_job["date"] or ""

        form_jewellery = (
            edit_job["jewellery"] or ""
        )

        form_work = (
            edit_job["work"] or "Other"
        )

        form_status = (
            edit_job["status"] or "Pending"
        )

        form_maal_aaya = (
            edit_job["maal_aaya"] or ""
        )

        form_maal_diyaa = (
            edit_job["maal_diyaa"] or ""
        )

        form_gross = (
            edit_job["gross_weight"] or 0
        )

        form_nag = (
            edit_job["nag_weight"] or 0
        )

        form_loss = (
            edit_job["loss"] or 0
        )

        form_taanch = (
            edit_job["taanch"] or 0
        )

        form_quantity = (
            edit_job["quantity"] or 1
        )

        form_amount = (
            edit_job["work_amount"] or 0
        )

        form_notes = (
            edit_job["notes"] or ""
        )

        heading = "✏️ EDIT JOB"
        button_text = "UPDATE JOB"

    else:

        selected_customer = ""

        form_date = datetime.now().strftime(
            "%Y-%m-%d"
        )

        form_jewellery = ""
        form_work = "Nag Setting"
        form_status = "Pending"
        form_maal_aaya = ""
        form_maal_diyaa = ""
        form_gross = 0
        form_nag = 0
        form_loss = 0
        form_taanch = 0
        form_quantity = 1
        form_amount = 0
        form_notes = ""

        heading = "➕ NEW JOB ENTRY"
        button_text = "SAVE JOB"

    body = f"""
    <h2>{heading}</h2>

    <div class="panel">

        <form method="post">

            <div class="form">

                <div>
                    <label>Customer</label>

                    <select
                        name="customer_id"
                        required
                    >

                        <option value="">
                            Select Customer
                        </option>

                        {"".join(
                            f'''
                            <option
                                value="{c["id"]}"
                                {"selected" if selected_customer == str(c["id"]) else ""}
                            >
                                {esc(c["name"])}
                            </option>
                            '''
                            for c in customers_rows
                        )}

                    </select>
                </div>

                <div>
                    <label>Date</label>

                    <input
                        type="date"
                        name="date"
                        value="{esc(form_date)}"
                        required
                    >
                </div>

                <div>
                    <label>Jewellery</label>

                    <input
                        name="jewellery"
                        value="{esc(form_jewellery)}"
                        placeholder="Ring / Chain / Pendant"
                        required
                    >
                </div>

                <div>
                    <label>Work</label>

                    <select name="work">

                        <option
                            {"selected" if form_work == "Nag Setting" else ""}
                        >
                            Nag Setting
                        </option>

                        <option
                            {"selected" if form_work == "Kachi Jadai" else ""}
                        >
                            Kachi Jadai
                        </option>

                        <option
                            {"selected" if form_work == "Chilai" else ""}
                        >
                            Chilai
                        </option>

                        <option
                            {"selected" if form_work == "Other" else ""}
                        >
                            Other
                        </option>

                    </select>
                </div>

                <div>
                    <label>Status</label>

                    <select name="status">

                        <option
                            {"selected" if form_status == "Pending" else ""}
                        >
                            Pending
                        </option>

                        <option
                            {"selected" if form_status == "In Progress" else ""}
                        >
                            In Progress
                        </option>

                        <option
                            {"selected" if form_status == "Ready" else ""}
                        >
                            Ready
                        </option>

                        <option
                            {"selected" if form_status == "Delivered" else ""}
                        >
                            Delivered
                        </option>

                    </select>
                </div>

                <div>
                    <label>नग</label>

                    <input
                        type="number"
                        name="quantity"
                        min="1"
                        value="{form_quantity}"
                    >
                </div>

                <div>
                    <label>माल आया</label>

                    <input
                        name="maal_aaya"
                        value="{esc(form_maal_aaya)}"
                    >
                </div>

                <div>
                    <label>माल गया</label>

                    <input
                        name="maal_diyaa"
                        value="{esc(form_maal_diyaa)}"
                    >
                </div>

                <div>
                    <label>काम की रकम</label>

                    <input
                        type="number"
                        step="0.01"
                        min="0"
                        name="work_amount"
                        value="{form_amount}"
                    >
                </div>

            </div>

            <br>

            <div class="weight-box">

                <h3>⚖️ वजन विवरण</h3>

                <div class="form">

                    <div>
                        <label>वजन</label>

                        <input
                            type="number"
                            step="0.001"
                            min="0"
                            id="gross_weight"
                            name="gross_weight"
                            value="{form_gross}"
                            oninput="calculateWeight()"
                        >
                    </div>

                    <div>
                        <label>+ नग वजन</label>

                        <input
                            type="number"
                            step="0.001"
                            min="0"
                            id="stone_weight"
                            name="nag_weight"
                            value="{form_nag}"
                            oninput="calculateWeight()"
                        >
                    </div>

                    <div>
                        <label>= कुल वजन</label>

                        <input
                            type="text"
                            id="total_weight"
                            class="weight-result"
                            readonly
                        >
                    </div>

                    <div>
                        <label>- लॉस</label>

                        <input
                            type="number"
                            step="0.001"
                            min="0"
                            id="loss"
                            name="loss"
                            value="{form_loss}"
                            oninput="calculateWeight()"
                        >
                    </div>

                    <div>
                        <label>= अंतिम वजन</label>

                        <input
                            type="text"
                            id="net_weight"
                            class="weight-result"
                            readonly
                        >
                    </div>

                    <div>
                        <label>ताँच</label>

                        <input
                            type="number"
                            step="0.001"
                            name="taanch"
                            value="{form_taanch}"
                            placeholder="ताँच"
                        >
                    </div>

                </div>

            </div>

            <br>

            <label>Notes</label>

            <textarea
                name="notes"
                placeholder="Extra notes..."
            >{esc(form_notes)}</textarea>

            <br><br>

            <button
                class="green"
                type="submit"
            >
                💾 {button_text}
            </button>

            <a
                class="btn gray"
                href="{url_for('jobs')}"
            >
                CANCEL
            </a>

        </form>

    </div>

    <div class="panel">

        <h3>📋 JOB RECORDS</h3>

        <div class="table">

            <table>

                <tr>
                    <th>ID</th>
                    <th>Date</th>
                    <th>Customer</th>
                    <th>Jewellery</th>
                    <th>Work</th>
                    <th>Weight</th>
                    <th>ताँच</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
    """

    for r in jobs_rows:

        whatsapp = ""

        if r["customer_mobile"]:

            phone = (
                str(r["customer_mobile"])
                .replace("+", "")
                .replace(" ", "")
                .replace("-", "")
            )

            message = urllib.parse.quote(
                f"Namaste {r['customer_name']}, "
                f"R.K JEWELERS me aapki "
                f"{r['jewellery']} ki job "
                f"{r['status']} hai. "
                f"Amount ₹{float(r['work_amount'] or 0):,.2f}"
            )

            whatsapp = f"""
            <a
                class="btn whatsapp small"
                target="_blank"
                href="https://wa.me/{phone}?text={message}"
            >
                📱 WhatsApp
            </a>
            """

        body += f"""

                <tr>

                    <td>{r["id"]}</td>

                    <td>{esc(r["date"])}</td>

                    <td>
                        <b>{esc(r["customer_name"])}</b>
                    </td>

                    <td>{esc(r["jewellery"])}</td>

                    <td>{esc(r["work"])}</td>

                    <td>
                        वजन:
                        {float(r["gross_weight"] or 0):.3f} g
                        <br>

                        + नग वजन:
                        {float(r["nag_weight"] or 0):.3f} g
                        <br>

                        = कुल:
                        {float(r["total_weight"] or 0):.3f} g
                        <br>

                        - लॉस:
                        {float(r["loss"] or 0):.3f} g
                        <br>

                        = अंतिम:
                        {float(r["final_weight"] or 0):.3f} g
                    </td>

                    <td>
                        {float(r["taanch"] or 0):.3f}
                    </td>

                    <td>
                        ₹{float(r["work_amount"] or 0):,.2f}
                    </td>

                    <td>
                        <span class="badge yellow">
                            {esc(r["status"])}
                        </span>
                    </td>

                    <td>

                        <div class="actions">

                            <a
                                class="btn small"
                                href="{url_for(
                                    'jobs',
                                    edit=r['id']
                                )}"
                            >
                                ✏️ EDIT
                            </a>

                            {whatsapp}

                            <a
                                class="btn purple small"
                                href="{url_for(
                                    'job_pdf',
                                    job_id=r['id']
                                )}"
                            >
                                📄 PDF
                            </a>

                            <form
                                method="post"
                                action="{url_for(
                                    'delete_job',
                                    job_id=r['id']
                                )}"
                                style="display:inline"
                                onsubmit="return confirm('Job delete kare?')"
                            >

                                <button class="red small">
                                    DELETE
                                </button>

                            </form>

                        </div>

                    </td>

                </tr>
        """

    body += """
            </table>

        </div>

    </div>

    <script>

    function calculateWeight(){

        const gross =
            parseFloat(
                document.getElementById(
                    "gross_weight"
                ).value
            ) || 0;

        const nag =
            parseFloat(
                document.getElementById(
                    "stone_weight"
                ).value
            ) || 0;

        const loss =
            parseFloat(
                document.getElementById(
                    "loss"
                ).value
            ) || 0;

        const total =
            gross + nag;

        const finalWeight =
            total - loss;

        document.getElementById(
            "total_weight"
        ).value =
            total.toFixed(3);

        document.getElementById(
            "net_weight"
        ).value =
            Math.max(
                0,
                finalWeight
            ).toFixed(3);
    }

    document.addEventListener(
        "DOMContentLoaded",
        function(){
            calculateWeight();
        }
    );

    </script>
    """

    return page(
        "Jobs",
        body
    )


# ============================================================
# DELETE JOB
# ============================================================

@app.post("/job/delete/<int:job_id>")
@login_required
def delete_job(job_id):

    con = db()

    con.execute(
        "DELETE FROM jobs WHERE id=?",
        (job_id,)
    )

    con.commit()
    con.close()

    flash(
        "Job deleted successfully.",
        "success"
    )

    return redirect(
        url_for("jobs")
    )


# ============================================================
# PAYMENTS
# ============================================================

@app.route("/payments", methods=["GET", "POST"])
@login_required
def payments():

    con = db()

    if request.method == "POST":

        try:

            customer_id = int(
                request.form.get(
                    "customer_id",
                    "0"
                )
            )

            date_value = request.form.get(
                "date",
                ""
            ).strip()

            amount = parse_float(
                "amount"
            )

            mode = request.form.get(
                "mode",
                "Cash"
            )

            note = request.form.get(
                "note",
                ""
            ).strip()

            if not customer_id:
                raise ValueError(
                    "Customer select karo."
                )

            if not date_value:
                raise ValueError(
                    "Date zaroori hai."
                )

            if amount <= 0:
                raise ValueError(
                    "Payment amount 0 se bada hona chahiye."
                )

            con.execute("""
                INSERT INTO payments(
                    customer_id,
                    date,
                    amount,
                    mode,
                    note
                )
                VALUES(?,?,?,?,?)
            """, (
                customer_id,
                date_value,
                amount,
                mode,
                note
            ))

            con.commit()

            flash(
                "Payment successfully save ho gaya.",
                "success"
            )

        except Exception as e:

            con.rollback()

            flash(
                str(e),
                "error"
            )

        con.close()

        return redirect(
            url_for("payments")
        )

    customers_rows = con.execute("""
        SELECT id,name
        FROM customers
        WHERE active=1
        ORDER BY name
    """).fetchall()

    payment_rows = con.execute("""
        SELECT
            p.*,
            c.name AS customer_name
        FROM payments p
        JOIN customers c
            ON c.id=p.customer_id
        ORDER BY p.id DESC
    """).fetchall()

    con.close()

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    body = """
    <h2>💰 Payment Entry</h2>

    <div class="panel">

        <form method="post">

            <div class="form">

                <div>
                    <label>Customer</label>

                    <select
                        name="customer_id"
                        required
                    >

                        <option value="">
                            Select Customer
                        </option>

                        {% for c in customers_rows %}

                        <option value="{{ c['id'] }}">
                            {{ c['name'] }}
                        </option>

                        {% endfor %}

                    </select>
                </div>

                <div>
                    <label>Date</label>

                    <input
                        type="date"
                        name="date"
                        value="{{ today }}"
                        required
                    >
                </div>

                <div>
                    <label>Amount</label>

                    <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        name="amount"
                        required
                    >
                </div>

                <div>
                    <label>Mode</label>

                    <select name="mode">

                        <option>Cash</option>
                        <option>UPI</option>
                        <option>Bank</option>
                        <option>Cheque</option>

                    </select>
                </div>

                <div>
                    <label>Note</label>

                    <input
                        name="note"
                        placeholder="Payment note"
                    >
                </div>

            </div>

            <br>

            <button class="green">
                💾 SAVE PAYMENT
            </button>

        </form>

    </div>

    <div class="panel">

        <h3>📋 Payment History</h3>

        <div class="table">

            <table>

                <tr>
                    <th>Date</th>
                    <th>Customer</th>
                    <th>Amount</th>
                    <th>Mode</th>
                    <th>Note</th>
                </tr>

                {% for p in payment_rows %}

                <tr>

                    <td>{{ p["date"] }}</td>

                    <td>
                        {{ p["customer_name"] }}
                    </td>

                    <td class="credit">
                        ₹{{ "%.2f"|format(p["amount"] or 0) }}
                    </td>

                    <td>
                        <span class="badge green">
                            {{ p["mode"] }}
                        </span>
                    </td>

                    <td>
                        {{ p["note"] }}
                    </td>

                </tr>

                {% endfor %}

            </table>

        </div>

    </div>
    """

    return render_template_string(
        BASE_HTML,
        title="Payments",
        body=render_template_string(
            body,
            customers_rows=customers_rows,
            payment_rows=payment_rows,
            today=today
        )
    )


# ============================================================
# CUSTOMER LEDGER
# ============================================================

@app.route("/ledger")
@login_required
def ledger():

    customer_id = request.args.get(
        "customer_id",
        type=int
    )

    con = db()

    customers_rows = con.execute("""
        SELECT id,name
        FROM customers
        WHERE active=1
        ORDER BY name
    """).fetchall()

    if not customer_id:

        con.close()

        body = """
        <h2>📒 Customer Ledger</h2>

        <div class="panel">

            <h3>Select Customer</h3>

            <form method="get">

                <select
                    name="customer_id"
                    required
                >

                    <option value="">
                        Select Customer
                    </option>

                    {% for c in customers_rows %}

                    <option value="{{ c['id'] }}">
                        {{ c['name'] }}
                    </option>

                    {% endfor %}

                </select>

                <br><br>

                <button class="blue">
                    📒 OPEN LEDGER
                </button>

            </form>

        </div>
        """

        return render_template_string(
            BASE_HTML,
            title="Ledger",
            body=render_template_string(
                body,
                customers_rows=customers_rows
            )
        )

    customer = con.execute("""
        SELECT *
        FROM customers
        WHERE id=?
    """, (customer_id,)).fetchone()

    if not customer:

        con.close()

        flash(
            "Customer nahi mila.",
            "error"
        )

        return redirect(
            url_for("ledger")
        )

    jobs_rows = con.execute("""
        SELECT *
        FROM jobs
        WHERE customer_id=?
        ORDER BY date,id
    """, (customer_id,)).fetchall()

    payment_rows = con.execute("""
        SELECT *
        FROM payments
        WHERE customer_id=?
        ORDER BY date,id
    """, (customer_id,)).fetchall()

    total_work = sum(
        float(r["work_amount"] or 0)
        for r in jobs_rows
    )

    total_paid = sum(
        float(r["amount"] or 0)
        for r in payment_rows
    )

    balance = (
        total_work - total_paid
    )

    mobile = (
        str(customer["mobile"] or "")
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
    )

    whatsapp_url = "#"

    if mobile:

        message = urllib.parse.quote(
            f"Namaste {customer['name']}, "
            f"R.K JEWELERS ka aapka ledger:\n"
            f"Total Kaam: ₹{total_work:,.2f}\n"
            f"Paid: ₹{total_paid:,.2f}\n"
            f"Baaki: ₹{balance:,.2f}"
        )

        whatsapp_url = (
            f"https://wa.me/{mobile}"
            f"?text={message}"
        )

    con.close()

    body = f"""
    <h2>📒 Customer Ledger</h2>

    <div class="panel">

        <h2>
            👤 {esc(customer["name"])}
        </h2>

        <p>
            📱 {esc(customer["mobile"])}
        </p>

        <div class="cardbox">

            <div class="card">
                <h3>TOTAL KAAM</h3>
                <b>{money(total_work)}</b>
            </div>

            <div class="card">
                <h3>TOTAL PAID</h3>
                <b class="credit">
                    {money(total_paid)}
                </b>
            </div>

            <div class="card">
                <h3>BAAKI</h3>
                <b class="debit">
                    {money(balance)}
                </b>
            </div>

            <div class="card">
                <h3>TOTAL JOBS</h3>
                <b>
                    {len(jobs_rows)}
                </b>
            </div>

        </div>

        <br>

        <div class="actions">

            <a
                class="btn purple"
                href="{url_for(
                    'ledger_pdf',
                    customer_id=customer_id
                )}"
            >
                📄 DOWNLOAD COLOUR PDF
            </a>

            <a
                class="btn whatsapp"
                target="_blank"
                href="{whatsapp_url}"
            >
                📱 SEND WHATSAPP
            </a>

            <button
                class="btn gray"
                onclick="window.print()"
            >
                🖨️ PRINT
            </button>

        </div>

    </div>

    <div class="panel">

        <h3>💎 Job History</h3>

        <div class="table">

            <table>

                <tr>
                    <th>Date</th>
                    <th>Jewellery</th>
                    <th>Work</th>
                    <th>Weight</th>
                    <th>Amount</th>
                    <th>Status</th>
                </tr>

    """

    for r in jobs_rows:

        body += f"""

                <tr>

                    <td>
                        {esc(r["date"])}
                    </td>

                    <td>
                        {esc(r["jewellery"])}
                    </td>

                    <td>
                        {esc(r["work"])}
                    </td>

                    <td>
                        {float(r["final_weight"] or 0):.3f} g
                    </td>

                    <td>
                        ₹{float(r["work_amount"] or 0):,.2f}
                    </td>

                    <td>
                        <span class="badge yellow">
                            {esc(r["status"])}
                        </span>
                    </td>

                </tr>
        """

    body += """

            </table>

        </div>

    </div>

    <div class="panel">

        <h3>💰 Payment History</h3>

        <div class="table">

            <table>

                <tr>
                    <th>Date</th>
                    <th>Amount</th>
                    <th>Mode</th>
                    <th>Note</th>
                </tr>
    """

    for p in payment_rows:

        body += f"""

                <tr>

                    <td>
                        {esc(p["date"])}
                    </td>

                    <td class="credit">
                        ₹{float(p["amount"] or 0):,.2f}
                    </td>

                    <td>
                        {esc(p["mode"])}
                    </td>

                    <td>
                        {esc(p["note"])}
                    </td>

                </tr>
        """

    body += """
            </table>

        </div>

    </div>
    """

    return page(
        "Customer Ledger",
        body
    )


# ============================================================
# CUSTOMER SEARCH
# ============================================================

@app.route("/search")
@login_required
def search():

    q = request.args.get(
        "q",
        ""
    ).strip()

    con = db()

    if q:

        # IMPORTANT:
        # mobile column use ho raha hai.
        # Old code me phone use hone ki wajah se
        # internal error aa raha tha.

        rows = con.execute("""
            SELECT *
            FROM customers
            WHERE
                name LIKE ?
                OR mobile LIKE ?
                OR address LIKE ?
            ORDER BY name
        """, (
            f"%{q}%",
            f"%{q}%",
            f"%{q}%"
        )).fetchall()

    else:

        rows = []

    con.close()

    body = """
    <h2>🔎 Customer Search</h2>

    <div class="panel">

        <form
            method="get"
            class="search-box"
        >

            <input
                type="text"
                name="q"
                value="{{ q }}"
                placeholder="Customer name / mobile / address"
            >

            <button class="blue">
                🔍 SEARCH
            </button>

        </form>

    </div>

    <div class="panel">

        <div class="table">

            <table>

                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Mobile</th>
                    <th>Address</th>
                    <th>Action</th>
                </tr>

                {% for c in rows %}

                <tr>

                    <td>{{ c["id"] }}</td>

                    <td>
                        <b>{{ c["name"] }}</b>
                    </td>

                    <td>
                        {{ c["mobile"] }}
                    </td>

                    <td>
                        {{ c["address"] }}
                    </td>

                    <td>

                        <div class="actions">

                            <a
                                class="btn small"
                                href="{{ url_for(
                                    'ledger',
                                    customer_id=c['id']
                                ) }}"
                            >
                                📒 Ledger
                            </a>

                            {% if c["mobile"] %}

                            <a
                                class="btn whatsapp small"
                                target="_blank"
                                href="https://wa.me/{{ c['mobile']|replace('+','')|replace(' ','') }}"
                            >
                                📱 WhatsApp
                            </a>

                            {% endif %}

                        </div>

                    </td>

                </tr>

                {% else %}

                <tr>

                    <td colspan="5">

                        {% if q %}
                        ❌ No customer found.
                        {% else %}
                        Customer search karne ke liye naam/mobile dalo.
                        {% endif %}

                    </td>

                </tr>

                {% endfor %}

            </table>

        </div>

    </div>
    """

    return render_template_string(
        BASE_HTML,
        title="Search",
        body=render_template_string(
            body,
            q=q,
            rows=rows
        )
    )


# ============================================================
# REPORTS
# ============================================================

@app.route("/reports")
@login_required
def reports():

    con = db()

    total_customers = con.execute("""
        SELECT COUNT(*)
        FROM customers
        WHERE active=1
    """).fetchone()[0]

    total_jobs = con.execute("""
        SELECT COUNT(*)
        FROM jobs
    """).fetchone()[0]

    total_work = con.execute("""
        SELECT COALESCE(SUM(work_amount),0)
        FROM jobs
    """).fetchone()[0]

    total_paid = con.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM payments
    """).fetchone()[0]

    pending_jobs = con.execute("""
        SELECT COUNT(*)
        FROM jobs
        WHERE status!='Delivered'
    """).fetchone()[0]

    delivered_jobs = con.execute("""
        SELECT COUNT(*)
        FROM jobs
        WHERE status='Delivered'
    """).fetchone()[0]

    con.close()

    balance = (
        total_work - total_paid
    )

    body = f"""
    <h2>📊 Reports</h2>

    <div class="cardbox">

        <div class="card">
            <h3>CUSTOMERS</h3>
            <b>{total_customers}</b>
        </div>

        <div class="card">
            <h3>TOTAL JOBS</h3>
            <b>{total_jobs}</b>
        </div>

        <div class="card">
            <h3>TOTAL KAAM</h3>
            <b>{money(total_work)}</b>
        </div>

        <div class="card">
            <h3>TOTAL PAID</h3>
            <b class="credit">
                {money(total_paid)}
            </b>
        </div>

        <div class="card">
            <h3>BAAKI</h3>
            <b class="debit">
                {money(balance)}
            </b>
        </div>

        <div class="card">
            <h3>PENDING</h3>
            <b>{pending_jobs}</b>
        </div>

        <div class="card">
            <h3>DELIVERED</h3>
            <b>{delivered_jobs}</b>
        </div>

    </div>

    <div class="panel">

        <h3>📄 PDF Reports</h3>

        <div class="actions">

            <a
                class="btn purple"
                href="{url_for('all_jobs_pdf')}"
            >
                📄 DOWNLOAD ALL JOBS PDF
            </a>

            <a
                class="btn blue"
                href="{url_for('all_customers_pdf')}"
            >
                📄 DOWNLOAD CUSTOMER REPORT
            </a>

        </div>

    </div>
    """

    return page(
        "Reports",
        body
    )


# ============================================================
# COLOUR PDF HELPER
# ============================================================

def make_pdf(title, story):

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle
    )

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()

    story.insert(
        0,
        Paragraph(
            "<b><font color='#8B5A00' size='22'>"
            "R.K JEWELERS"
            "</font></b>",
            styles["Title"]
        )
    )

    story.insert(
        1,
        Paragraph(
            f"<b>{title}</b>",
            styles["Heading2"]
        )
    )

    story.insert(
        2,
        Spacer(1, 12)
    )

    doc.build(story)

    buffer.seek(0)

    return buffer


# ============================================================
# JOB PDF
# ============================================================

@app.route("/job/pdf/<int:job_id>")
@login_required
def job_pdf(job_id):

    from reportlab.platypus import (
        Paragraph,
        Spacer,
        Table,
        TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    con = db()

    job = con.execute("""
        SELECT
            j.*,
            c.name AS customer_name,
            c.mobile AS customer_mobile
        FROM jobs j
        JOIN customers c
            ON c.id=j.customer_id
        WHERE j.id=?
    """, (job_id,)).fetchone()

    con.close()

    if not job:

        flash(
            "Job nahi mila.",
            "error"
        )

        return redirect(
            url_for("jobs")
        )

    styles = getSampleStyleSheet()

    data = [
        ["Field", "Details"],

        ["Customer", job["customer_name"]],

        ["Mobile", job["customer_mobile"] or ""],

        ["Date", job["date"]],

        ["Jewellery", job["jewellery"]],

        ["Work", job["work"]],

        ["Status", job["status"]],

        ["वजन",
         f"{float(job['gross_weight'] or 0):.3f} g"],

        ["नग वजन",
         f"{float(job['nag_weight'] or 0):.3f} g"],

        ["कुल वजन",
         f"{float(job['total_weight'] or 0):.3f} g"],

        ["लॉस",
         f"{float(job['loss'] or 0):.3f} g"],

        ["अंतिम वजन",
         f"{float(job['final_weight'] or 0):.3f} g"],

        ["ताँच",
         f"{float(job['taanch'] or 0):.3f}"],

        ["Quantity",
         str(job["quantity"] or 1)],

        ["काम की रकम",
         money(job["work_amount"])],

        ["माल आया",
         job["maal_aaya"] or ""],

        ["माल गया",
         job["maal_diyaa"] or ""],

        ["Notes",
         job["notes"] or ""]
    ]

    table = Table(
        data,
        colWidths=[150, 350]
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0,0),
                (-1,0),
                colors.HexColor("#5B3215")
            ),
            (
                "TEXTCOLOR",
                (0,0),
                (-1,0),
                colors.HexColor("#FFE59A")
            ),
            (
                "BACKGROUND",
                (0,1),
                (0,-1),
                colors.HexColor("#FFF1BF")
            ),
            (
                "GRID",
                (0,0),
                (-1,-1),
                0.5,
                colors.HexColor("#C49A45")
            ),
            (
                "FONTNAME",
                (0,0),
                (-1,0),
                "Helvetica-Bold"
            ),
            (
                "FONTNAME",
                (0,1),
                (0,-1),
                "Helvetica-Bold"
            ),
            (
                "VALIGN",
                (0,0),
                (-1,-1),
                "TOP"
            ),
            (
                "PADDING",
                (0,0),
                (-1,-1),
                8
            )
        ])
    )

    story = [
        Paragraph(
            "Jewellery Job Receipt",
            styles["Heading2"]
        ),
        Spacer(1,10),
        table,
        Spacer(1,20),
        Paragraph(
            "<b>Developer: KRISHNA</b>",
            styles["Normal"]
        )
    ]

    pdf = make_pdf(
        "Jewellery Job Receipt",
        story
    )

    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"job_{job_id}.pdf",
        mimetype="application/pdf"
    )


# ============================================================
# LEDGER PDF
# ============================================================

@app.route("/ledger/pdf/<int:customer_id>")
@login_required
def ledger_pdf(customer_id):

    from reportlab.platypus import (
        Paragraph,
        Spacer,
        Table,
        TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    con = db()

    customer = con.execute("""
        SELECT *
        FROM customers
        WHERE id=?
    """, (customer_id,)).fetchone()

    if not customer:

        con.close()

        flash(
            "Customer nahi mila.",
            "error"
        )

        return redirect(
            url_for("ledger")
        )

    jobs_rows = con.execute("""
        SELECT *
        FROM jobs
        WHERE customer_id=?
        ORDER BY date,id
    """, (customer_id,)).fetchall()

    payment_rows = con.execute("""
        SELECT *
        FROM payments
        WHERE customer_id=?
        ORDER BY date,id
    """, (customer_id,)).fetchall()

    con.close()

    total_work = sum(
        float(j["work_amount"] or 0)
        for j in jobs_rows
    )

    total_paid = sum(
        float(p["amount"] or 0)
        for p in payment_rows
    )

    balance = (
        total_work - total_paid
    )

    styles = getSampleStyleSheet()

    story = [
        Paragraph(
            f"<b>Customer:</b> {esc(customer['name'])}",
            styles["Normal"]
        ),
        Paragraph(
            f"<b>Mobile:</b> {esc(customer['mobile'])}",
            styles["Normal"]
        ),
        Spacer(1,10)
    ]

    summary = [
        ["Total Kaam", "Total Paid", "Baaki"],
        [
            money(total_work),
            money(total_paid),
            money(balance)
        ]
    ]

    summary_table = Table(
        summary,
        colWidths=[170,170,170]
    )

    summary_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0,0),
                (-1,0),
                colors.HexColor("#5B3215")
            ),
            (
                "TEXTCOLOR",
                (0,0),
                (-1,0),
                colors.HexColor("#FFE59A")
            ),
            (
                "BACKGROUND",
                (0,1),
                (-1,1),
                colors.HexColor("#FFF1BF")
            ),
            (
                "GRID",
                (0,0),
                (-1,-1),
                0.5,
                colors.HexColor("#C49A45")
            ),
            (
                "ALIGN",
                (0,0),
                (-1,-1),
                "CENTER"
            ),
            (
                "PADDING",
                (0,0),
                (-1,-1),
                8
            )
        ])
    )

    story += [
        summary_table,
        Spacer(1,18),
        Paragraph(
            "<b>Job History</b>",
            styles["Heading3"]
        )
    ]

    job_data = [
        [
            "Date",
            "Jewellery",
            "Work",
            "Weight",
            "Amount",
            "Status"
        ]
    ]

    for j in jobs_rows:

        job_data.append([
            str(j["date"]),
            str(j["jewellery"]),
            str(j["work"]),
            f"{float(j['final_weight'] or 0):.3f} g",
            money(j["work_amount"]),
            str(j["status"])
        ])

    if len(job_data) == 1:

        job_data.append([
            "-",
            "No jobs",
            "-",
            "-",
            "-",
            "-"
        ])

    table = Table(
        job_data,
        colWidths=[
            65,
            100,
            80,
            75,
            85,
            75
        ],
        repeatRows=1
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0,0),
                (-1,0),
                colors.HexColor("#5B3215")
            ),
            (
                "TEXTCOLOR",
                (0,0),
                (-1,0),
                colors.HexColor("#FFE59A")
            ),
            (
                "GRID",
                (0,0),
                (-1,-1),
                0.4,
                colors.HexColor("#C49A45")
            ),
            (
                "PADDING",
                (0,0),
                (-1,-1),
                6
            ),
            (
                "VALIGN",
                (0,0),
                (-1,-1),
                "TOP"
            )
        ])
    )

    story += [
        table,
        Spacer(1,18),
        Paragraph(
            "<b>Payment History</b>",
            styles["Heading3"]
        )
    ]

    payment_data = [
        [
            "Date",
            "Amount",
            "Mode",
            "Note"
        ]
    ]

    for p in payment_rows:

        payment_data.append([
            str(p["date"]),
            money(p["amount"]),
            str(p["mode"]),
            str(p["note"] or "")
        ])

    if len(payment_data) == 1:

        payment_data.append([
            "-",
            "-",
            "-",
            "No payments"
        ])

    ptable = Table(
        payment_data,
        colWidths=[
            100,
            110,
            100,
            180
        ],
        repeatRows=1
    )

    ptable.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0,0),
                (-1,0),
                colors.HexColor("#198754")
            ),
            (
                "TEXTCOLOR",
                (0,0),
                (-1,0),
                colors.white
            ),
            (
                "GRID",
                (0,0),
                (-1,-1),
                0.4,
                colors.HexColor("#75B798")
            ),
            (
                "PADDING",
                (0,0),
                (-1,-1),
                6
            )
        ])
    )

    story += [
        ptable,
        Spacer(1,20),
        Paragraph(
            "<b>Developer: KRISHNA</b>",
            styles["Normal"]
        )
    ]

    pdf = make_pdf(
        f"Customer Ledger - {customer['name']}",
        story
    )

    return send_file(
        pdf,
        as_attachment=True,
        download_name=(
            f"ledger_{customer_id}.pdf"
        ),
        mimetype="application/pdf"
    )


# ============================================================
# ALL JOBS PDF
# ============================================================

@app.route("/reports/jobs-pdf")
@login_required
def all_jobs_pdf():

    from reportlab.platypus import (
        Paragraph,
        Spacer,
        Table,
        TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    con = db()

    rows = con.execute("""
        SELECT
            j.*,
            c.name AS customer_name
        FROM jobs j
        JOIN customers c
            ON c.id=j.customer_id
        ORDER BY j.date DESC,j.id DESC
    """).fetchall()

    con.close()

    data = [
        [
            "Date",
            "Customer",
            "Jewellery",
            "Work",
            "Final Weight",
            "Amount",
            "Status"
        ]
    ]

    for r in rows:

        data.append([
            str(r["date"]),
            str(r["customer_name"]),
            str(r["jewellery"]),
            str(r["work"]),
            f"{float(r['final_weight'] or 0):.3f} g",
            money(r["work_amount"]),
            str(r["status"])
        ])

    if len(data) == 1:
        data.append([
            "-",
            "No records",
            "-",
            "-",
            "-",
            "-",
            "-"
        ])

    table = Table(
        data,
        repeatRows=1
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0,0),
                (-1,0),
                colors.HexColor("#5B3215")
            ),
            (
                "TEXTCOLOR",
                (0,0),
                (-1,0),
                colors.HexColor("#FFE59A")
            ),
            (
                "GRID",
                (0,0),
                (-1,-1),
                .4,
                colors.HexColor("#C49A45")
            ),
            (
                "PADDING",
                (0,0),
                (-1,-1),
                5
            )
        ])
    )

    styles = getSampleStyleSheet()

    pdf = make_pdf(
        "All Jewellery Jobs",
        [
            table,
            Spacer(1,15),
            Paragraph(
                "<b>Developer: KRISHNA</b>",
                styles["Normal"]
            )
        ]
    )

    return send_file(
        pdf,
        as_attachment=True,
        download_name="all_jobs.pdf",
        mimetype="application/pdf"
    )


# ============================================================
# ALL CUSTOMERS PDF
# ============================================================

@app.route("/reports/customers-pdf")
@login_required
def all_customers_pdf():

    from reportlab.platypus import (
        Paragraph,
        Spacer,
        Table,
        TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    con = db()

    rows = con.execute("""
        SELECT
            c.id,
            c.name,
            c.mobile,

            (
                SELECT COALESCE(
                    SUM(j.work_amount),0
                )
                FROM jobs j
                WHERE j.customer_id=c.id
            ) AS total_work,

            (
                SELECT COALESCE(
                    SUM(p.amount),0
                )
                FROM payments p
                WHERE p.customer_id=c.id
            ) AS total_paid

        FROM customers c

        WHERE c.active=1

        ORDER BY c.name
    """).fetchall()

    con.close()

    data = [
        [
            "Customer",
            "Mobile",
            "Total Work",
            "Paid",
            "Baaki"
        ]
    ]

    for r in rows:

        work_amount = float(
            r["total_work"] or 0
        )

        paid_amount = float(
            r["total_paid"] or 0
        )

        data.append([
            str(r["name"]),
            str(r["mobile"] or ""),
            money(work_amount),
            money(paid_amount),
            money(
                work_amount - paid_amount
            )
        ])

    if len(data) == 1:

        data.append([
            "No customers",
            "-",
            "-",
            "-",
            "-"
        ])

    table = Table(
        data,
        repeatRows=1
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0,0),
                (-1,0),
                colors.HexColor("#5B3215")
            ),
            (
                "TEXTCOLOR",
                (0,0),
                (-1,0),
                colors.HexColor("#FFE59A")
            ),
            (
                "GRID",
                (0,0),
                (-1,-1),
                .4,
                colors.HexColor("#C49A45")
            ),
            (
                "PADDING",
                (0,0),
                (-1,-1),
                7
            )
        ])
    )

    styles = getSampleStyleSheet()

    pdf = make_pdf(
        "Customer Report",
        [
            table,
            Spacer(1,15),
            Paragraph(
                "<b>Developer: KRISHNA</b>",
                styles["Normal"]
            )
        ]
    )

    return send_file(
        pdf,
        as_attachment=True,
        download_name="customer_report.pdf",
        mimetype="application/pdf"
    )


# ============================================================
# BACKUP
# ============================================================

@app.route("/backup")
@login_required
def backup():

    if not DB.exists():

        flash(
            "Database file nahi mili.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_name = (
        f"rk_jewellers_backup_{timestamp}.db"
    )

    backup_path = (
        BACKUP_DIR / backup_name
    )

    shutil.copy2(
        DB,
        backup_path
    )

    return send_file(
        backup_path,
        as_attachment=True,
        download_name=backup_name
    )


# ============================================================
# RESTORE
# ============================================================

@app.route(
    "/restore",
    methods=["GET", "POST"]
)
@login_required
def restore():

    if request.method == "POST":

        uploaded = request.files.get(
            "backup_file"
        )

        if not uploaded or not uploaded.filename:

            flash(
                "Backup .db file select karo.",
                "error"
            )

            return redirect(
                url_for("restore")
            )

        temp_path = (
            BACKUP_DIR / "restore_temp.db"
        )

        uploaded.save(temp_path)

        try:

            test = sqlite3.connect(
                temp_path
            )

            test.execute(
                "SELECT name FROM sqlite_master LIMIT 1"
            )

            test.close()

            shutil.copy2(
                temp_path,
                DB
            )

            temp_path.unlink(
                missing_ok=True
            )

            setup()

            flash(
                "Database successfully restore ho gaya.",
                "success"
            )

        except Exception as e:

            temp_path.unlink(
                missing_ok=True
            )

            flash(
                f"Restore failed: {e}",
                "error"
            )

        return redirect(
            url_for("restore")
        )

    backups = sorted(
        BACKUP_DIR.glob(
            "rk_jewellers_backup_*.db"
        ),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    body = """
    <h2>♻️ Restore Backup</h2>

    <div class="panel">

        <h3>Upload Database Backup</h3>

        <form
            method="post"
            enctype="multipart/form-data"
            onsubmit="
                return confirm(
                    'Current database replace karna hai?'
                )
            "
        >

            <input
                type="file"
                name="backup_file"
                accept=".db"
                required
            >

            <br><br>

            <button class="red">
                ♻️ RESTORE DATABASE
            </button>

        </form>

    </div>

    <div class="panel">

        <h3>💾 Existing Backups</h3>

        {% for b in backups %}

        <p>
            📁 {{ b.name }}
        </p>

        {% else %}

        <p class="muted">
            No backup found.
        </p>

        {% endfor %}

    </div>
    """

    return render_template_string(
        BASE_HTML,
        title="Restore",
        body=render_template_string(
            body,
            backups=backups
        )
    )


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
@login_required
def about():

    body = """
    <div class="hero">

        <h2>💎 R.K JEWELERS</h2>

        <p>
            Jewellery Job Work & Customer Ledger System
        </p>

        <hr>

        <p>
            💎 Nag Setting
        </p>

        <p>
            💎 Kachi Jadai
        </p>

        <p>
            💎 Chilai
        </p>

        <p>
            💰 Customer Payment
        </p>

        <p>
            📒 Customer Ledger
        </p>

        <p>
            📄 Colour PDF Reports
        </p>

        <p>
            📱 WhatsApp Customer Contact
        </p>

        <br>

        <h3 style="color:#ffe58a;">
            Developer: KRISHNA
        </h3>

    </div>
    """

    return page(
        "About",
        body
    )


# ============================================================
# DASHBOARD ALIAS
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():
    return redirect(
        url_for("home")
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    setup()

    print("=" * 60)
    print("              R.K JEWELERS PRO")
    print("=" * 60)
    print("Developer : KRISHNA")
    print("Server    : http://127.0.0.1:5000")
    print("Username  : admin")
    print("Password  : 1234")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
