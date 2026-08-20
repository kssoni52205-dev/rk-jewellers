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
# PDF
# ============================================================

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

# ============================================================
# APP SETTINGS
# ============================================================

APP_DIR = Path(__file__).resolve().parent

DB = APP_DIR / "rk_jewellers.db"

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

ADMIN_USER = os.environ.get(
    "RK_ADMIN_USER",
    "admin"
)

ADMIN_PASSWORD = os.environ.get(
    "RK_ADMIN_PASSWORD",
    "1234"
)

ADMIN_PASSWORD_HASH = generate_password_hash(
    ADMIN_PASSWORD
)

# ============================================================
# DATABASE
# ============================================================

def db():
    con = sqlite3.connect(DB)

    con.row_factory = sqlite3.Row

    con.execute(
        "PRAGMA foreign_keys = ON"
    )

    return con


def setup():

    con = db()

    con.executescript("""
    
    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT DEFAULT '',
        address TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

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

        quantity INTEGER DEFAULT 1,

        taanch TEXT DEFAULT '',

        work_amount REAL DEFAULT 0,

        notes TEXT DEFAULT '',

        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(customer_id)
        REFERENCES customers(id)
        ON DELETE CASCADE
    );

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

    # ========================================================
    # OLD DATABASE UPGRADE
    # ========================================================

    customer_columns = {
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(customers)"
        ).fetchall()
    }

    customer_add = {
        "mobile": "TEXT DEFAULT ''",
        "address": "TEXT DEFAULT ''",
        "notes": "TEXT DEFAULT ''",
        "active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT"
    }

    for column, definition in customer_add.items():

        if column not in customer_columns:

            con.execute(
                f"""
                ALTER TABLE customers
                ADD COLUMN {column} {definition}
                """
            )

    job_columns = {
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(jobs)"
        ).fetchall()
    }

    job_add = {
        "status": "TEXT NOT NULL DEFAULT 'Pending'",
        "maal_aaya": "TEXT DEFAULT ''",
        "maal_diyaa": "TEXT DEFAULT ''",
        "gross_weight": "REAL DEFAULT 0",
        "nag_weight": "REAL DEFAULT 0",
        "total_weight": "REAL DEFAULT 0",
        "loss": "REAL DEFAULT 0",
        "final_weight": "REAL DEFAULT 0",
        "stone_weight": "REAL DEFAULT 0",
        "net_weight": "REAL DEFAULT 0",
        "quantity": "INTEGER DEFAULT 1",
        "taanch": "TEXT DEFAULT ''",
        "work_amount": "REAL DEFAULT 0",
        "notes": "TEXT DEFAULT ''",
        "created_at": "TEXT"
    }

    for column, definition in job_add.items():

        if column not in job_columns:

            con.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN {column} {definition}
                """
            )

    payment_columns = {
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(payments)"
        ).fetchall()
    }

    if "mode" not in payment_columns:

        con.execute(
            """
            ALTER TABLE payments
            ADD COLUMN mode TEXT NOT NULL DEFAULT 'Cash'
            """
        )

    if "note" not in payment_columns:

        con.execute(
            """
            ALTER TABLE payments
            ADD COLUMN note TEXT DEFAULT ''
            """
        )

    if "created_at" not in payment_columns:

        con.execute(
            """
            ALTER TABLE payments
            ADD COLUMN created_at TEXT
            """
        )

    con.commit()
    con.close()


# ============================================================
# HELPERS
# ============================================================

def money(value):

    return "₹ {:,.2f}".format(
        float(value or 0)
    )


def esc(value):

    return html.escape(
        "" if value is None else str(value)
    )


def parse_float(name, default=0.0):

    raw = request.form.get(
        name,
        ""
    ).strip()

    if not raw:
        return default

    try:
        value = float(raw)

    except ValueError:

        raise ValueError(
            f"{name} me valid number dalo."
        )

    if value < 0:

        raise ValueError(
            f"{name} negative nahi ho sakta."
        )

    return value


def parse_int(name, default=1):

    raw = request.form.get(
        name,
        ""
    ).strip()

    if not raw:
        return default

    try:
        value = int(raw)

    except ValueError:

        raise ValueError(
            f"{name} me valid number dalo."
        )

    return value


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("logged_in"):

            return redirect(
                url_for("login")
            )

        return view(
            *args,
            **kwargs
        )

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

<title>
    {{ title }} - R.K JEWELERS
</title>

<style>

*{
    box-sizing:border-box;
}

body{

    margin:0;

    font-family:
        Arial,
        "Noto Sans Devanagari",
        sans-serif;

    background:
        linear-gradient(
            135deg,
            #fff8df,
            #ead19a
        );

    color:#342316;
}

header{

    background:
        linear-gradient(
            135deg,
            #241309,
            #633a18
        );

    color:white;

    padding:18px;

    text-align:center;

    border-bottom:
        5px solid #e3b93f;
}

header h1{

    margin:0;

    color:#ffe39a;

    font-size:32px;
}

header p{

    margin:5px 0 0;

    color:#fff;
}

.layout{

    display:flex;

    min-height:
        calc(100vh - 100px);
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

    border-bottom:
        1px solid #6d4a27;

    margin-bottom:10px;
}

main{

    flex:1;

    padding:22px;

    max-width:1700px;
}

.cardbox{

    display:grid;

    grid-template-columns:
        repeat(4,1fr);

    gap:15px;
}

.card{

    background:white;

    padding:20px;

    border-radius:16px;

    box-shadow:
        0 8px 25px #76501f33;

    border-left:
        6px solid #d6a52e;
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

    box-shadow:
        0 8px 25px #76501f33;
}

.form{

    display:grid;

    grid-template-columns:
        repeat(3,1fr);

    gap:12px;
}

input,
select,
textarea{

    width:100%;

    padding:12px;

    border:
        1px solid #d6c19a;

    border-radius:9px;

    font-size:15px;

    background:#fffdf7;
}

textarea{

    min-height:80px;
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

    opacity:.88;
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

    min-width:900px;
}

th{

    background:#4a2915;

    color:#ffe49b;

    padding:11px;

    text-align:left;

    white-space:nowrap;
}

td{

    padding:10px;

    border-bottom:
        1px solid #eee2c9;

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

.login{

    max-width:420px;

    margin:70px auto;
}

.login .panel{

    padding:30px;
}

.mobile-menu{

    display:none;

    background:#2b180d;

    color:white;

    padding:10px;

    text-align:center;
}

.stat{

    font-size:28px;

    font-weight:bold;

    margin-top:8px;
}

.info-grid{

    display:grid;

    grid-template-columns:
        repeat(2,1fr);

    gap:15px;
}

@media(max-width:1000px){

    .cardbox{

        grid-template-columns:
            repeat(2,1fr);
    }

    .form{

        grid-template-columns:
            repeat(2,1fr);
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

        grid-template-columns:
            repeat(2,1fr);

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

    .info-grid{

        grid-template-columns:1fr;
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

<h1>
    R.K JEWELERS
</h1>

<p>
    JEWELLERY JOB WORK & CUSTOMER LEDGER
</p>

</header>

<div class="mobile-menu">

<button
    onclick="
        document
        .getElementById('nav')
        .classList.toggle('show')
    "
>
    ☰ MENU
</button>

</div>

<div class="layout">

<nav id="nav">

{% if session.get('logged_in') %}

<div class="userbox">
    Logged in as {{ session.get('user') }}
</div>

<a href="{{ url_for('home') }}">
    🏠 Dashboard
</a>

<a href="{{ url_for('customers') }}">
    👥 Customers
</a>

<a href="{{ url_for('jobs') }}">
    💍 Job Entry
</a>

<a href="{{ url_for('payments') }}">
    💰 Payment Entry
</a>

<a href="{{ url_for('ledger') }}">
    📒 Customer Ledger
</a>

<a href="{{ url_for('reports') }}">
    📊 Reports
</a>

<a href="{{ url_for('backup') }}">
    💾 Backup Database
</a>

<a href="{{ url_for('restore') }}">
    ♻️ Restore Backup
</a>

<a href="{{ url_for('about') }}">
    ℹ️ Shop Information
</a>

<a href="{{ url_for('logout') }}">
    🚪 Logout
</a>

{% endif %}

</nav>

<main>

{% with messages =
    get_flashed_messages(
        category_filter=['success']
    )
%}

{% for m in messages %}

<div class="msg">
    {{ m }}
</div>

{% endfor %}

{% endwith %}


{% with messages =
    get_flashed_messages(
        category_filter=['error']
    )
%}

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

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USER
            and check_password_hash(
                ADMIN_PASSWORD_HASH,
                password
            )
        ):

            session.clear()

            session["logged_in"] = True

            session["user"] = username

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

            <h2>
                🔐 R.K JEWELERS Login
            </h2>

            <p class="muted">
                Shop Management System
            </p>

            <form method="post">

                <label>
                    Username
                </label>

                <input
                    name="username"
                    required
                    autocomplete="username"
                >

                <br><br>

                <label>
                    Password / PIN
                </label>

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
                    🔐 LOGIN
                </button>

            </form>

        </div>

    </div>

    """

    return page(
        "Login",
        body
    )


@app.get("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/")
@login_required
def home():

    con = db()

    customers_count = con.execute(
        """
        SELECT COUNT(*)
        FROM customers
        WHERE active=1
        """
    ).fetchone()[0]

    jobs_count = con.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        """
    ).fetchone()[0]

    total_work = con.execute(
        """
        SELECT COALESCE(
            SUM(work_amount),0
        )
        FROM jobs
        """
    ).fetchone()[0]

    total_paid = con.execute(
        """
        SELECT COALESCE(
            SUM(amount),0
        )
        FROM payments
        """
    ).fetchone()[0]

    pending = con.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE status != 'Delivered'
        """
    ).fetchone()[0]

    con.close()

    balance = (
        float(total_work or 0)
        -
        float(total_paid or 0)
    )

    body = f"""

    <h2>
        🏠 Dashboard
    </h2>

    <div class="cardbox">

        <div class="card">
            <h3>
                👥 Active Customers
            </h3>
            <b>
                {customers_count}
            </b>
        </div>

        <div class="card">
            <h3>
                💍 Total Jobs
            </h3>
            <b>
                {jobs_count}
            </b>
        </div>

        <div class="card">
            <h3>
                💰 Total Kaam
            </h3>
            <b>
                {money(total_work)}
            </b>
        </div>

        <div class="card">
            <h3>
                💵 Total Paid
            </h3>
            <b>
                {money(total_paid)}
            </b>
        </div>

    </div>

    <div class="cardbox">

        <div class="card">
            <h3>
                ⏳ Pending Jobs
            </h3>
            <b>
                {pending}
            </b>
        </div>

        <div class="card">
            <h3>
                📒 Total Baaki
            </h3>
            <b class="debit">
                {money(balance)}
            </b>
        </div>

    </div>

    <div class="panel">

        <h2>
            💎 R.K JEWELERS
        </h2>

        <p>
            Jewellery Job Work Management System
        </p>

        <div class="actions">

            <span class="badge yellow">
                Nag Setting
            </span>

            <span class="badge yellow">
                Kachi Jadai
            </span>

            <span class="badge yellow">
                Chilai
            </span>

            <span class="badge green">
                Customer Ledger
            </span>

            <span class="badge green">
                Automatic Weight Calculation
            </span>

            <span class="badge">
                PDF Reports
            </span>

        </div>

        <br>

        <p class="muted">
            Developer: <b>KRISHNA</b>
        </p>

    </div>

    """

    return page(
        "Dashboard",
        body
    )


# ============================================================
# CUSTOMERS
# ============================================================

@app.route(
    "/customers",
    methods=["GET", "POST"]
)
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

                con.execute(
                    """
                    INSERT INTO customers
                    (
                        name,
                        mobile,
                        address,
                        notes
                    )
                    VALUES(?,?,?,?)
                    """,
                    (
                        name,
                        mobile,
                        address,
                        notes
                    )
                )

                con.commit()

                flash(
                    "Customer successfully add ho gaya.",
                    "success"
                )

            elif action == "delete":

                customer_id = int(
                    request.form.get(
                        "customer_id",
                        "0"
                    )
                )

                con.execute(
                    """
                    UPDATE customers
                    SET active=0
                    WHERE id=?
                    """,
                    (customer_id,)
                )

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

        finally:

            con.close()

        return redirect(
            url_for("customers")
        )

    rows = con.execute(
        """
        SELECT
            c.*,

            COUNT(j.id)
                AS jobs_count,

            COALESCE(
                SUM(j.work_amount),
                0
            )
                AS total_work,

            COALESCE(
                (
                    SELECT SUM(p.amount)
                    FROM payments p
                    WHERE p.customer_id=c.id
                ),
                0
            )
                AS total_paid

        FROM customers c

        LEFT JOIN jobs j
            ON j.customer_id=c.id

        WHERE c.active=1

        GROUP BY c.id

        ORDER BY c.name
        """
    ).fetchall()

    con.close()

    body = """

    <h2>
        👥 Customers
    </h2>

    <div class="panel">

        <h3>
            ➕ Add New Customer
        </h3>

        <form method="post">

            <input
                type="hidden"
                name="action"
                value="add"
            >

            <div class="form">

                <div>
                    <label>
                        Customer Name
                    </label>

                    <input
                        name="name"
                        required
                        placeholder="Customer name"
                    >
                </div>

                <div>
                    <label>
                        Mobile
                    </label>

                    <input
                        name="mobile"
                        placeholder="Mobile"
                    >
                </div>

                <div>
                    <label>
                        Address
                    </label>

                    <input
                        name="address"
                        placeholder="Address"
                    >
                </div>

                <div
                    style="grid-column:1/-1"
                >

                    <label>
                        Notes
                    </label>

                    <textarea
                        name="notes"
                    ></textarea>

                </div>

            </div>

            <br>

            <button
                class="green"
                type="submit"
            >
                💾 SAVE CUSTOMER
            </button>

        </form>

    </div>


    <div class="panel">

        <h3>
            📋 Customer List
        </h3>

        <div class="table">

            <table>

                <tr>

                    <th>
                        Name
                    </th>

                    <th>
                        Mobile
                    </th>

                    <th>
                        Jobs
                    </th>

                    <th>
                        Total Kaam
                    </th>

                    <th>
                        Paid
                    </th>

                    <th>
                        Baaki
                    </th>

                    <th>
                        Action
                    </th>

                </tr>

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
                        <b>
                            {esc(r["name"])}
                        </b>

                        <br>

                        <span class="muted">
                            {esc(r["address"])}
                        </span>
                    </td>

                    <td>
                        {esc(r["mobile"])}
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
                                📒 LEDGER
                            </a>

                            <a
                                class="btn small blue"
                                href="{url_for(
                                    'jobs',
                                    customer_id=r['id']
                                )}"
                            >
                                💍 JOB
                            </a>

                            <form
                                method="post"
                                style="display:inline"
                                onsubmit="
                                    return confirm(
                                        'Customer remove kare?'
                                    )
                                "
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
                                    DELETE
                                </button>

                            </form>

                        </div>

                    </td>

                </tr>

        """

    if not rows:

        body += """

                <tr>

                    <td
                        colspan="7"
                        class="muted"
                    >
                        Abhi koi customer nahi hai.
                    </td>

                </tr>

        """

    body += """

            </table>

        </div>

    </div>

    """

    return page(
        "Customers",
        body
    )


# ============================================================
# JOBS
# ============================================================

@app.route(
    "/jobs",
    methods=["GET", "POST"]
)
@login_required
def jobs():

    con = db()

    edit_id = request.args.get(
        "edit",
        type=int
    )

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

            quantity = parse_int(
                "quantity",
                1
            )

            taanch = request.form.get(
                "taanch",
                ""
            ).strip()

            work_amount = parse_float(
                "work_amount"
            )

            notes = request.form.get(
                "notes",
                ""
            ).strip()

            if customer_id <= 0:

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

            if quantity < 1:

                raise ValueError(
                    "नग कम से कम 1 hona chahiye."
                )

            # =================================================
            # AUTOMATIC WEIGHT CALCULATION
            #
            # वजन + नग वजन = कुल वजन
            # कुल वजन - लॉस = अंतिम वजन
            # =================================================

            total_weight = (
                gross_weight
                +
                nag_weight
            )

            final_weight = (
                total_weight
                -
                loss
            )

            if final_weight < 0:

                raise ValueError(
                    "अंतिम वजन negative nahi ho sakta."
                )

            if action == "update":

                job_id = int(
                    request.form.get(
                        "job_id",
                        "0"
                    )
                )

                con.execute(
                    """
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
                        quantity=?,
                        taanch=?,
                        work_amount=?,
                        notes=?

                    WHERE id=?
                    """,
                    (
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
                        quantity,
                        taanch,
                        work_amount,
                        notes,
                        job_id
                    )
                )

                message = (
                    "Job entry update ho gayi."
                )

            else:

                con.execute(
                    """
                    INSERT INTO jobs
                    (
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
                        quantity,
                        taanch,
                        work_amount,
                        notes
                    )

                    VALUES
                    (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    """,
                    (
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
                        quantity,
                        taanch,
                        work_amount,
                        notes
                    )
                )

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

    # ========================================================
    # CUSTOMER LIST
    # ========================================================

    customers_rows = con.execute(
        """
        SELECT id,name
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()

    # ========================================================
    # EDIT JOB
    # ========================================================

    edit_job = None

    if edit_id:

        edit_job = con.execute(
            """
            SELECT *
            FROM jobs
            WHERE id=?
            """,
            (edit_id,)
        ).fetchone()

    # ========================================================
    # JOB LIST
    # ========================================================

    jobs_rows = con.execute(
        """
        SELECT
            j.*,
            c.name AS customer_name

        FROM jobs j

        JOIN customers c
            ON c.id=j.customer_id

        ORDER BY
            j.date DESC,
            j.id DESC
        """
    ).fetchall()

    con.close()

    # ========================================================
    # FORM DEFAULTS
    # ========================================================

    if edit_job:

        selected_customer = str(
            edit_job["customer_id"]
        )

        form_date = edit_job["date"]

        form_jewellery = (
            edit_job["jewellery"]
            or ""
        )

        form_work = (
            edit_job["work"]
            or "Other"
        )

        form_status = (
            edit_job["status"]
            or "Pending"
        )

        form_maal_aaya = (
            edit_job["maal_aaya"]
            or ""
        )

        form_maal_diyaa = (
            edit_job["maal_diyaa"]
            or ""
        )

        form_gross = (
            edit_job["gross_weight"]
            or 0
        )

        form_nag = (
            edit_job["nag_weight"]
            or edit_job["stone_weight"]
            or 0
        )

        form_loss = (
            edit_job["loss"]
            or 0
        )

        form_taanch = (
            edit_job["taanch"]
            or ""
        )

        form_quantity = (
            edit_job["quantity"]
            or 1
        )

        form_amount = (
            edit_job["work_amount"]
            or 0
        )

        form_notes = (
            edit_job["notes"]
            or ""
        )

        heading = "✏️ EDIT JOB"

        button_text = "UPDATE JOB"

        action_value = "update"

        job_id_html = f"""
        <input
            type="hidden"
            name="job_id"
            value="{edit_id}"
        >
        """

    else:

        selected_customer = request.args.get(
            "customer_id",
            ""
        )

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

        heading = "➕ NEW JOB ENTRY"

        button_text = "SAVE JOB"

        action_value = "save"

        job_id_html = ""

    # ========================================================
    # CUSTOMER OPTIONS
    # ========================================================

    customer_options = ""

    for c in customers_rows:

        selected = (
            "selected"
            if str(c["id"])
            ==
            str(selected_customer)
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

    # ========================================================
    # JOB FORM
    # ========================================================

    body = f"""

    <h2>
        {heading}
    </h2>

    <div class="panel">

        <form method="post">

            <input
                type="hidden"
                name="action"
                value="{action_value}"
            >

            {job_id_html}

            <div class="form">

                <div>

                    <label>
                        Customer
                    </label>

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

                    <label>
                        Date
                    </label>

                    <input
                        type="date"
                        name="date"
                        value="{esc(form_date)}"
                        required
                    >

                </div>


                <div>

                    <label>
                        Jewellery
                    </label>

                    <input
                        name="jewellery"
                        value="{esc(form_jewellery)}"
                        placeholder="Ring / Chain / Pendant"
                        required
                    >

                </div>


                <div>

                    <label>
                        Work
                    </label>

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

                    <label>
                        Status
                    </label>

                    <select name="status">

                        <option
                            value="Pending"
                            {"selected" if form_status == "Pending" else ""}
                        >
                            Pending
                        </option>

                        <option
                            value="In Progress"
                            {"selected" if form_status == "In Progress" else ""}
                        >
                            In Progress
                        </option>

                        <option
                            value="Ready"
                            {"selected" if form_status == "Ready" else ""}
                        >
                            Ready
                        </option>

                        <option
                            value="Delivered"
                            {"selected" if form_status == "Delivered" else ""}
                        >
                            Delivered
                        </option>

                    </select>

                </div>


                <div>

                    <label>
                        नग
                    </label>

                    <input
                        type="number"
                        name="quantity"
                        min="1"
                        value="{form_quantity}"
                    >

                </div>


                <div>

                    <label>
                        माल आया
                    </label>

                    <input
                        name="maal_aaya"
                        value="{esc(form_maal_aaya)}"
                        placeholder="माल आया"
                    >

                </div>


                <div>

                    <label>
                        माल गया
                    </label>

                    <input
                        name="maal_diyaa"
                        value="{esc(form_maal_diyaa)}"
                        placeholder="माल गया"
                    >

                </div>


                <div>

                    <label>
                        काम की रकम
                    </label>

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


            <h3>
                ⚖️ वजन विवरण
            </h3>


            <div class="form">

                <div>

                    <label>
                        वजन
                    </label>

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

                    <label>
                        + नग वजन
                    </label>

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

                    <label>
                        = कुल वजन
                    </label>

                    <input
                        type="number"
                        step="0.001"
                        id="total_weight"
                        value="0"
                        readonly
                    >

                </div>


                <div>

                    <label>
                        - लॉस
                    </label>

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

                    <label>
                        = अंतिम वजन
                    </label>

                    <input
                        type="number"
                        step="0.001"
                        id="final_weight"
                        value="0"
                        readonly
                    >

                </div>


                <div>

                    <label>
                        ताँच
                    </label>

                    <input
                        name="taanch"
                        value="{esc(form_taanch)}"
                        placeholder="ताँच"
                    >

                </div>

            </div>


            <br>


            <label>
                Notes
            </label>

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


            {"<a class='btn gray' href='" + url_for("jobs") + "'>CANCEL</a>" if edit_job else ""}

        </form>

    </div>


    <div class="panel">

        <h3>
            📋 JOB RECORDS
        </h3>

        <div class="table">

            <table>

                <tr>

                    <th>
                        ID
                    </th>

                    <th>
                        Date
                    </th>

                    <th>
                        Customer
                    </th>

                    <th>
                        Jewellery
                    </th>

                    <th>
                        Work
                    </th>

                    <th>
                        वजन
                    </th>

                    <th>
                        नग वजन
                    </th>

                    <th>
                        कुल वजन
                    </th>

                    <th>
                        लॉस
                    </th>

                    <th>
                        अंतिम वजन
                    </th>

                    <th>
                        ताँच
                    </th>

                    <th>
                        Status
                    </th>

                    <th>
                        Amount
                    </th>

                    <th>
                        Action
                    </th>

                </tr>

    """

    # ========================================================
    # JOB ROWS
    # ========================================================

    for r in jobs_rows:

        body += f"""

                <tr>

                    <td>
                        {r["id"]}
                    </td>

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
                        {esc(r["work"])}
                    </td>

                    <td>
                        {float(r["gross_weight"] or 0):.3f} g
                    </td>

                    <td>
                        {float(r["nag_weight"] or 0):.3f} g
                    </td>

                    <td>
                        {float(r["total_weight"] or 0):.3f} g
                    </td>

                    <td>
                        {float(r["loss"] or 0):.3f} g
                    </td>

                    <td>
                        <b>
                            {float(r["final_weight"] or r["net_weight"] or 0):.3f}
                            g
                        </b>
                    </td>

                    <td>
                        {esc(r["taanch"])}
                    </td>

                    <td>

                        <span class="badge yellow">
                            {esc(r["status"])}
                        </span>

                    </td>

                    <td>
                        {money(r["work_amount"])}
                    </td>

                    <td>

                        <div class="actions">

                            <a
                                class="btn small blue"
                                href="{url_for(
                                    'jobs',
                                    edit=r['id']
                                )}"
                            >
                                ✏️ EDIT
                            </a>

                            <form
                                method="post"
                                action="{url_for(
                                    'delete_job',
                                    job_id=r['id']
                                )}"
                                style="display:inline"
                                onsubmit="
                                    return confirm(
                                        'Job delete kare?'
                                    )
                                "
                            >

                                <button
                                    class="red small"
                                    type="submit"
                                >
                                    🗑 DELETE
                                </button>

                            </form>

                        </div>

                    </td>

                </tr>

        """

    if not jobs_rows:

        body += """

                <tr>

                    <td
                        colspan="14"
                        class="muted"
                    >
                        Abhi koi job entry nahi hai.
                    </td>

                </tr>

        """

    body += """

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
            "final_weight"
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

@app.post(
    "/job/delete/<int:job_id>"
)
@login_required
def delete_job(job_id):

    con = db()

    con.execute(
        """
        DELETE FROM jobs
        WHERE id=?
        """,
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

@app.route(
    "/payments",
    methods=["GET", "POST"]
)
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

            if customer_id <= 0:

                raise ValueError(
                    "Customer select karo."
                )

            if not date_value:

                raise ValueError(
                    "Date zaroori hai."
                )

            if amount <= 0:

                raise ValueError(
                    "Payment amount 0 se zyada hona chahiye."
                )

            con.execute(
                """
                INSERT INTO payments
                (
                    customer_id,
                    date,
                    amount,
                    mode,
                    note
                )
                VALUES(?,?,?,?,?)
                """,
                (
                    customer_id,
                    date_value,
                    amount,
                    mode,
                    note
                )
            )

            con.commit()

            flash(
                "Payment save ho gaya.",
                "success"
            )

        except Exception as e:

            con.rollback()

            flash(
                str(e),
                "error"
            )

        finally:

            con.close()

        return redirect(
            url_for("payments")
        )

    customers_rows = con.execute(
        """
        SELECT id,name
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()

    payments_rows = con.execute(
        """
        SELECT
            p.*,
            c.name AS customer_name

        FROM payments p

        JOIN customers c
            ON c.id=p.customer_id

        ORDER BY
            p.date DESC,
            p.id DESC
        """
    ).fetchall()

    con.close()

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    customer_options = ""

    for c in customers_rows:

        customer_options += f"""
        <option value="{c['id']}">
            {esc(c['name'])}
        </option>
        """

    body = f"""

    <h2>
        💰 Payment Entry
    </h2>

    <div class="panel">

        <h3>
            ➕ New Payment
        </h3>

        <form method="post">

            <div class="form">

                <div>

                    <label>
                        Customer
                    </label>

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

                    <label>
                        Date
                    </label>

                    <input
                        type="date"
                        name="date"
                        value="{today}"
                        required
                    >

                </div>


                <div>

                    <label>
                        Amount
                    </label>

                    <input
                        type="number"
                        step="0.01"
                        min="0"
                        name="amount"
                        required
                    >

                </div>


                <div>

                    <label>
                        Mode
                    </label>

                    <select name="mode">

                        <option>
                            Cash
                        </option>

                        <option>
                            UPI
                        </option>

                        <option>
                            Bank
                        </option>

                        <option>
                            Other
                        </option>

                    </select>

                </div>


                <div>

                    <label>
                        Note
                    </label>

                    <input
                        name="note"
                        placeholder="Payment note"
                    >

                </div>

            </div>

            <br>

            <button
                class="green"
                type="submit"
            >
                💾 SAVE PAYMENT
            </button>

        </form>

    </div>


    <div class="panel">

        <h3>
            📋 Payment Records
        </h3>

        <div class="table">

            <table>

                <tr>

                    <th>
                        Date
                    </th>

                    <th>
                        Customer
                    </th>

                    <th>
                        Amount
                    </th>

                    <th>
                        Mode
                    </th>

                    <th>
                        Note
                    </th>

                </tr>

    """

    for p in payments_rows:

        body += f"""

                <tr>

                    <td>
                        {esc(p["date"])}
                    </td>

                    <td>
                        <b>
                            {esc(p["customer_name"])}
                        </b>
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

    if not payments_rows:

        body += """

                <tr>

                    <td
                        colspan="5"
                        class="muted"
                    >
                        Abhi koi payment nahi hai.
                    </td>

                </tr>

        """

    body += """

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

    customers_rows = con.execute(
        """
        SELECT id,name
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()

    selected_customer = None

    jobs_rows = []

    payment_rows = []

    if customer_id:

        selected_customer = con.execute(
            """
            SELECT *
            FROM customers
            WHERE id=?
            """,
            (customer_id,)
        ).fetchone()

        jobs_rows = con.execute(
            """
            SELECT *
            FROM jobs
            WHERE customer_id=?
            ORDER BY date,id
            """,
            (customer_id,)
        ).fetchall()

        payment_rows = con.execute(
            """
            SELECT *
            FROM payments
            WHERE customer_id=?
            ORDER BY date,id
            """,
            (customer_id,)
        ).fetchall()

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
        total_work
        -
        total_paid
    )

    options = ""

    for c in customers_rows:

        selected = (
            "selected"
            if customer_id == c["id"]
            else ""
        )

        options += f"""
        <option
            value="{c['id']}"
            {selected}
        >
            {esc(c['name'])}
        </option>
        """

    body = f"""

    <h2>
        📒 Customer Ledger
    </h2>

    <div class="panel">

        <form
            method="get"
            class="toolbar"
        >

            <div class="field">

                <label>
                    Customer
                </label>

                <select
                    name="customer_id"
                    required
                >

                    <option value="">
                        Select Customer
                    </option>

                    {options}

                </select>

            </div>

            <button
                class="blue"
                type="submit"
            >
                📒 SHOW LEDGER
            </button>

        </form>

    </div>

    """

    if selected_customer:

        body += f"""

        <div class="cardbox">

            <div class="card">

                <h3>
                    Customer
                </h3>

                <div class="stat">
                    {esc(selected_customer["name"])}
                </div>

            </div>


            <div class="card">

                <h3>
                    Total Kaam
                </h3>

                <div class="stat">
                    {money(total_work)}
                </div>

            </div>


            <div class="card">

                <h3>
                    Total Paid
                </h3>

                <div class="stat credit">
                    {money(total_paid)}
                </div>

            </div>


            <div class="card">

                <h3>
                    Baaki
                </h3>

                <div class="stat debit">
                    {money(balance)}
                </div>

            </div>

        </div>


        <div class="panel">

            <h3>
                💍 Job Entries
            </h3>

            <div class="table">

                <table>

                    <tr>

                        <th>
                            Date
                        </th>

                        <th>
                            Jewellery
                        </th>

                        <th>
                            Work
                        </th>

                        <th>
                            अंतिम वजन
                        </th>

                        <th>
                            Amount
                        </th>

                        <th>
                            Status
                        </th>

                    </tr>

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
                            {esc(j["work"])}
                        </td>

                        <td>
                            {float(
                                j["final_weight"]
                                or j["net_weight"]
                                or 0
                            ):.3f} g
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

                </table>

            </div>

        </div>


        <div class="panel">

            <h3>
                💰 Payments
            </h3>

            <div class="table">

                <table>

                    <tr>

                        <th>
                            Date
                        </th>

                        <th>
                            Amount
                        </th>

                        <th>
                            Mode
                        </th>

                        <th>
                            Note
                        </th>

                    </tr>

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

                </table>

            </div>

        </div>

        """

    return page(
        "Ledger",
        body
    )


# ============================================================
# SEARCH
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

        rows = con.execute(
            """
            SELECT *
            FROM customers

            WHERE
                name LIKE ?
                OR mobile LIKE ?

            ORDER BY name
            """,
            (
                f"%{q}%",
                f"%{q}%"
            )
        ).fetchall()

    else:

        rows = []

    con.close()

    body = f"""

    <h2>
        🔎 Customer Search
    </h2>

    <div class="panel">

        <form method="get">

            <input
                name="q"
                value="{esc(q)}"
                placeholder="Customer name / mobile"
            >

            <br><br>

            <button
                class="blue"
                type="submit"
            >
                🔍 SEARCH
            </button>

        </form>

    </div>


    <div class="panel">

        <div class="table">

            <table>

                <tr>

                    <th>
                        ID
                    </th>

                    <th>
                        Name
                    </th>

                    <th>
                        Mobile
                    </th>

                    <th>
                        Address
                    </th>

                    <th>
                        Action
                    </th>

                </tr>

    """

    for c in rows:

        body += f"""

                <tr>

                    <td>
                        {c["id"]}
                    </td>

                    <td>
                        {esc(c["name"])}
                    </td>

                    <td>
                        {esc(c["mobile"])}
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
                            📒 LEDGER
                        </a>

                    </td>

                </tr>

        """

    body += """

            </table>

        </div>

    </div>

    """

    return page(
        "Search",
        body
    )


# ============================================================
# REPORTS
# ============================================================

@app.route("/reports")
@login_required
def reports():

    con = db()

    total_customers = con.execute(
        """
        SELECT COUNT(*)
        FROM customers
        WHERE active=1
        """
    ).fetchone()[0]

    total_jobs = con.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        """
    ).fetchone()[0]

    total_work = con.execute(
        """
        SELECT COALESCE(
            SUM(work_amount),0
        )
        FROM jobs
        """
    ).fetchone()[0]

    total_paid = con.execute(
        """
        SELECT COALESCE(
            SUM(amount),0
        )
        FROM payments
        """
    ).fetchone()[0]

    work_by_type = con.execute(
        """
        SELECT
            work,
            COUNT(*) AS total_jobs,
            COALESCE(
                SUM(work_amount),
                0
            ) AS total_amount

        FROM jobs

        GROUP BY work

        ORDER BY total_amount DESC
        """
    ).fetchall()

    con.close()

    balance = (
        float(total_work or 0)
        -
        float(total_paid or 0)
    )

    body = f"""

    <h2>
        📊 Reports
    </h2>

    <div class="cardbox">

        <div class="card">
            <h3>
                Customers
            </h3>
            <b>
                {total_customers}
            </b>
        </div>

        <div class="card">
            <h3>
                Jobs
            </h3>
            <b>
                {total_jobs}
            </b>
        </div>

        <div class="card">
            <h3>
                Total Kaam
            </h3>
            <b>
                {money(total_work)}
            </b>
        </div>

        <div class="card">
            <h3>
                Total Paid
            </h3>
            <b class="credit">
                {money(total_paid)}
            </b>
        </div>

    </div>


    <div class="panel">

        <h3>
            📈 Work Summary
        </h3>

        <div class="table">

            <table>

                <tr>

                    <th>
                        Work
                    </th>

                    <th>
                        Jobs
                    </th>

                    <th>
                        Amount
                    </th>

                </tr>

    """

    for r in work_by_type:

        body += f"""

                <tr>

                    <td>
                        {esc(r["work"])}
                    </td>

                    <td>
                        {r["total_jobs"]}
                    </td>

                    <td>
                        {money(r["total_amount"])}
                    </td>

                </tr>

        """

    body += f"""

            </table>

        </div>

    </div>


    <div class="panel">

        <h3>
            💰 Overall Baaki
        </h3>

        <div class="stat debit">
            {money(balance)}
        </div>

    </div>

    """

    return page(
        "Reports",
        body
    )


# ============================================================
# PDF REPORT
# ============================================================

@app.route("/reports/pdf")
@login_required
def reports_pdf():

    con = db()

    rows = con.execute(
        """
        SELECT
            j.*,
            c.name AS customer_name

        FROM jobs j

        JOIN customers c
            ON c.id=j.customer_id

        ORDER BY
            j.date DESC,
            j.id DESC
        """
    ).fetchall()

    con.close()

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "R.K JEWELERS",
            styles["Title"]
        )
    )

    story.append(
        Paragraph(
            "Jewellery Job Work Report",
            styles["Heading2"]
        )
    )

    story.append(
        Spacer(1, 15)
    )

    data = [
        [
            "Date",
            "Customer",
            "Jewellery",
            "Work",
            "Weight",
            "Amount"
        ]
    ]

    for r in rows:

        data.append(
            [
                str(r["date"] or ""),
                str(r["customer_name"] or ""),
                str(r["jewellery"] or ""),
                str(r["work"] or ""),
                f'{float(r["final_weight"] or 0):.3f} g',
                money(r["work_amount"])
            ]
        )

    table = Table(
        data,
        repeatRows=1
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0,0),
                    (-1,0),
                    colors.HexColor("#4a2915")
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
                    0.5,
                    colors.grey
                ),

                (
                    "FONTNAME",
                    (0,0),
                    (-1,0),
                    "Helvetica-Bold"
                ),

                (
                    "FONTSIZE",
                    (0,0),
                    (-1,-1),
                    8
                ),

                (
                    "VALIGN",
                    (0,0),
                    (-1,-1),
                    "TOP"
                )
            ]
        )
    )

    story.append(table)

    document.build(story)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="rk_jewellers_jobs_report.pdf",
        mimetype="application/pdf"
    )


# ============================================================
# BACKUP
# ============================================================

@app.get("/backup")
@login_required
def backup():

    setup()

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
            "database"
        )

        if not uploaded:

            flash(
                "Backup file select karo.",
                "error"
            )

            return redirect(
                url_for("restore")
            )

        filename = (
            uploaded.filename
            or ""
        ).lower()

        if not filename.endswith(".db"):

            flash(
                "Sirf .db backup file allowed hai.",
                "error"
            )

            return redirect(
                url_for("restore")
            )

        # Existing DB backup
        if DB.exists():

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            old_backup = (
                BACKUP_DIR
                /
                f"before_restore_{timestamp}.db"
            )

            shutil.copy2(
                DB,
                old_backup
            )

        uploaded.save(DB)

        setup()

        flash(
            "Database restore ho gaya.",
            "success"
        )

        return redirect(
            url_for("home")
        )

    body = """

    <h2>
        ♻️ Restore Database
    </h2>

    <div class="panel">

        <p>
            Apni purani <b>.db</b> backup file select karein.
        </p>

        <form
            method="post"
            enctype="multipart/form-data"
            onsubmit="
                return confirm(
                    'Database restore karna hai?'
                )
            "
        >

            <input
                type="file"
                name="database"
                accept=".db"
                required
            >

            <br><br>

            <button
                class="red"
                type="submit"
            >
                ♻️ RESTORE DATABASE
            </button>

        </form>

    </div>

    """

    return page(
        "Restore",
        body
    )


# ============================================================
# ABOUT
# ============================================================

@app.get("/about")
@login_required
def about():

    body = """

    <h2>
        ℹ️ Shop Information
    </h2>

    <div class="panel">

        <h2>
            R.K JEWELERS
        </h2>

        <p>
            Jewellery Job Work & Customer Ledger
        </p>

        <hr>

        <h3>
            Work Types
        </h3>

        <div class="actions">

            <span class="badge yellow">
                Nag Setting
            </span>

            <span class="badge yellow">
                Kachi Jadai
            </span>

            <span class="badge yellow">
                Chilai
            </span>

        </div>

        <br>

        <h3>
            Weight Calculation
        </h3>

        <p>
            <b>
                वजन + नग वजन = कुल वजन
            </b>
        </p>

        <p>
            <b>
                कुल वजन - लॉस = अंतिम वजन
            </b>
        </p>

        <hr>

        <p>
            Developer:
            <b>
                KRISHNA
            </b>
        </p>

    </div>

    """

    return page(
        "About",
        body
    )


# ============================================================
# DASHBOARD ALIAS
# ============================================================

@app.get("/dashboard")
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

    print("=" * 55)

    print(
        "             R.K JEWELERS PRO"
    )

    print("=" * 55)

    print(
        "Developer : KRISHNA"
    )

    print(
        "Server    : http://127.0.0.1:5000"
    )

    print(
        "Username  : admin"
    )

    print(
        "Password  : 1234"
    )

    print("=" * 55)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
