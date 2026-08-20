from flask import Flask, request, redirect, render_template_string, flash, session, send_file, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
from pathlib import Path
import os
import shutil
import html

# PDF FEATURE
from io import BytesIO
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

APP_DIR = Path(__file__).resolve().parent
DB = APP_DIR / "rk_jewellers.db"
BACKUP_DIR = APP_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("RK_SECRET_KEY") or os.urandom(32)

# LOGIN DETAILS
# Website par ye details kahin display nahi hongi.
ADMIN_USER = os.environ.get("RK_ADMIN_USER", "dheeraj")
ADMIN_PASSWORD = os.environ.get("RK_ADMIN_PASSWORD", "4141")
ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)


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
        work TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        maal_aaya TEXT DEFAULT '',
        maal_diyaa TEXT DEFAULT '',
        gross_weight REAL DEFAULT 0,
        stone_weight REAL DEFAULT 0,
        net_weight REAL DEFAULT 0,
        quantity INTEGER DEFAULT 1,
        work_amount REAL DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        mode TEXT NOT NULL DEFAULT 'Cash',
        note TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
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

    # OLD DATABASE UPGRADE

    existing = {
        r[1]
        for r in con.execute(
            "PRAGMA table_info(customers)"
        ).fetchall()
    }

    customer_cols = {
        "notes": "TEXT DEFAULT ''",
        "active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT",
    }

    for col, definition in customer_cols.items():

        if col not in existing:

            con.execute(
                f"""
                ALTER TABLE customers
                ADD COLUMN {col} {definition}
                """
            )

    existing = {
        r[1]
        for r in con.execute(
            "PRAGMA table_info(jobs)"
        ).fetchall()
    }

    job_cols = {
        "status": "TEXT NOT NULL DEFAULT 'Pending'",
        "gross_weight": "REAL DEFAULT 0",
        "stone_weight": "REAL DEFAULT 0",
        "net_weight": "REAL DEFAULT 0",
        "quantity": "INTEGER DEFAULT 1",
        "created_at": "TEXT",
    }

    for col, definition in job_cols.items():

        if col not in existing:

            con.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN {col} {definition}
                """
            )

    existing = {
        r[1]
        for r in con.execute(
            "PRAGMA table_info(payments)"
        ).fetchall()
    }

    if "mode" not in existing:

        con.execute(
            """
            ALTER TABLE payments
            ADD COLUMN mode TEXT NOT NULL DEFAULT 'Cash'
            """
        )

    if "created_at" not in existing:

        con.execute(
            """
            ALTER TABLE payments
            ADD COLUMN created_at TEXT
            """
        )

    con.commit()
    con.close()


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

        return float(raw)

    except ValueError:

        raise ValueError(
            f"{name} me valid number dalo."
        )


def parse_int(name, default=1):

    raw = request.form.get(
        name,
        ""
    ).strip()

    if not raw:
        return default

    try:

        return int(raw)

    except ValueError:

        raise ValueError(
            f"{name} me valid number dalo."
        )


BASE_HTML = """
<!DOCTYPE html>
<html lang="en">

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
    font-family:Arial,sans-serif;
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
}

label{
    font-weight:bold;
    font-size:13px;
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
    min-width:780px;
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

{% with messages=get_flashed_messages(
    category_filter=['success']
) %}

{% for m in messages %}

<div class="msg">
    {{m}}
</div>

{% endfor %}

{% endwith %}


{% with messages=get_flashed_messages(
    category_filter=['error']
) %}

{% for m in messages %}

<div class="err">
    {{m}}
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


def login_required(view):

    from functools import wraps

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


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        user = request.form.get(
            "username",
            ""
        )

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

    <h2>
        🔐 R.K JEWELERS Login
    </h2>

    <p class="muted">
        Local shop management system
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
            LOGIN
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


@app.get("/")
@login_required
def home():

    con = db()

    customers_count = con.execute(
        """
        SELECT COUNT(*) c
        FROM customers
        WHERE active=1
        """
    ).fetchone()["c"]

    jobs_count = con.execute(
        """
        SELECT COUNT(*) c
        FROM jobs
        """
    ).fetchone()["c"]

    work = con.execute(
        """
        SELECT
            COALESCE(
                SUM(work_amount),
                0
            ) c
        FROM jobs
        """
    ).fetchone()["c"]

    paid = con.execute(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) c
        FROM payments
        """
    ).fetchone()["c"]

    pending = con.execute(
        """
        SELECT COUNT(*) c
        FROM jobs
        WHERE status!='Delivered'
        """
    ).fetchone()["c"]

    con.close()

    body = f"""

    <h2>
        🏠 Dashboard
    </h2>

    <p>
        R.K JEWELERS Management System
    </p>

    <div class="cardbox">

        <div class="card">

            <h3>
                ACTIVE CUSTOMERS
            </h3>

            <b>
                {customers_count}
            </b>

        </div>

        <div class="card">

            <h3>
                TOTAL JOBS
            </h3>

            <b>
                {jobs_count}
            </b>

        </div>

        <div class="card">

            <h3>
                TOTAL KAAM
            </h3>

            <b>
                {money(work)}
            </b>

        </div>

        <div class="card">

            <h3>
                TOTAL BAAKI
            </h3>

            <b>
                {money(work-paid)}
            </b>

        </div>

    </div>

    <div class="three">

        <div class="panel">

            <h3>
                ⏳ Pending Jobs
            </h3>

            <div class="balance">
                {pending}
            </div>

            <p class="muted">
                Delivered ko chhodkar.
            </p>

        </div>

        <div class="panel">

            <h3>
                💰 Total Payment
            </h3>

            <div class="balance">
                {money(paid)}
            </div>

        </div>

        <div class="panel">

            <h3>
                ⚡ Quick Actions
            </h3>

            <div class="actions">

                <a
                    class="btn green"
                    href="{url_for('customers')}#add"
                >
                    + Customer
                </a>

                <a
                    class="btn"
                    href="{url_for('jobs')}"
                >
                    + Job
                </a>

                <a
                    class="btn blue"
                    href="{url_for('payments')}"
                >
                    + Payment
                </a>

            </div>

        </div>

    </div>

    <div class="panel">

        <h2>
            💎 Jewellery Job Work
        </h2>

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

            <span class="badge yellow">
                Other Jewellery Work
            </span>

        </div>

    </div>

    """

    return page(
        "Dashboard",
        body
    )


@app.route("/customers", methods=["GET"])
@login_required
def customers():

    con = db()

    q = request.args.get(
        "q",
        ""
    ).strip()

    status = request.args.get(
        "status",
        "active"
    )

    where = "WHERE 1=1"

    params = []

    if q:

        where += """
        AND (
            name LIKE ?
            OR mobile LIKE ?
            OR address LIKE ?
        )
        """

        like = f"%{q}%"

        params += [
            like,
            like,
            like
        ]

    if status == "active":

        where += " AND active=1"

    elif status == "inactive":

        where += " AND active=0"

    rows = con.execute(
        f"""
        SELECT *
        FROM customers
        {where}
        ORDER BY name
        """,
        params
    ).fetchall()

    con.close()

    body = f"""

    <h2>
        👥 Customers
    </h2>

    <div class="panel" id="add">

        <h3>
            ➕ Add Customer
        </h3>

        <form
            class="form"
            method="post"
            action="{url_for('add_customer')}"
        >

            <div>

                <label>Name</label>

                <input
                    name="name"
                    required
                >

            </div>

            <div>

                <label>Mobile</label>

                <input
                    name="mobile"
                    inputmode="tel"
                >

            </div>

            <div>

                <label>Address</label>

                <input
                    name="address"
                >

            </div>

            <div>

                <label>Notes</label>

                <input
                    name="notes"
                >

            </div>

            <div>

                <button class="green">
                    SAVE CUSTOMER
                </button>

            </div>

        </form>

    </div>

    <div class="panel">

        <h3>
            🔎 Search / Filter
        </h3>

        <form
            class="toolbar"
            method="get"
        >

            <div class="field">

                <label>
                    Search
                </label>

                <input
                    name="q"
                    value="{esc(q)}"
                    placeholder="Name / mobile / address"
                >

            </div>

            <div class="field">

                <label>
                    Status
                </label>

                <select name="status">

                    <option
                        value="active"
                        {"selected" if status=="active" else ""}
                    >
                        Active
                    </option>

                    <option
                        value="inactive"
                        {"selected" if status=="inactive" else ""}
                    >
                        Inactive
                    </option>

                    <option
                        value="all"
                        {"selected" if status=="all" else ""}
                    >
                        All
                    </option>

                </select>

            </div>

            <button class="blue">
                SEARCH
            </button>

        </form>

    </div>

    <div class="panel">

        <h3>
            Customer List
            ({len(rows)})
        </h3>

        <div class="table">

        <table>

        <tr>

            <th>ID</th>
            <th>Name</th>
            <th>Mobile</th>
            <th>Address</th>
            <th>Status</th>
            <th>Actions</th>

        </tr>

    """

    for r in rows:

        if r["active"]:

            status_badge = (
                '<span class="badge green">'
                'ACTIVE'
                '</span>'
            )

            toggle_label = "DISABLE"

        else:

            status_badge = (
                '<span class="badge red">'
                'INACTIVE'
                '</span>'
            )

            toggle_label = "ACTIVATE"

        body += f"""

        <tr>

            <td>
                {r["id"]}
            </td>

            <td>

                <b>
                    {esc(r["name"])}
                </b>

                <br>

                <span class="muted">
                    {esc(r["notes"])}
                </span>

            </td>

            <td>
                {esc(r["mobile"]) or "-"}
            </td>

            <td>
                {esc(r["address"]) or "-"}
            </td>

            <td>
                {status_badge}
            </td>

            <td>

                <div class="actions">

                    <a
                        class="btn small"
                        href="{url_for(
                            'edit_customer',
                            cid=r['id']
                        )}"
                    >
                        EDIT
                    </a>

                    <a
                        class="btn small blue"
                        href="{url_for('ledger')}?customer_id={r['id']}"
                    >
                        LEDGER
                    </a>

                    <form
                        method="post"
                        action="{url_for(
                            'toggle_customer',
                            cid=r['id']
                        )}"
                        style="display:inline"
                    >

                        <button
                            class="small {'red' if r['active'] else 'green'}"
                            type="submit"
                        >
                            {toggle_label}
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

    """

    return page(
        "Customers",
        body
    )


@app.post("/customers/add")
@login_required
def add_customer():

    name = request.form.get(
        "name",
        ""
    ).strip()

    if not name:

        flash(
            "Customer name zaroori hai.",
            "error"
        )

        return redirect(
            url_for("customers")
        )

    con = db()

    con.execute(
        """
        INSERT INTO customers(
            name,
            mobile,
            address,
            notes,
            active
        )
        VALUES(
            ?,
            ?,
            ?,
            ?,
            1
        )
        """,
        (
            name,

            request.form.get(
                "mobile",
                ""
            ).strip(),

            request.form.get(
                "address",
                ""
            ).strip(),

            request.form.get(
                "notes",
                ""
            ).strip()
        )
    )

    con.commit()
    con.close()

    flash(
        "Customer save ho gaya.",
        "success"
    )

    return redirect(
        url_for("customers")
    )


@app.route(
    "/customers/edit/<int:cid>",
    methods=["GET", "POST"]
)
@login_required
def edit_customer(cid):

    con = db()

    c = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (cid,)
    ).fetchone()

    if not c:

        con.close()

        flash(
            "Customer nahi mila.",
            "error"
        )

        return redirect(
            url_for("customers")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        if not name:

            flash(
                "Customer name zaroori hai.",
                "error"
            )

        else:

            con.execute(
                """
                UPDATE customers
                SET
                    name=?,
                    mobile=?,
                    address=?,
                    notes=?
                WHERE id=?
                """,
                (
                    name,

                    request.form.get(
                        "mobile",
                        ""
                    ).strip(),

                    request.form.get(
                        "address",
                        ""
                    ).strip(),

                    request.form.get(
                        "notes",
                        ""
                    ).strip(),

                    cid
                )
            )

            con.commit()
            con.close()

            flash(
                "Customer update ho gaya.",
                "success"
            )

            return redirect(
                url_for("customers")
            )

    con.close()

    body = f"""

    <h2>
        ✏️ Edit Customer
    </h2>

    <div class="panel">

        <form
            class="form"
            method="post"
        >

            <div>

                <label>
                    Name
                </label>

                <input
                    name="name"
                    required
                    value="{esc(c['name'])}"
                >

            </div>

            <div>

                <label>
                    Mobile
                </label>

                <input
                    name="mobile"
                    value="{esc(c['mobile'])}"
                >

            </div>

            <div>

                <label>
                    Address
                </label>

                <input
                    name="address"
                    value="{esc(c['address'])}"
                >

            </div>

            <div>

                <label>
                    Notes
                </label>

                <input
                    name="notes"
                    value="{esc(c['notes'])}"
                >

            </div>

            <div>

                <button class="green">
                    UPDATE CUSTOMER
                </button>

                <a
                    class="btn gray"
                    href="{url_for('customers')}"
                >
                    CANCEL
                </a>

            </div>

        </form>

    </div>

    """

    return page(
        "Edit Customer",
        body
    )


@app.post("/customers/toggle/<int:cid>")
@login_required
def toggle_customer(cid):

    con = db()

    c = con.execute(
        """
        SELECT active
        FROM customers
        WHERE id=?
        """,
        (cid,)
    ).fetchone()

    if c:

        new_status = (
            0
            if c["active"]
            else 1
        )

        con.execute(
            """
            UPDATE customers
            SET active=?
            WHERE id=?
            """,
            (
                new_status,
                cid
            )
        )

        con.commit()

        flash(
            "Customer status update ho gaya.",
            "success"
        )

    con.close()

    return redirect(
        url_for("customers")
    )
    @app.route(
    "/jobs",
    methods=["GET", "POST"]
)
@login_required
def jobs():

    con = db()

    customers = con.execute(
        """
        SELECT *
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()

    edit_id = request.args.get(
        "edit",
        type=int
    )

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

    if request.method == "POST":

        try:

            customer_id = request.form.get(
                "customer_id",
                ""
            ).strip()

            date_value = (
                request.form.get(
                    "date",
                    ""
                ).strip()
                or datetime.now().strftime(
                    "%d-%m-%Y"
                )
            )

            jewellery = request.form.get(
                "jewellery",
                ""
            ).strip()

            work_type = request.form.get(
                "work",
                "Other"
            )

            status = request.form.get(
                "status",
                "Pending"
            )

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

            stone_weight = parse_float(
                "stone_weight"
            )

            net_weight = parse_float(
                "net_weight"
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

            if not jewellery:

                raise ValueError(
                    "Jewellery name zaroori hai."
                )

            if gross_weight < 0:

                raise ValueError(
                    "Gross weight negative nahi ho sakta."
                )

            if stone_weight < 0:

                raise ValueError(
                    "Stone weight negative nahi ho sakta."
                )

            if net_weight < 0:

                raise ValueError(
                    "Net weight negative nahi ho sakta."
                )

            if quantity < 1:

                raise ValueError(
                    "Quantity kam se kam 1 honi chahiye."
                )

            if work_amount < 0:

                raise ValueError(
                    "Amount negative nahi ho sakta."
                )

            data = (
                customer_id,
                date_value,
                jewellery,
                work_type,
                status,
                maal_aaya,
                maal_diyaa,
                gross_weight,
                stone_weight,
                net_weight,
                quantity,
                work_amount,
                notes
            )

            if edit_id:

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
                        stone_weight=?,
                        net_weight=?,
                        quantity=?,
                        work_amount=?,
                        notes=?
                    WHERE id=?
                    """,
                    data + (edit_id,)
                )

                message = (
                    "Job entry update ho gayi."
                )

            else:

                con.execute(
                    """
                    INSERT INTO jobs(
                        customer_id,
                        date,
                        jewellery,
                        work,
                        status,
                        maal_aaya,
                        maal_diyaa,
                        gross_weight,
                        stone_weight,
                        net_weight,
                        quantity,
                        work_amount,
                        notes
                    )
                    VALUES(
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
                    data
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

        except ValueError as e:

            flash(
                str(e),
                "error"
            )

    rows = con.execute(
        """
        SELECT
            jobs.*,
            customers.name AS customer
        FROM jobs
        JOIN customers
            ON jobs.customer_id =
               customers.id
        ORDER BY jobs.id DESC
        """
    ).fetchall()

    con.close()

    if edit_job:

        selected_customer = str(
            edit_job["customer_id"]
        )

        form_date = edit_job["date"]
        form_jewellery = edit_job["jewellery"]
        form_maal_aaya = edit_job["maal_aaya"]
        form_maal_diyaa = edit_job["maal_diyaa"]
        form_gross = edit_job["gross_weight"]
        form_stone = edit_job["stone_weight"]
        form_net = edit_job["net_weight"]
        form_quantity = edit_job["quantity"]
        form_amount = edit_job["work_amount"]
        form_notes = edit_job["notes"]

        heading = "✏️ Edit Job Entry"
        button_text = "UPDATE JOB"

    else:

        selected_customer = ""

        form_date = datetime.now().strftime(
            "%d-%m-%Y"
        )

        form_jewellery = ""
        form_maal_aaya = ""
        form_maal_diyaa = ""
        form_gross = 0
        form_stone = 0
        form_net = 0
        form_quantity = 1
        form_amount = 0
        form_notes = ""

        heading = "💍 New Job Entry"
        button_text = "SAVE JOB ENTRY"

    body = f"""

    <h2>
        {heading}
    </h2>

    <div class="panel">

        <form
            class="form"
            method="post"
        >

            <div>

                <label>
                    Date
                </label>

                <input
                    name="date"
                    value="{esc(form_date)}"
                    required
                >

            </div>

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

    """

    for c in customers:

        selected = (
            "selected"
            if (
                str(c["id"])
                == selected_customer
            )
            else ""
        )

        body += f"""

                    <option
                        value="{c['id']}"
                        {selected}
                    >
                        {esc(c['name'])}
                    </option>

        """

    body += f"""

                </select>

            </div>

            <div>

                <label>
                    Jewellery Name
                </label>

                <input
                    name="jewellery"
                    required
                    value="{esc(form_jewellery)}"
                >

            </div>

            <div>

                <label>
                    Kaam
                </label>

                <select name="work">
    """

    work_options = [
        "Nag Setting",
        "Kachi Jadai",
        "Chilai",
        "Other"
    ]

    current_work = (
        edit_job["work"]
        if edit_job
        else "Nag Setting"
    )

    for w in work_options:

        selected = (
            "selected"
            if w == current_work
            else ""
        )

        body += f"""

                    <option {selected}>
                        {w}
                    </option>

        """

    body += """

                </select>

            </div>

            <div>

                <label>
                    Status
                </label>

                <select name="status">
    """

    status_options = [
        "Pending",
        "Kaam Chal Raha",
        "Ready",
        "Delivered"
    ]

    current_status = (
        edit_job["status"]
        if edit_job
        else "Pending"
    )

    for s in status_options:

        selected = (
            "selected"
            if s == current_status
            else ""
        )

        body += f"""

                    <option {selected}>
                        {s}
                    </option>

        """

    body += f"""

                </select>

            </div>

            <div>

                <label>
                    Quantity
                </label>

                <input
                    name="quantity"
                    type="number"
                    min="1"
                    value="{form_quantity}"
                >

            </div>

            <div>

                <label>
                    Maal Aaya
                </label>

                <input
                    name="maal_aaya"
                    value="{esc(form_maal_aaya)}"
                >

            </div>

            <div>

                <label>
                    Maal Diya
                </label>

                <input
                    name="maal_diyaa"
                    value="{esc(form_maal_diyaa)}"
                >

            </div>

            <div>

                <label>
                    Gross Weight (g)
                </label>

                <input
                    name="gross_weight"
                    type="number"
                    step="0.001"
                    min="0"
                    value="{form_gross}"
                >

            </div>

            <div>

                <label>
                    Stone Weight (g)
                </label>

                <input
                    name="stone_weight"
                    type="number"
                    step="0.001"
                    min="0"
                    value="{form_stone}"
                >

            </div>

            <div>

                <label>
                    Net Weight (g)
                </label>

                <input
                    name="net_weight"
                    type="number"
                    step="0.001"
                    min="0"
                    value="{form_net}"
                >

            </div>

            <div>

                <label>
                    Kaam Ke Paise
                </label>

                <input
                    name="work_amount"
                    type="number"
                    step="0.01"
                    min="0"
                    value="{form_amount}"
                >

            </div>

            <div>

                <label>
                    Notes
                </label>

                <input
                    name="notes"
                    value="{esc(form_notes)}"
                >

            </div>

            <div>

                <button
                    class="green"
                    type="submit"
                >
                    {button_text}
                </button>

    """

    if edit_job:

        body += f"""

                <a
                    class="btn gray"
                    href="{url_for('jobs')}"
                >
                    CANCEL
                </a>

        """

    body += """

            </div>

        </form>

    </div>

    <div class="panel">

        <h3>
            Recent Jobs
        </h3>

        <div class="table">

        <table>

            <tr>

                <th>Date</th>
                <th>Customer</th>
                <th>Jewellery</th>
                <th>Work</th>
                <th>Status</th>
                <th>Weight</th>
                <th>Amount</th>
                <th>Action</th>

            </tr>

    """

    for r in rows:

        if r["status"] == "Delivered":

            status_class = "green"

        elif r["status"] == "Ready":

            status_class = "yellow"

        elif r["status"] == "Pending":

            status_class = "red"

        else:

            status_class = ""

        body += f"""

            <tr>

                <td>
                    {esc(r["date"])}
                </td>

                <td>
                    {esc(r["customer"])}
                </td>

                <td>
                    {esc(r["jewellery"])}
                </td>

                <td>
                    {esc(r["work"])}
                </td>

                <td>

                    <span
                        class="badge {status_class}"
                    >
                        {esc(r["status"])}
                    </span>

                </td>

                <td>

                    G:
                    {r["gross_weight"] or 0}g

                    <br>

                    S:
                    {r["stone_weight"] or 0}g

                    <br>

                    N:
                    {r["net_weight"] or 0}g

                </td>

                <td>
                    {money(r["work_amount"])}
                </td>

                <td>

                    <a
                        class="btn small"
                        href="{url_for('jobs')}?edit={r['id']}"
                    >
                        EDIT
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
        "Jobs",
        body
    )


@app.route(
    "/payments",
    methods=["GET", "POST"]
)
@login_required
def payments():

    con = db()

    customers = con.execute(
        """
        SELECT *
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()

    edit_id = request.args.get(
        "edit",
        type=int
    )

    edit_payment = None

    if edit_id:

        edit_payment = con.execute(
            """
            SELECT *
            FROM payments
            WHERE id=?
            """,
            (edit_id,)
        ).fetchone()

    if request.method == "POST":

        try:

            customer_id = request.form.get(
                "customer_id",
                ""
            ).strip()

            date_value = (
                request.form.get(
                    "date",
                    ""
                ).strip()
                or datetime.now().strftime(
                    "%d-%m-%Y"
                )
            )

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

            if amount <= 0:

                raise ValueError(
                    "Payment amount valid dalo."
                )

            data = (
                customer_id,
                date_value,
                amount,
                mode,
                note
            )

            if edit_id:

                con.execute(
                    """
                    UPDATE payments
                    SET
                        customer_id=?,
                        date=?,
                        amount=?,
                        mode=?,
                        note=?
                    WHERE id=?
                    """,
                    data + (edit_id,)
                )

                message = (
                    "Payment update ho gayi."
                )

            else:

                con.execute(
                    """
                    INSERT INTO payments(
                        customer_id,
                        date,
                        amount,
                        mode,
                        note
                    )
                    VALUES(
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    """,
                    data
                )

                message = (
                    "Payment save ho gayi."
                )

            con.commit()
            con.close()

            flash(
                message,
                "success"
            )

            return redirect(
                url_for("payments")
            )

        except ValueError as e:

            flash(
                str(e),
                "error"
            )

    rows = con.execute(
        """
        SELECT
            payments.*,
            customers.name AS customer
        FROM payments
        JOIN customers
            ON payments.customer_id =
               customers.id
        ORDER BY payments.id DESC
        """
    ).fetchall()

    con.close()

    if edit_payment:

        selected_customer = str(
            edit_payment["customer_id"]
        )

        form_date = edit_payment["date"]
        form_amount = edit_payment["amount"]
        form_mode = edit_payment["mode"]
        form_note = edit_payment["note"]

        heading = "✏️ Edit Payment"
        button_text = "UPDATE PAYMENT"

    else:

        selected_customer = ""

        form_date = datetime.now().strftime(
            "%d-%m-%Y"
        )

        form_amount = 0
        form_mode = "Cash"
        form_note = ""

        heading = "💰 Payment Entry"
        button_text = "SAVE PAYMENT"

    body = f"""

    <h2>
        {heading}
    </h2>

    <div class="panel">

        <form
            class="form"
            method="post"
        >

            <div>

                <label>
                    Date
                </label>

                <input
                    name="date"
                    value="{esc(form_date)}"
                    required
                >

            </div>

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

    """

    for c in customers:

        selected = (
            "selected"
            if (
                str(c["id"])
                == selected_customer
            )
            else ""
        )

        body += f"""

                    <option
                        value="{c['id']}"
                        {selected}
                    >
                        {esc(c['name'])}
                    </option>

        """

    body += f"""

                </select>

            </div>

            <div>

                <label>
                    Payment Amount
                </label>

                <input
                    name="amount"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value="{form_amount}"
                >

            </div>

            <div>

                <label>
                    Payment Mode
                </label>

                <select name="mode">
    """

    modes = [
        "Cash",
        "UPI",
        "Bank",
        "Other"
    ]

    for m in modes:

        selected = (
            "selected"
            if m == form_mode
            else ""
        )

        body += f"""

                    <option {selected}>
                        {m}
                    </option>

        """

    body += f"""

                </select>

            </div>

            <div>

                <label>
                    Note
                </label>

                <input
                    name="note"
                    value="{esc(form_note)}"
                >

            </div>

            <div>

                <button
                    class="green"
                    type="submit"
                >
                    {button_text}
                </button>

    """

    if edit_payment:

        body += f"""

                <a
                    class="btn gray"
                    href="{url_for('payments')}"
                >
                    CANCEL
                </a>

        """

    body += """

            </div>

        </form>

    </div>

    <div class="panel">

        <h3>
            Payment History
        </h3>

        <div class="table">

        <table>

            <tr>

                <th>Date</th>
                <th>Customer</th>
                <th>Amount</th>
                <th>Mode</th>
                <th>Note</th>
                <th>Action</th>

            </tr>

    """

    for r in rows:

        body += f"""

            <tr>

                <td>
                    {esc(r["date"])}
                </td>

                <td>
                    {esc(r["customer"])}
                </td>

                <td class="credit">
                    {money(r["amount"])}
                </td>

                <td>
                    {esc(r["mode"])}
                </td>

                <td>
                    {esc(r["note"]) or "-"}
                </td>

                <td>

                    <a
                        class="btn small"
                        href="{url_for('payments')}?edit={r['id']}"
                    >
                        EDIT
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
        "Payments",
        body
    )


@app.route("/ledger")
@login_required
def ledger():

    con = db()

    customers = con.execute(
        """
        SELECT *
        FROM customers
        ORDER BY name
        """
    ).fetchall()

    cid = request.args.get(
        "customer_id",
        ""
    ).strip()

    body = """

    <h2>
        📒 Customer Ledger
    </h2>

    <div class="panel">

        <form
            class="toolbar"
            method="get"
        >

            <div class="field">

                <label>
                    Select Customer
                </label>

                <select
                    name="customer_id"
                    onchange="this.form.submit()"
                >

                    <option value="">
                        Select Customer
                    </option>

    """

    for c in customers:

        selected = (
            "selected"
            if str(c["id"]) == cid
            else ""
        )

        body += f"""

                    <option
                        value="{c['id']}"
                        {selected}
                    >
                        {esc(c['name'])}
                    </option>

        """

    body += """

                </select>

            </div>

        </form>

    </div>

    """

    if cid:

        customer = con.execute(
            """
            SELECT *
            FROM customers
            WHERE id=?
            """,
            (cid,)
        ).fetchone()

        if customer:

            jobs_list = con.execute(
                """
                SELECT *
                FROM jobs
                WHERE customer_id=?
                ORDER BY id
                """,
                (cid,)
            ).fetchall()

            payments_list = con.execute(
                """
                SELECT *
                FROM payments
                WHERE customer_id=?
                ORDER BY id
                """,
                (cid,)
            ).fetchall()

            events = []

            for j in jobs_list:

                events.append(
                    {
                        "date": j["date"],
                        "sort": j["id"],
                        "type": "KAAM",
                        "particular":
                            (
                                f"{j['jewellery']} - "
                                f"{j['work']} "
                                f"({j['status']})"
                            ),
                        "debit":
                            float(
                                j["work_amount"]
                                or 0
                            ),
                        "credit": 0.0
                    }
                )

            for p in payments_list:

                events.append(
                    {
                        "date": p["date"],
                        "sort":
                            1000000 + p["id"],
                        "type": "PAYMENT",
                        "particular":
                            (
                                f"{p['mode']} - "
                                f"{p['note'] or 'Payment'}"
                            ),
                        "debit": 0.0,
                        "credit":
                            float(
                                p["amount"]
                                or 0
                            )
                    }
                )

            events.sort(
                key=lambda item: (
                    item["date"],
                    item["sort"]
                )
            )

            total_debit = sum(
                item["debit"]
                for item in events
            )

            total_credit = sum(
                item["credit"]
                for item in events
            )

            final_balance = (
                total_debit
                - total_credit
            )

            share_text = (
                "R.K JEWELERS\n"
                f"Customer: {customer['name']}\n"
                f"Total Kaam: {money(total_debit)}\n"
                f"Total Payment: {money(total_credit)}\n"
                f"Baaki: {money(final_balance)}"
            )

            body += f"""

            <div class="cardbox">

                <div class="card">

                    <h3>
                        CUSTOMER
                    </h3>

                    <b>
                        {esc(customer["name"])}
                    </b>

                </div>

                <div class="card">

                    <h3>
                        TOTAL KAAM
                    </h3>

                    <b>
                        {money(total_debit)}
                    </b>

                </div>

                <div class="card">

                    <h3>
                        TOTAL PAYMENT
                    </h3>

                    <b>
                        {money(total_credit)}
                    </b>

                </div>

                <div class="card">

                    <h3>
                        TOTAL BAAKI
                    </h3>

                    <b>
                        {money(final_balance)}
                    </b>

                </div>

            </div>

            <div class="panel">

                <div class="actions no-print">

                    <button
                        onclick="window.print()"
                    >
                        🖨️ PRINT LEDGER
                    </button>

                    <a
                        class="btn blue"
                        href="{url_for(
                            'ledger_pdf',
                            customer_id=cid
                        )}"
                    >
                        📄 DOWNLOAD PDF
                    </a>

                    <a
                        class="btn green"
                        href="{url_for(
                            'ledger_whatsapp',
                            customer_id=cid
                        )}"
                    >
                        💬 WHATSAPP
                    </a>

                </div>

                <h3>
                    Complete Hisaab
                </h3>

                <div class="table">

                <table>

                    <tr>

                        <th>
                            Date
                        </th>

                        <th>
                            Particular
                        </th>

                        <th>
                            Debit
                        </th>

                        <th>
                            Credit
                        </th>

                        <th>
                            Running Balance
                        </th>

                    </tr>

            """

            running = 0

            for item in events:

                running += (
                    item["debit"]
                    - item["credit"]
                )

                debit_text = (
                    money(item["debit"])
                    if item["debit"] > 0
                    else "-"
                )

                credit_text = (
                    money(item["credit"])
                    if item["credit"] > 0
                    else "-"
                )

                body += f"""

                    <tr>

                        <td>
                            {esc(item["date"])}
                        </td>

                        <td>

                            <b>
                                {esc(item["type"])}
                            </b>

                            <br>

                            {esc(item["particular"])}

                        </td>

                        <td class="debit">
                            {debit_text}
                        </td>

                        <td class="credit">
                            {credit_text}
                        </td>

                        <td>

                            <b>
                                {money(running)}
                            </b>

                        </td>

                    </tr>

                """

            body += """

                </table>

                </div>

            </div>

            <div class="panel no-print">

                <h3>
                    Share Text
                </h3>

                <textarea
                    readonly
                >""" + esc(share_text) + """</textarea>

            </div>

            """

    con.close()

    return page(
        "Ledger",
        body
    )


@app.get("/ledger/whatsapp")
@login_required
def ledger_whatsapp():

    from urllib.parse import quote

    cid = request.args.get(
        "customer_id",
        type=int
    )

    if not cid:

        return redirect(
            url_for("ledger")
        )

    con = db()

    customer = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (cid,)
    ).fetchone()

    if not customer:

        con.close()

        return redirect(
            url_for("ledger")
        )

    total_work = con.execute(
        """
        SELECT
            COALESCE(
                SUM(work_amount),
                0
            ) total
        FROM jobs
        WHERE customer_id=?
        """,
        (cid,)
    ).fetchone()["total"]

    total_payment = con.execute(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) total
        FROM payments
        WHERE customer_id=?
        """,
        (cid,)
    ).fetchone()["total"]

    con.close()

    balance = (
        total_work
        - total_payment
    )

    message = (
        "R.K JEWELERS\n"
        f"Customer: {customer['name']}\n"
        f"Total Kaam: {money(total_work)}\n"
        f"Total Payment: {money(total_payment)}\n"
        f"Baaki: {money(balance)}"
    )

    return redirect(
        "https://wa.me/?text="
        + quote(message)
    )


@app.get("/ledger/pdf")
@login_required
def ledger_pdf():

    try:

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle
        )
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.units import mm

    except ImportError:

        flash(
            "PDF ke liye reportlab install karo: pip install reportlab",
            "error"
        )

        return redirect(
            url_for("ledger")
        )

    cid = request.args.get(
        "customer_id",
        type=int
    )

    if not cid:

        return redirect(
            url_for("ledger")
        )

    con = db()

    customer = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (cid,)
    ).fetchone()

    if not customer:

        con.close()

        flash(
            "Customer nahi mila.",
            "error"
        )

        return redirect(
            url_for("ledger")
        )

    jobs_list = con.execute(
        """
        SELECT *
        FROM jobs
        WHERE customer_id=?
        ORDER BY id
        """,
        (cid,)
    ).fetchall()

    payments_list = con.execute(
        """
        SELECT *
        FROM payments
        WHERE customer_id=?
        ORDER BY id
        """,
        (cid,)
    ).fetchall()

    con.close()

    events = []

    for j in jobs_list:

        events.append(
            {
                "date": j["date"],
                "sort": j["id"],
                "type": "KAAM",
                "particular":
                    (
                        f"{j['jewellery']} - "
                        f"{j['work']} "
                        f"({j['status']})"
                    ),
                "debit":
                    float(
                        j["work_amount"] or 0
                    ),
                "credit": 0.0
            }
        )

    for p in payments_list:

        events.append(
            {
                "date": p["date"],
                "sort": 1000000 + p["id"],
                "type": "PAYMENT",
                "particular":
                    (
                        f"{p['mode']} - "
                        f"{p['note'] or 'Payment'}"
                    ),
                "debit": 0.0,
                "credit":
                    float(
                        p["amount"] or 0
                    )
            }
        )

    events.sort(
        key=lambda x: (
            x["date"],
            x["sort"]
        )
    )

    total_debit = sum(
        x["debit"]
        for x in events
    )

    total_credit = sum(
        x["credit"]
        for x in events
    )

    balance = (
        total_debit
        - total_credit
    )

    filename = (
        "ledger_"
        + str(customer["name"])
        .replace(" ", "_")
        + ".pdf"
    )

    pdf_path = (
        BACKUP_DIR
        / filename
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.alignment = TA_CENTER

    normal = styles["Normal"]

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    story = []

    story.append(
        Paragraph(
            "R.K JEWELERS",
            title_style
        )
    )

    story.append(
        Paragraph(
            "Jewellery Job Work & Customer Ledger",
            normal
        )
    )

    story.append(
        Spacer(
            1,
            8
        )
    )

    story.append(
        Paragraph(
            f"<b>Customer:</b> "
            f"{html.escape(str(customer['name']))}",
            normal
        )
    )

    story.append(
        Paragraph(
            f"<b>Mobile:</b> "
            f"{html.escape(str(customer['mobile'] or '-'))}",
            normal
        )
    )

    story.append(
        Spacer(
            1,
            10
        )
    )

    table_data = [
        [
            "Date",
            "Particular",
            "Debit",
            "Credit",
            "Balance"
        ]
    ]

    running = 0

    for item in events:

        running += (
            item["debit"]
            - item["credit"]
        )

        table_data.append(
            [
                str(item["date"]),
                (
                    str(item["type"])
                    + "\n"
                    + str(item["particular"])
                ),
                (
                    f"₹ {item['debit']:,.2f}"
                    if item["debit"] > 0
                    else "-"
                ),
                (
                    f"₹ {item['credit']:,.2f}"
                    if item["credit"] > 0
                    else "-"
                ),
                f"₹ {running:,.2f}"
            ]
        )

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            25 * mm,
            75 * mm,
            25 * mm,
            25 * mm,
            30 * mm
        ]
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#4a2915")
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )
            ]
        )
    )

    story.append(table)

    story.append(
        Spacer(
            1,
            12
        )
    )

    summary_data = [
        [
            "Total Kaam",
            f"₹ {total_debit:,.2f}"
        ],
        [
            "Total Payment",
            f"₹ {total_credit:,.2f}"
        ],
        [
            "Total Baaki",
            f"₹ {balance:,.2f}"
        ]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            70 * mm,
            50 * mm
        ]
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica-Bold"
                ),
                (
                    "ALIGN",
                    (1, 0),
                    (1, -1),
                    "RIGHT"
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.whitesmoke
                )
            ]
        )
    )

    story.append(
        summary_table
    )

    story.append(
        Spacer(
            1,
            20
        )
    )

    story.append(
        Paragraph(
            "Developer: KRISHNA",
            normal
        )
    )

    doc.build(story)

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )
    # ================================
# PART 3 — REPORTS + PDF + BACKUP
# ================================

@app.route("/reports")
@login_required
def reports():

    con = db()

    customers_count = con.execute(
        """
        SELECT COUNT(*) c
        FROM customers
        WHERE active=1
        """
    ).fetchone()["c"]

    jobs_count = con.execute(
        """
        SELECT COUNT(*) c
        FROM jobs
        """
    ).fetchone()["c"]

    total_work = con.execute(
        """
        SELECT COALESCE(
            SUM(work_amount), 0
        ) c
        FROM jobs
        """
    ).fetchone()["c"]

    total_payment = con.execute(
        """
        SELECT COALESCE(
            SUM(amount), 0
        ) c
        FROM payments
        """
    ).fetchone()["c"]

    pending = con.execute(
        """
        SELECT COUNT(*) c
        FROM jobs
        WHERE status != 'Delivered'
        """
    ).fetchone()["c"]

    delivered = jobs_count - pending

    final_balance = (
        total_work - total_payment
    )

    top_customers = con.execute(
        """
        SELECT
            customers.name,
            COALESCE(
                SUM(jobs.work_amount),
                0
            ) total
        FROM jobs
        JOIN customers
            ON jobs.customer_id =
               customers.id
        GROUP BY customers.id
        ORDER BY total DESC
        LIMIT 10
        """
    ).fetchall()

    con.close()

    body = f"""

    <h2>
        📊 Reports
    </h2>

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
            <b>{money(total_work)}</b>
        </div>

        <div class="card">
            <h3>TOTAL BAAKI</h3>
            <b>{money(final_balance)}</b>
        </div>

    </div>


    <div class="two">

        <div class="panel">

            <h3>
                📦 Job Status
            </h3>

            <p>
                Pending:
                <b>{pending}</b>
            </p>

            <p>
                Delivered:
                <b>{delivered}</b>
            </p>

            <p>
                Total Payment:
                <b>{money(total_payment)}</b>
            </p>

        </div>


        <div class="panel">

            <h3>
                👑 Top Customers
            </h3>

            <div class="table">

                <table>

                    <tr>
                        <th>Customer</th>
                        <th>Total Work</th>
                    </tr>

    """

    for customer in top_customers:

        body += f"""

                    <tr>

                        <td>
                            {esc(customer["name"])}
                        </td>

                        <td>
                            {money(customer["total"])}
                        </td>

                    </tr>

        """

    body += """

                </table>

            </div>

        </div>

    </div>


    <div class="panel">

        <h3>
            📄 Report Actions
        </h3>

        <div class="actions">

            <button
                onclick="window.print()"
                class="blue"
            >
                🖨️ PRINT REPORT
            </button>

            <a
                href="/reports/pdf"
                class="btn green"
            >
                📄 DOWNLOAD PDF
            </a>

        </div>

    </div>

    """

    return page(
        "Reports",
        body
    )


# =================================
# PDF REPORT
# =================================

@app.get("/reports/pdf")
@login_required
def reports_pdf():

    try:

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle
        )
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.enums import TA_CENTER

    except ImportError:

        flash(
            "PDF ke liye reportlab install karo: pip install reportlab",
            "error"
        )

        return redirect(
            url_for("reports")
        )


    con = db()

    customers_count = con.execute(
        """
        SELECT COUNT(*) c
        FROM customers
        WHERE active=1
        """
    ).fetchone()["c"]


    jobs_count = con.execute(
        """
        SELECT COUNT(*) c
        FROM jobs
        """
    ).fetchone()["c"]


    total_work = con.execute(
        """
        SELECT COALESCE(
            SUM(work_amount), 0
        ) c
        FROM jobs
        """
    ).fetchone()["c"]


    total_payment = con.execute(
        """
        SELECT COALESCE(
            SUM(amount), 0
        ) c
        FROM payments
        """
    ).fetchone()["c"]


    pending = con.execute(
        """
        SELECT COUNT(*) c
        FROM jobs
        WHERE status != 'Delivered'
        """
    ).fetchone()["c"]


    delivered = (
        jobs_count - pending
    )


    final_balance = (
        total_work - total_payment
    )


    top_customers = con.execute(
        """
        SELECT
            customers.name,
            COALESCE(
                SUM(jobs.work_amount),
                0
            ) total
        FROM jobs
        JOIN customers
            ON jobs.customer_id =
               customers.id
        GROUP BY customers.id
        ORDER BY total DESC
        LIMIT 10
        """
    ).fetchall()


    con.close()


    pdf_name = (
        "RK_Jewellers_Report_"
        + datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        + ".pdf"
    )


    pdf_path = (
        APP_DIR / pdf_name
    )


    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )


    styles = getSampleStyleSheet()


    title_style = styles["Title"]
    title_style.alignment = TA_CENTER


    normal = styles["Normal"]


    story = []


    story.append(
        Paragraph(
            "R.K JEWELERS",
            title_style
        )
    )


    story.append(
        Paragraph(
            "Jewellery Job Work & Customer Ledger",
            normal
        )
    )


    story.append(
        Spacer(1, 15)
    )


    story.append(
        Paragraph(
            "Business Report",
            styles["Heading2"]
        )
    )


    story.append(
        Paragraph(
            "Generated: "
            + datetime.now().strftime(
                "%d-%m-%Y %H:%M"
            ),
            normal
        )
    )


    story.append(
        Spacer(1, 15)
    )


    summary_data = [

        ["Report", "Value"],

        [
            "Active Customers",
            str(customers_count)
        ],

        [
            "Total Jobs",
            str(jobs_count)
        ],

        [
            "Pending Jobs",
            str(pending)
        ],

        [
            "Delivered Jobs",
            str(delivered)
        ],

        [
            "Total Kaam",
            money(total_work)
        ],

        [
            "Total Payment",
            money(total_payment)
        ],

        [
            "Total Baaki",
            money(final_balance)
        ]

    ]


    summary_table = Table(
        summary_data,
        colWidths=[250, 180]
    )


    summary_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#4a2915")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                8
            )

        ])
    )


    story.append(
        summary_table
    )


    story.append(
        Spacer(1, 20)
    )


    story.append(
        Paragraph(
            "Top Customers",
            styles["Heading2"]
        )
    )


    customer_data = [
        [
            "Customer",
            "Total Work"
        ]
    ]


    for customer in top_customers:

        customer_data.append(
            [
                str(customer["name"]),
                money(customer["total"])
            ]
        )


    if len(customer_data) == 1:

        customer_data.append(
            [
                "No customer data",
                "-"
            ]
        )


    customer_table = Table(
        customer_data,
        colWidths=[250, 180]
    )


    customer_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#4a2915")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                8
            )

        ])
    )


    story.append(
        customer_table
    )


    story.append(
        Spacer(1, 25)
    )


    story.append(
        Paragraph(
            "R.K JEWELERS",
            styles["Heading3"]
        )
    )


    story.append(
        Paragraph(
            "Jewellery Job Work Management System",
            normal
        )
    )


    doc.build(story)


    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=pdf_name
    )


# =================================
# DATABASE BACKUP
# =================================

@app.get("/backup")
@login_required
def backup():

    if not DB.exists():

        setup()


    filename = (
        "rk_jewellers_backup_"
        + datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        + ".db"
    )


    target = (
        BACKUP_DIR / filename
    )


    shutil.copy2(
        DB,
        target
    )


    return send_file(
        target,
        as_attachment=True,
        download_name=filename
    )


# =================================
# RESTORE DATABASE
# =================================

@app.route(
    "/restore",
    methods=["GET", "POST"]
)
@login_required
def restore():

    if request.method == "POST":

        backup_file = request.files.get(
            "backup"
        )


        if (
            not backup_file
            or not backup_file.filename
            or not backup_file.filename.lower().endswith(
                ".db"
            )
        ):

            flash(
                "Valid .db backup file select karo.",
                "error"
            )

            return redirect(
                url_for("restore")
            )


        safety_name = (
            "before_restore_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )
            + ".db"
        )


        safety_path = (
            BACKUP_DIR / safety_name
        )


        if DB.exists():

            shutil.copy2(
                DB,
                safety_path
            )


        temp_path = (
            BACKUP_DIR /
            "restore_temp.db"
        )


        backup_file.save(
            temp_path
        )


        try:

            test_con = sqlite3.connect(
                temp_path
            )


            test_con.execute(
                """
                SELECT name
                FROM sqlite_master
                LIMIT 1
                """
            )


            test_con.close()


            shutil.copy2(
                temp_path,
                DB
            )


            setup()


            flash(
                "Backup restore ho gaya.",
                "success"
            )


        except Exception as e:

            flash(
                f"Restore fail: {e}",
                "error"
            )


        finally:

            if temp_path.exists():

                temp_path.unlink()


        return redirect(
            url_for("restore")
        )


    body = """

    <h2>
        ♻️ Restore Backup
    </h2>


    <div class="panel">

        <p>

            <b>Important:</b>

            Restore karne se current
            database replace hoga.

            Safety backup pehle
            automatically banega.

        </p>


        <form
            method="post"
            enctype="multipart/form-data"
        >

            <input
                type="file"
                name="backup"
                accept=".db"
                required
            >

            <br><br>


            <button
                class="red"
                type="submit"
            >
                RESTORE DATABASE
            </button>

        </form>

    </div>


    <div class="panel">

        <h3>
            Backup Folder
        </h3>

        <p class="muted">
            Database backups automatically
            yahan store honge.
        </p>

    </div>

    """

    return page(
        "Restore",
        body
    )


# =================================
# SHOP INFORMATION
# =================================

@app.get("/about")
@login_required
def about():

    body = """

    <div class="panel">

        <h1>
            💎 R.K JEWELERS 💎
        </h1>

        <h2>
            ॥ जय माताजी री ॥
        </h2>

        <p>
            Jewellery Job Work &
            Customer Ledger
        </p>


        <p>

            <b>Owner:</b>
            Ramkishor Soni

        </p>


        <hr>


        <h3>
            Available Services
        </h3>


        <p>
            💍 Nag Setting
        </p>

        <p>
            💍 Kachi Jadai
        </p>

        <p>
            ✨ Chilai
        </p>

        <p>
            💎 Other Jewellery Work
        </p>


        <hr>


        <p>

            <b>Developer:</b>
            KRISHNA

        </p>


        <p class="muted">

            Ledger,
            Search,
            Edit,
            Job Status,
            Weight Details,
            Payment Modes,
            Reports,
            PDF,
            Backup,
            Restore
            aur Login System.

        </p>

    </div>

    """


    return page(
        "Shop Information",
        body
    )


# =================================
# START APPLICATION
# =================================

setup()


if __name__ == "__main__":

    print()
    print(
        "==================================="
    )

    print(
        "       R.K JEWELERS PRO"
    )

    print(
        "==================================="
    )

    print(
        "Open on laptop:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print(
        "Login page open karke"
        " apna username/password enter karein."
    )

    print(
        "Server stop karne ke liye CTRL+C"
    )

    print(
        "==================================="
    )


    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
