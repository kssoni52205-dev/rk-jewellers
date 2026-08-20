from flask import (
    Flask,
    request,
    redirect,
    render_template_string,
    flash,
    session,
    send_file,
    url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
from pathlib import Path
from functools import wraps
from io import BytesIO
import os
import shutil
import html

# ============================================================
# R.K JEWELERS PRO
# SINGLE FILE VERSION
# DEVELOPER: KRISHNA
# ============================================================

APP_DIR = Path(__file__).resolve().parent
DB = APP_DIR / "rk_jewellers.db"
DB_PATH = DB
BACKUP_DIR = APP_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

app.secret_key = (
    os.environ.get("RK_SECRET_KEY")
    or "RK-JEWELERS-KRISHNA-SECRET-2026"
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


get_db = db


def setup():

    con = db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        address TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        customer TEXT DEFAULT '',
        date TEXT NOT NULL,
        jewellery TEXT DEFAULT '',
        job_type TEXT DEFAULT '',
        work TEXT DEFAULT '',
        status TEXT DEFAULT 'Pending',

        maal_aaya TEXT DEFAULT '',
        maal_diyaa TEXT DEFAULT '',

        gross_weight REAL DEFAULT 0,
        nag_weight REAL DEFAULT 0,
        stone_weight REAL DEFAULT 0,

        total_weight REAL DEFAULT 0,
        loss REAL DEFAULT 0,
        final_weight REAL DEFAULT 0,
        net_weight REAL DEFAULT 0,

        taanch TEXT DEFAULT '',
        quantity INTEGER DEFAULT 1,

        work_amount REAL DEFAULT 0,
        notes TEXT DEFAULT '',

        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(customer_id)
        REFERENCES customers(id)
        ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        date TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        mode TEXT DEFAULT 'Cash',
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(customer_id)
        REFERENCES customers(id)
        ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_jobs_customer
    ON jobs(customer_id);

    CREATE INDEX IF NOT EXISTS idx_jobs_date
    ON jobs(date);

    CREATE INDEX IF NOT EXISTS idx_payments_customer
    ON payments(customer_id);

    CREATE INDEX IF NOT EXISTS idx_payments_date
    ON payments(date);
    """)

    # --------------------------------------------------------
    # CUSTOMERS OLD DATABASE UPGRADE
    # --------------------------------------------------------

    existing = {
        r["name"]
        for r in con.execute(
            "PRAGMA table_info(customers)"
        ).fetchall()
    }

    customer_cols = {
        "mobile": "TEXT DEFAULT ''",
        "phone": "TEXT DEFAULT ''",
        "address": "TEXT DEFAULT ''",
        "notes": "TEXT DEFAULT ''",
        "active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT"
    }

    for col, definition in customer_cols.items():

        if col not in existing:

            con.execute(
                f"""
                ALTER TABLE customers
                ADD COLUMN {col} {definition}
                """
            )

    # --------------------------------------------------------
    # JOBS OLD DATABASE UPGRADE
    # --------------------------------------------------------

    existing = {
        r["name"]
        for r in con.execute(
            "PRAGMA table_info(jobs)"
        ).fetchall()
    }

    job_cols = {
        "customer_id": "INTEGER",
        "customer": "TEXT DEFAULT ''",
        "date": "TEXT",
        "jewellery": "TEXT DEFAULT ''",
        "job_type": "TEXT DEFAULT ''",
        "work": "TEXT DEFAULT ''",
        "status": "TEXT DEFAULT 'Pending'",
        "maal_aaya": "TEXT DEFAULT ''",
        "maal_diyaa": "TEXT DEFAULT ''",
        "gross_weight": "REAL DEFAULT 0",
        "nag_weight": "REAL DEFAULT 0",
        "stone_weight": "REAL DEFAULT 0",
        "total_weight": "REAL DEFAULT 0",
        "loss": "REAL DEFAULT 0",
        "final_weight": "REAL DEFAULT 0",
        "net_weight": "REAL DEFAULT 0",
        "taanch": "TEXT DEFAULT ''",
        "quantity": "INTEGER DEFAULT 1",
        "work_amount": "REAL DEFAULT 0",
        "notes": "TEXT DEFAULT ''",
        "created_at": "TEXT"
    }

    for col, definition in job_cols.items():

        if col not in existing:

            con.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN {col} {definition}
                """
            )

    # --------------------------------------------------------
    # PAYMENTS OLD DATABASE UPGRADE
    # --------------------------------------------------------

    existing = {
        r["name"]
        for r in con.execute(
            "PRAGMA table_info(payments)"
        ).fetchall()
    }

    payment_cols = {
        "customer_id": "INTEGER",
        "date": "TEXT",
        "amount": "REAL NOT NULL DEFAULT 0",
        "mode": "TEXT DEFAULT 'Cash'",
        "note": "TEXT DEFAULT ''",
        "created_at": "TEXT"
    }

    for col, definition in payment_cols.items():

        if col not in existing:

            con.execute(
                f"""
                ALTER TABLE payments
                ADD COLUMN {col} {definition}
                """
            )

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

    if not raw:
        return default

    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"{name} me valid number dalo."
        )


def parse_int(name, default=1):

    raw = request.form.get(name, "").strip()

    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"{name} me valid number dalo."
        )


def login_required(view):

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

<meta
    name="viewport"
    content="width=device-width, initial-scale=1"
>

<title>{{ title }} - R.K JEWELERS</title>

<style>

*{
    box-sizing:border-box;
}

body{
    margin:0;
    font-family:Arial,Helvetica,sans-serif;
    background:linear-gradient(
        135deg,
        #fff8df,
        #ead19a
    );
    color:#342316;
}

header{
    background:linear-gradient(
        135deg,
        #241309,
        #633a18
    );
    color:white;
    padding:18px;
    text-align:center;
    border-bottom:5px solid #e3b93f;
}

header h1{
    margin:0;
    color:#ffe39a;
    font-size:32px;
}

header p{
    margin:5px 0 0;
}

.layout{
    display:flex;
    min-height:calc(100vh - 100px);
}

nav{
    width:250px;
    background:#2b180d;
    padding:15px;
    flex:none;
}

nav a{
    display:block;
    text-decoration:none;
    color:white;
    padding:12px;
    margin:6px 0;
    border-radius:10px;
    font-weight:bold;
}

nav a:hover{
    background:#d7a72c;
    color:#241309;
}

.userbox{
    color:#ffe39a;
    padding:8px 12px;
    font-size:12px;
    border-bottom:1px solid #6d4a27;
    margin-bottom:10px;
}

main{
    flex:1;
    padding:22px;
    max-width:1700px;
    width:100%;
}

.cardbox{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:15px;
}

.card{
    background:white;
    padding:20px;
    border-radius:16px;
    box-shadow:0 8px 25px #76501f33;
    border-left:6px solid #d6a52e;
}

.card h3{
    margin:0;
    font-size:13px;
    color:#777;
}

.card b{
    display:block;
    font-size:24px;
    margin-top:8px;
}

.panel{
    background:white;
    padding:20px;
    margin:18px 0;
    border-radius:16px;
    box-shadow:0 8px 25px #76501f33;
}

.form{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:12px;
}

input,
select,
textarea{
    width:100%;
    padding:12px;
    border:1px solid #d6c19a;
    border-radius:9px;
    font-size:15px;
    background:#fffdf7;
}

textarea{
    min-height:80px;
    resize:vertical;
}

label{
    font-weight:bold;
    font-size:13px;
    display:block;
    margin-bottom:5px;
}

button,
.btn{
    border:0;
    padding:11px 15px;
    border-radius:9px;
    background:#d6a52e;
    color:#241309;
    font-weight:bold;
    cursor:pointer;
    text-decoration:none;
    display:inline-block;
}

button:hover,
.btn:hover{
    opacity:.85;
}

.green{
    background:#198754;
    color:white;
}

.red{
    background:#b52d38;
    color:white;
}

.blue{
    background:#2864c7;
    color:white;
}

.gray{
    background:#6c757d;
    color:white;
}

.small{
    padding:8px 10px;
    font-size:12px;
}

.table{
    overflow-x:auto;
}

table{
    width:100%;
    border-collapse:collapse;
    min-width:800px;
}

th{
    background:#4a2915;
    color:#ffe49b;
    padding:11px;
    text-align:left;
}

td{
    padding:10px;
    border-bottom:1px solid #eee2c9;
    vertical-align:top;
}

.msg{
    background:#dff3e6;
    padding:12px;
    border-radius:10px;
    margin-bottom:15px;
    color:#17663c;
    font-weight:bold;
}

.err{
    background:#ffe2e4;
    padding:12px;
    border-radius:10px;
    margin-bottom:15px;
    color:#8b1e2b;
    font-weight:bold;
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

.badge{
    display:inline-block;
    padding:5px 8px;
    border-radius:999px;
    background:#eee;
    font-size:12px;
    font-weight:bold;
}

.badge.green{
    background:#dff3e6;
    color:#17663c;
}

.badge.yellow{
    background:#fff1bf;
    color:#7a5b00;
}

.badge.red{
    background:#ffe2e4;
    color:#8b1e2b;
}

.muted{
    color:#777;
}

.login{
    max-width:420px;
    margin:70px auto;
}

.login .panel{
    padding:30px;
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

.two{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:15px;
}

.three{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:15px;
}

.mobile-menu{
    display:none;
    background:#2b180d;
    color:white;
    padding:10px;
    text-align:center;
}

.stat{
    font-size:25px;
    font-weight:bold;
    margin-top:8px;
}

.full{
    grid-column:1/-1;
}

@media(max-width:1000px){

    .cardbox{
        grid-template-columns:repeat(2,1fr);
    }

    .form{
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

    .form{
        grid-template-columns:1fr;
    }

    .panel{
        padding:14px;
    }

    header h1{
        font-size:25px;
    }

    .two,
    .three{
        grid-template-columns:1fr;
    }

    .toolbar .field{
        min-width:100%;
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

    .panel,
    .card{
        box-shadow:none;
    }

    main{
        max-width:none;
        padding:0;
    }
}

</style>

</head>

<body>

<header>

<h1>R.K JEWELERS</h1>

<p>
JEWELLERY JOB WORK & CUSTOMER LEDGER
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

<a href="{{ url_for('jobs') }}">💍 Job Entry</a>

<a href="{{ url_for('payments') }}">💰 Payment Entry</a>

<a href="{{ url_for('ledger') }}">📒 Customer Ledger</a>

<a href="{{ url_for('reports') }}">📊 Reports</a>

<a href="{{ url_for('search') }}">🔎 Customer Search</a>

<a href="{{ url_for('backup') }}">💾 Backup Database</a>

<a href="{{ url_for('restore') }}">♻️ Restore Backup</a>

<a href="{{ url_for('about') }}">ℹ️ Shop Information</a>

<a href="{{ url_for('logout') }}">🚪 Logout</a>

{% endif %}

</nav>

<main>

{% with messages=get_flashed_messages(category_filter=['success']) %}

{% for m in messages %}

<div class="msg">{{ m }}</div>

{% endfor %}

{% endwith %}

{% with messages=get_flashed_messages(category_filter=['error']) %}

{% for m in messages %}

<div class="err">{{ m }}</div>

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
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
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

            <h2>🔐 R.K JEWELERS Login</h2>

            <p class="muted">
                Local shop management system
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

                <button
                    class="green"
                    type="submit"
                >
                    LOGIN
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
        SELECT COUNT(*) AS c
        FROM customers
        WHERE active=1
    """).fetchone()["c"]

    jobs_count = con.execute("""
        SELECT COUNT(*) AS c
        FROM jobs
    """).fetchone()["c"]

    work_amount = con.execute("""
        SELECT COALESCE(SUM(work_amount),0) AS c
        FROM jobs
    """).fetchone()["c"]

    paid_amount = con.execute("""
        SELECT COALESCE(SUM(amount),0) AS c
        FROM payments
    """).fetchone()["c"]

    pending = con.execute("""
        SELECT COUNT(*) AS c
        FROM jobs
        WHERE status != 'Delivered'
    """).fetchone()["c"]

    con.close()

    balance = work_amount - paid_amount

    body = f"""

    <h2>🏠 Dashboard</h2>

    <div class="cardbox">

        <div class="card">
            <h3>ACTIVE CUSTOMERS</h3>
            <b>{customers_count}</b>
        </div>

        <div class="card">
            <h3>TOTAL JOBS</h3>
            <b>{jobs_count}</b>
        </div>

        <div class="card">
            <h3>TOTAL KAAM</h3>
            <b>{money(work_amount)}</b>
        </div>

        <div class="card">
            <h3>TOTAL PAYMENT</h3>
            <b>{money(paid_amount)}</b>
        </div>

        <div class="card">
            <h3>BAAKI</h3>
            <b class="debit">{money(balance)}</b>
        </div>

        <div class="card">
            <h3>PENDING JOBS</h3>
            <b>{pending}</b>
        </div>

    </div>

    <div class="panel">

        <h3>💎 R.K JEWELERS PRO</h3>

        <p>
            Jewellery Job Work, Customer Ledger,
            Payment Tracking aur Automatic Weight Calculation.
        </p>

        <div class="actions">

            <a class="btn" href="{url_for('customers')}">
                👥 Customers
            </a>

            <a class="btn" href="{url_for('jobs')}">
                💍 New Job
            </a>

            <a class="btn green" href="{url_for('payments')}">
                💰 Payment
            </a>

            <a class="btn blue" href="{url_for('ledger')}">
                📒 Ledger
            </a>

        </div>

        <br>

        <p class="muted">
            Developer: <b>KRISHNA</b>
        </p>

    </div>

    """

    return page("Dashboard", body)


@app.route("/dashboard")
@login_required
def dashboard():
    return redirect(url_for("home"))


# ============================================================
# CUSTOMERS
# ============================================================

@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():

    con = db()

    if request.method == "POST":

        action = request.form.get(
            "action",
            ""
        )

        try:

            if action == "add":

                name = request.form.get(
                    "name",
                    ""
                ).strip()

                mobile = request.form.get(
                    "mobile",
                    ""
                ).strip()

                address = request.form.get(
                    "address",
                    ""
                ).strip()

                notes = request.form.get(
                    "notes",
                    ""
                ).strip()

                if not name:
                    raise ValueError(
                        "Customer name zaroori hai."
                    )

                con.execute("""
                    INSERT INTO customers
                    (
                        name,
                        mobile,
                        phone,
                        address,
                        notes
                    )
                    VALUES(?,?,?,?,?)
                """, (
                    name,
                    mobile,
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
                SELECT COUNT(*)
                FROM jobs j
                WHERE j.customer_id=c.id
            ) AS jobs_count,

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

    body = """

    <h2>👥 Customers</h2>

    <div class="panel">

        <h3>➕ Add New Customer</h3>

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
                        placeholder="Mobile number"
                    >
                </div>

                <div>
                    <label>Address</label>
                    <input
                        name="address"
                        placeholder="Address"
                    >
                </div>

                <div class="full">
                    <label>Notes</label>
                    <textarea
                        name="notes"
                        placeholder="Notes"
                    ></textarea>
                </div>

            </div>

            <br>

            <button
                class="green"
                type="submit"
            >
                💾 Save Customer
            </button>

        </form>

    </div>

    <div class="panel">

        <h3>📋 Customer List</h3>

        <div class="table">

            <table>

                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Mobile</th>
                        <th>Jobs</th>
                        <th>Total Kaam</th>
                        <th>Paid</th>
                        <th>Baaki</th>
                        <th>Action</th>
                    </tr>
                </thead>

                <tbody>

    """

    for r in rows:

        balance = (
            float(r["total_work"] or 0)
            -
            float(r["total_paid"] or 0)
        )

        body += f"""

                    <tr>

                        <td>
                            <b>{esc(r["name"])}</b>
                            <br>
                            <span class="muted">
                                {esc(r["address"])}
                            </span>
                        </td>

                        <td>
                            {esc(r["mobile"] or r["phone"])}
                        </td>

                        <td>
                            {r["jobs_count"]}
                        </td>

                        <td>
                            {money(r["total_work"])}
                        </td>

                        <td class="credit">
                            {money(r["total_paid"])}
                        </td>

                        <td class="debit">
                            {money(balance)}
                        </td>

                        <td>

                            <div class="actions">

                                <a
                                    class="btn small"
                                    href="{url_for(
                                        'ledger',
                                        customer_id=r['id']
                                    )}"
                                >
                                    📒 Ledger
                                </a>

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
                                        value="{r['id']}"
                                    >

                                    <button
                                        class="red small"
                                        type="submit"
                                    >
                                        Delete
                                    </button>

                                </form>

                            </div>

                        </td>

                    </tr>

        """

    body += """

                </tbody>

            </table>

        </div>

    </div>

    """

    return page("Customers", body)


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

        customers_rows = con.execute("""
            SELECT *
            FROM customers
            WHERE active=1
            AND (
                name LIKE ?
                OR mobile LIKE ?
                OR phone LIKE ?
                OR address LIKE ?
            )
            ORDER BY name
        """, (
            f"%{q}%",
            f"%{q}%",
            f"%{q}%",
            f"%{q}%"
        )).fetchall()

    else:

        customers_rows = []

    con.close()

    body = f"""

    <div class="panel">

        <h2>🔎 Customer Search</h2>

        <form method="get">

            <div class="toolbar">

                <div class="field">

                    <label>
                        Customer Name / Mobile
                    </label>

                    <input
                        type="text"
                        name="q"
                        value="{esc(q)}"
                        placeholder="Search customer..."
                        autofocus
                    >

                </div>

                <button
                    type="submit"
                    class="blue"
                >
                    🔍 Search
                </button>

                <a
                    href="{url_for('search')}"
                    class="btn gray"
                >
                    Clear
                </a>

            </div>

        </form>

    </div>

    """

    if q:

        body += """

        <div class="panel">

            <h3>Search Results</h3>

            <div class="table">

                <table>

                    <thead>

                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Mobile</th>
                            <th>Address</th>
                            <th>Action</th>
                        </tr>

                    </thead>

                    <tbody>

        """

        if customers_rows:

            for c in customers_rows:

                body += f"""

                        <tr>

                            <td>{c["id"]}</td>

                            <td>
                                <b>{esc(c["name"])}</b>
                            </td>

                            <td>
                                {esc(c["mobile"] or c["phone"])}
                            </td>

                            <td>
                                {esc(c["address"])}
                            </td>

                            <td>

                                <a
                                    class="btn small"
                                    href="{url_for(
                                        'ledger',
                                        customer_id=c['id']
                                    )}"
                                >
                                    📒 Ledger
                                </a>

                            </td>

                        </tr>

                """

        else:

            body += """

                        <tr>

                            <td
                                colspan="5"
                                class="muted"
                            >
                                Customer nahi mila.
                            </td>

                        </tr>

            """

        body += """

                    </tbody>

                </table>

            </div>

        </div>

        """

    return page(
        "Customer Search",
        body
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

            customer_id = request.form.get(
                "customer_id",
                ""
            ).strip()

            date_value = request.form.get(
                "date",
                ""
            ).strip()

            jewellery = request.form.get(
                "jewellery",
                ""
            ).strip()

            work_type = request.form.get(
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

            # AUTOMATIC CALCULATION
            total_weight = (
                gross_weight +
                nag_weight
            )

            net_weight = (
                total_weight -
                loss
            )

            stone_weight = nag_weight

            taanch = request.form.get(
                "taanch",
                ""
            ).strip()

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
                date_value = datetime.now().strftime(
                    "%Y-%m-%d"
                )

            if not jewellery:
                raise ValueError(
                    "Jewellery name zaroori hai."
                )

            if gross_weight < 0:
                raise ValueError(
                    "वजन negative nahi ho sakta."
                )

            if nag_weight < 0:
                raise ValueError(
                    "नग वजन negative nahi ho sakta."
                )

            if loss < 0:
                raise ValueError(
                    "लॉस negative nahi ho sakta."
                )

            if net_weight < 0:
                raise ValueError(
                    "अंतिम वजन negative nahi ho sakta."
                )

            if quantity < 1:
                raise ValueError(
                    "नग kam se kam 1 hona chahiye."
                )

            if work_amount < 0:
                raise ValueError(
                    "Amount negative nahi ho sakta."
                )

            customer = con.execute("""
                SELECT name
                FROM customers
                WHERE id=?
            """, (customer_id,)).fetchone()

            if not customer:
                raise ValueError(
                    "Customer nahi mila."
                )

            data = (
                customer_id,
                customer["name"],
                date_value,
                jewellery,
                work_type,
                status,
                maal_aaya,
                maal_diyaa,
                gross_weight,
                nag_weight,
                stone_weight,
                total_weight,
                loss,
                net_weight,
                net_weight,
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
                        customer=?,
                        date=?,
                        jewellery=?,
                        job_type=?,
                        work=?,
                        status=?,
                        maal_aaya=?,
                        maal_diyaa=?,
                        gross_weight=?,
                        nag_weight=?,
                        stone_weight=?,
                        total_weight=?,
                        loss=?,
                        final_weight=?,
                        net_weight=?,
                        taanch=?,
                        quantity=?,
                        work_amount=?,
                        notes=?
                    WHERE id=?
                """, data + (edit_id,))

                message = (
                    "Job entry update ho gayi."
                )

            else:

                con.execute("""
                    INSERT INTO jobs
                    (
                        customer_id,
                        customer,
                        date,
                        jewellery,
                        job_type,
                        work,
                        status,
                        maal_aaya,
                        maal_diyaa,
                        gross_weight,
                        nag_weight,
                        stone_weight,
                        total_weight,
                        loss,
                        final_weight,
                        net_weight,
                        taanch,
                        quantity,
                        work_amount,
                        notes
                    )
                    VALUES(
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?
                    )
                """, data)

                message = (
                    "Job entry save ho gayi."
                )

            con.commit()
            con.close()

            flash(
                message,
                "success"
            )

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
        SELECT id,name
        FROM customers
        WHERE active=1
        ORDER BY name
    """).fetchall()

    rows = con.execute("""
        SELECT
            j.*,
            COALESCE(
                c.name,
                j.customer,
                ''
            ) AS customer_name
        FROM jobs j
        LEFT JOIN customers c
            ON c.id=j.customer_id
        ORDER BY
            j.date DESC,
            j.id DESC
    """).fetchall()

    con.close()

    if edit_job:

        selected_customer = str(
            edit_job["customer_id"] or ""
        )

        form_date = edit_job["date"] or ""

        form_jewellery = (
            edit_job["jewellery"] or ""
        )

        form_work = (
            edit_job["work"]
            or edit_job["job_type"]
            or "Other"
        )

        form_status = (
            edit_job["status"]
            or "Pending"
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
            edit_job["nag_weight"]
            if edit_job["nag_weight"] is not None
            else edit_job["stone_weight"] or 0
        )

        form_loss = (
            edit_job["loss"] or 0
        )

        form_taanch = (
            edit_job["taanch"] or ""
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

        heading = "✏️ Edit Job Entry"
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
        form_taanch = ""
        form_quantity = 1
        form_amount = 0
        form_notes = ""

        heading = "➕ New Job Entry"
        button_text = "SAVE JOB"

    customer_options = ""

    for c in customers_rows:

        selected = (
            "selected"
            if selected_customer ==
            str(c["id"])
            else ""
        )

        customer_options += f"""
        <option
            value="{c["id"]}"
            {selected}
        >
            {esc(c["name"])}
        </option>
        """

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

                        {customer_options}

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
                            value="Nag Setting"
                            {"selected" if form_work == "Nag Setting" else ""}
                        >
                            Nag Setting
                        </option>

                        <option
                            value="Kachi Jadai"
                            {"selected" if form_work == "Kachi Jadai" else ""}
                        >
                            Kachi Jadai
                        </option>

                        <option
                            value="Chilai"
                            {"selected" if form_work == "Chilai" else ""}
                        >
                            Chilai
                        </option>

                        <option
                            value="Other"
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


            <hr>


            <h3>⚖️ वजन विवरण</h3>

            <div class="form">

                <div>
                    <label>वजन</label>

                    <input
                        type="number"
                        step="0.001"
                        min="0"
                        name="gross_weight"
                        id="gross_weight"
                        value="{form_gross}"
                        oninput="calculateWeight()"
                    >
                </div>


                <div>
                    <label>+नग वजन</label>

                    <input
                        type="number"
                        step="0.001"
                        min="0"
                        name="nag_weight"
                        id="nag_weight"
                        value="{form_nag}"
                        oninput="calculateWeight()"
                    >
                </div>


                <div>
                    <label>=कुल वजन</label>

                    <input
                        type="number"
                        step="0.001"
                        id="total_weight"
                        value="0"
                        readonly
                    >
                </div>


                <div>
                    <label>-लॉस</label>

                    <input
                        type="number"
                        step="0.001"
                        min="0"
                        name="loss"
                        id="loss"
                        value="{form_loss}"
                        oninput="calculateWeight()"
                    >
                </div>


                <div>
                    <label>=अंतिम वजन</label>

                    <input
                        type="number"
                        step="0.001"
                        id="net_weight"
                        value="0"
                        readonly
                    >
                </div>


                <div>
                    <label>ताँच</label>

                    <input
                        name="taanch"
                        value="{esc(form_taanch)}"
                        placeholder="ताँच"
                    >
                </div>

            </div>


            <br>


            <div>
                <label>Notes</label>

                <textarea
                    name="notes"
                    placeholder="Extra notes..."
                >{esc(form_notes)}</textarea>
            </div>


            <br>


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

        <h3>📋 Job Records</h3>

        <div class="table">

            <table>

                <thead>

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

                </thead>

                <tbody>

    """

    for r in rows:

        gross = float(
            r["gross_weight"] or 0
        )

        nag = float(
            r["nag_weight"]
            if r["nag_weight"] is not None
            else r["stone_weight"] or 0
        )

        total = float(
            r["total_weight"]
            if r["total_weight"] is not None
            else gross + nag
        )

        loss = float(
            r["loss"] or 0
        )

        net = float(
            r["net_weight"]
            if r["net_weight"] is not None
            else total - loss
        )

        body += f"""

                    <tr>

                        <td>{r["id"]}</td>

                        <td>
                            {esc(r["date"])}
                        </td>

                        <td>
                            <b>
                                {esc(r["customer_name"])}
                            </b>
                        </td>

                        <td>
                            {esc(r["jewellery"])}
                        </td>

                        <td>
                            {esc(
                                r["work"]
                                or r["job_type"]
                            )}
                        </td>

                        <td>
                            वजन:
                            {gross:.3f} g
                            <br>

                            +नग वजन:
                            {nag:.3f} g
                            <br>

                            =कुल वजन:
                            {total:.3f} g
                            <br>

                            -लॉस:
                            {loss:.3f} g
                            <br>

                            =अंतिम वजन:
                            {net:.3f} g
                        </td>

                        <td>
                            {esc(r["taanch"])}
                            <br>
                            नग: {r["quantity"] or 1}
                        </td>

                        <td>
                            {money(r["work_amount"])}
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
                                    EDIT
                                </a>

                                <form
                                    method="post"
                                    action="{url_for(
                                        'delete_job',
                                        job_id=r['id']
                                    )}"
                                    style="display:inline"
                                    onsubmit="return confirm('Delete job?')"
                                >

                                    <button
                                        class="red small"
                                        type="submit"
                                    >
                                        DELETE
                                    </button>

                                </form>

                            </div>

                        </td>

                    </tr>

        """

    body += """

                </tbody>

            </table>

        </div>

    </div>


    <script>

    function calculateWeight(){

        const weight =
            parseFloat(
                document.getElementById(
                    "gross_weight"
                ).value
            ) || 0;

        const nagWeight =
            parseFloat(
                document.getElementById(
                    "nag_weight"
                ).value
            ) || 0;

        const loss =
            parseFloat(
                document.getElementById(
                    "loss"
                ).value
            ) || 0;

        const total =
            weight + nagWeight;

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
# TOGGLE CUSTOMER
# ============================================================

@app.post("/customers/toggle/<int:cid>")
@login_required
def toggle_customer(cid):

    con = db()

    c = con.execute("""
        SELECT active
        FROM customers
        WHERE id=?
    """, (cid,)).fetchone()

    if not c:

        con.close()

        flash(
            "Customer nahi mila.",
            "error"
        )

        return redirect(
            url_for("customers")
        )

    new_status = (
        0
        if c["active"]
        else 1
    )

    con.execute("""
        UPDATE customers
        SET active=?
        WHERE id=?
    """, (
        new_status,
        cid
    ))

    con.commit()
    con.close()

    flash(
        "Customer status update ho gaya.",
        "success"
    )

    return redirect(
        url_for("customers")
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

            if amount <= 0:
                raise ValueError(
                    "Payment amount 0 se zyada hona chahiye."
                )

            if not date_value:
                date_value = datetime.now().strftime(
                    "%Y-%m-%d"
                )

            customer = con.execute("""
                SELECT id
                FROM customers
                WHERE id=?
            """, (customer_id,)).fetchone()

            if not customer:
                raise ValueError(
                    "Customer select karo."
                )

            con.execute("""
                INSERT INTO payments
                (
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

    payments_rows = con.execute("""
        SELECT
            p.*,
            c.name AS customer_name
        FROM payments p
        JOIN customers c
            ON c.id=p.customer_id
        ORDER BY
            p.date DESC,
            p.id DESC
    """).fetchall()

    con.close()

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    body = f"""

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
    """

    for c in customers_rows:

        body += f"""
                        <option value="{c["id"]}">
                            {esc(c["name"])}
                        </option>
        """

    body += f"""

                    </select>

                </div>


                <div>

                    <label>Date</label>

                    <input
                        type="date"
                        name="date"
                        value="{today}"
                        required
                    >

                </div>


                <div>

                    <label>Amount</label>

                    <input
                        type="number"
                        name="amount"
                        step="0.01"
                        min="0"
                        value="0"
                        required
                    >

                </div>


                <div>

                    <label>Payment Mode</label>

                    <select name="mode">

                        <option>Cash</option>
                        <option>UPI</option>
                        <option>Bank</option>
                        <option>Other</option>

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

            <button
                type="submit"
                class="green"
            >
                💾 Save Payment
            </button>

        </form>

    </div>


    <div class="panel">

        <h3>📋 Payment Records</h3>

        <div class="table">

            <table>

                <thead>

                    <tr>
                        <th>Date</th>
                        <th>Customer</th>
                        <th>Amount</th>
                        <th>Mode</th>
                        <th>Note</th>
                    </tr>

                </thead>

                <tbody>

    """

    for p in payments_rows:

        body += f"""

                    <tr>

                        <td>
                            {esc(p["date"])}
                        </td>

                        <td>
                            {esc(p["customer_name"])}
                        </td>

                        <td class="credit">
                            {money(p["amount"])}
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

                </tbody>

            </table>

        </div>

    </div>

    """

    return page(
        "Payments",
        body
    )


# ============================================================
# LEDGER
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
        ORDER BY name
    """).fetchall()

    if not customer_id:

        con.close()

        body = """

        <div class="panel">

            <h2>📒 Customer Ledger</h2>

            <p>
                Ledger dekhne ke liye customer select karo.
            </p>

            <form method="get">

                <select
                    name="customer_id"
                    required
                >

                    <option value="">
                        Select Customer
                    </option>

        """

        for c in customers_rows:

            body += f"""
                    <option value="{c["id"]}">
                        {esc(c["name"])}
                    </option>
            """

        body += """

                </select>

                <br><br>

                <button
                    class="blue"
                    type="submit"
                >
                    📒 Open Ledger
                </button>

            </form>

        </div>

        """

        con.close()

        return page(
            "Ledger",
            body
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

    balance = total_work - total_paid

    con.close()

    body = f"""

    <div class="panel">

        <div class="actions no-print">

            <a
                class="btn gray"
                href="{url_for('ledger')}"
            >
                ← Customers
            </a>

            <button
                class="btn"
                onclick="window.print()"
            >
                🖨️ Print
            </button>

        </div>

        <h2>
            📒 Customer Ledger
        </h2>

        <h3>
            {esc(customer["name"])}
        </h3>

        <p>
            Mobile:
            <b>{esc(customer["mobile"] or customer["phone"])}</b>
        </p>

        <p>
            Address:
            <b>{esc(customer["address"])}</b>
        </p>

    </div>


    <div class="cardbox">

        <div class="card">
            <h3>TOTAL KAAM</h3>
            <div class="stat">
                {money(total_work)}
            </div>
        </div>

        <div class="card">
            <h3>TOTAL PAID</h3>
            <div class="stat credit">
                {money(total_paid)}
            </div>
        </div>

        <div class="card">
            <h3>BAAKI</h3>
            <div class="stat debit">
                {money(balance)}
            </div>
        </div>

    </div>


    <div class="panel">

        <h3>💍 Job Entries</h3>

        <div class="table">

            <table>

                <thead>

                    <tr>
                        <th>Date</th>
                        <th>Jewellery</th>
                        <th>Work</th>
                        <th>Final Weight</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>

                </thead>

                <tbody>

    """

    for j in jobs_rows:

        body += f"""

                    <tr>

                        <td>
                            {esc(j["date"])}
                        </td>

                        <td>
                            {esc(j["jewellery"])}
                        </td>

                        <td>
                            {esc(
                                j["work"]
                                or j["job_type"]
                            )}
                        </td>

                        <td>
                            {float(j["net_weight"] or 0):.3f} g
                        </td>

                        <td class="debit">
                            {money(j["work_amount"])}
                        </td>

                        <td>
                            {esc(j["status"])}
                        </td>

                    </tr>

        """

    body += """

                </tbody>

            </table>

        </div>

    </div>


    <div class="panel">

        <h3>💰 Payments</h3>

        <div class="table">

            <table>

                <thead>

                    <tr>
                        <th>Date</th>
                        <th>Amount</th>
                        <th>Mode</th>
                        <th>Note</th>
                    </tr>

                </thead>

                <tbody>

    """

    for p in payment_rows:

        body += f"""

                    <tr>

                        <td>
                            {esc(p["date"])}
                        </td>

                        <td class="credit">
                            {money(p["amount"])}
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

                </tbody>

            </table>

        </div>

    </div>

    """

    return page(
        "Customer Ledger",
        body
    )


# ============================================================
# REPORTS
# ============================================================

@app.route("/reports")
@login_required
def reports():

    con = db()

    total_jobs = con.execute("""
        SELECT COUNT(*) AS c
        FROM jobs
    """).fetchone()["c"]

    total_work = con.execute("""
        SELECT COALESCE(SUM(work_amount),0) AS c
        FROM jobs
    """).fetchone()["c"]

    total_paid = con.execute("""
        SELECT COALESCE(SUM(amount),0) AS c
        FROM payments
    """).fetchone()["c"]

    pending = con.execute("""
        SELECT COUNT(*) AS c
        FROM jobs
        WHERE status != 'Delivered'
    """).fetchone()["c"]

    work_types = con.execute("""
        SELECT
            COALESCE(work,'Other') AS work,
            COUNT(*) AS count,
            COALESCE(SUM(work_amount),0) AS amount
        FROM jobs
        GROUP BY work
        ORDER BY amount DESC
    """).fetchall()

    recent_jobs = con.execute("""
        SELECT
            j.*,
            COALESCE(c.name,j.customer,'') AS customer_name
        FROM jobs j
        LEFT JOIN customers c
            ON c.id=j.customer_id
        ORDER BY j.id DESC
        LIMIT 20
    """).fetchall()

    con.close()

    body = f"""

    <div class="actions no-print">

        <button
            class="btn"
            onclick="window.print()"
        >
            🖨️ Print Report
        </button>

    </div>

    <h2>📊 Reports</h2>

    <div class="cardbox">

        <div class="card">
            <h3>TOTAL JOBS</h3>
            <b>{total_jobs}</b>
        </div>

        <div class="card">
            <h3>TOTAL KAAM</h3>
            <b>{money(total_work)}</b>
        </div>

        <div class="card">
            <h3>TOTAL PAYMENT</h3>
            <b>{money(total_paid)}</b>
        </div>

        <div class="card">
            <h3>BAAKI</h3>
            <b class="debit">
                {money(total_work-total_paid)}
            </b>
        </div>

    </div>


    <div class="panel">

        <h3>📈 Work Summary</h3>

        <div class="table">

            <table>

                <thead>
                    <tr>
                        <th>Work</th>
                        <th>Jobs</th>
                        <th>Amount</th>
                    </tr>
                </thead>

                <tbody>

    """

    for w in work_types:

        body += f"""

                    <tr>

                        <td>
                            {esc(w["work"])}
                        </td>

                        <td>
                            {w["count"]}
                        </td>

                        <td>
                            {money(w["amount"])}
                        </td>

                    </tr>

        """

    body += """

                </tbody>

            </table>

        </div>

    </div>


    <div class="panel">

        <h3>
            📋 Recent Jobs
        </h3>

        <div class="table">

            <table>

                <thead>

                    <tr>
                        <th>Date</th>
                        <th>Customer</th>
                        <th>Jewellery</th>
                        <th>Work</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>

                </thead>

                <tbody>

    """

    for j in recent_jobs:

        body += f"""

                    <tr>

                        <td>
                            {esc(j["date"])}
                        </td>

                        <td>
                            {esc(j["customer_name"])}
                        </td>

                        <td>
                            {esc(j["jewellery"])}
                        </td>

                        <td>
                            {esc(j["work"] or j["job_type"])}
                        </td>

                        <td>
                            {money(j["work_amount"])}
                        </td>

                        <td>
                            {esc(j["status"])}
                        </td>

                    </tr>

        """

    body += """

                </tbody>

            </table>

        </div>

    </div>

    """

    return page(
        "Reports",
        body
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

@app.route("/restore", methods=["GET", "POST"])
@login_required
def restore():

    if request.method == "POST":

        file = request.files.get(
            "backup_file"
        )

        if not file or not file.filename:

            flash(
                "Backup file select karo.",
                "error"
            )

            return redirect(
                url_for("restore")
            )

        try:

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            safety_backup = (
                BACKUP_DIR
                /
                f"before_restore_{timestamp}.db"
            )

            if DB.exists():

                shutil.copy2(
                    DB,
                    safety_backup
                )

            temp_path = (
                BACKUP_DIR
                /
                f"restore_{timestamp}.db"
            )

            file.save(temp_path)

            # Check SQLite database
            test = sqlite3.connect(
                temp_path
            )

            test.execute(
                "PRAGMA integrity_check"
            ).fetchone()

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
                "Database restore ho gaya.",
                "success"
            )

        except Exception as e:

            flash(
                f"Restore failed: {e}",
                "error"
            )

        return redirect(
            url_for("restore")
        )

    body = """

    <div class="panel">

        <h2>♻️ Restore Database</h2>

        <p class="muted">
            Restore karne se current database replace ho jayega.
            Safety backup automatically banega.
        </p>

        <form
            method="post"
            enctype="multipart/form-data"
            onsubmit="return confirm('Database restore karna hai?')"
        >

            <label>
                Backup Database File
            </label>

            <input
                type="file"
                name="backup_file"
                accept=".db"
                required
            >

            <br><br>

            <button
                class="red"
                type="submit"
            >
                ♻️ Restore Database
            </button>

        </form>

    </div>

    """

    return page(
        "Restore",
        body
    )


# ============================================================
# SHOP INFORMATION
# ============================================================

@app.route("/about")
@login_required
def about():

    body = """

    <div class="panel">

        <h2>ℹ️ R.K JEWELERS</h2>

        <h3>Jewellery Job Work Management</h3>

        <p>
            Nag Setting
        </p>

        <p>
            Kachi Jadai
        </p>

        <p>
            Chilai
        </p>

        <hr>

        <p>
            <b>Developer:</b> KRISHNA
        </p>

        <p class="muted">
            R.K JEWELERS PRO
        </p>

    </div>

    """

    return page(
        "Shop Information",
        body
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):

    body = """

    <div class="panel">

        <h2>❌ Page Not Found</h2>

        <p>
            Ye page available nahi hai.
        </p>

        <a
            class="btn"
            href="/"
        >
            🏠 Dashboard
        </a>

    </div>

    """

    return page(
        "Page Not Found",
        body
    ), 404


@app.errorhandler(500)
def internal_error(error):

    body = """

    <div class="panel">

        <h2>⚠️ Application Error</h2>

        <p>
            Application me error aa gaya.
        </p>

        <a
            class="btn"
            href="/"
        >
            🏠 Dashboard
        </a>

    </div>

    """

    return page(
        "Application Error",
        body
    ), 500


# ============================================================
# START APPLICATION
# ============================================================

setup()


if __name__ == "__main__":

    print("=" * 55)
    print("              R.K JEWELERS PRO")
    print("=" * 55)
    print("Developer : KRISHNA")
    print("Server    : http://127.0.0.1:5000")
    print("Username  : admin")
    print("Password  : 1234")
    print("=" * 55)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
