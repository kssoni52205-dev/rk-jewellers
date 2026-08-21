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

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

import sqlite3
from datetime import datetime
from pathlib import Path
from functools import wraps
from io import BytesIO
import os
import html
import shutil

# ============================================================
# PDF
# ============================================================

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


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
    or os.urandom(32)
)


# ============================================================
# LOGIN DETAILS
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
# PDF DEVANAGARI FONT
# ============================================================

PDF_FONT = "Helvetica"

FONT_CANDIDATES = [
    APP_DIR / "NotoSansDevanagari-Regular.ttf",
    APP_DIR / "static" / "NotoSansDevanagari-Regular.ttf",

    Path(
        "/usr/share/fonts/truetype/noto/"
        "NotoSansDevanagari-Regular.ttf"
    ),

    Path(
        "/usr/share/fonts/opentype/noto/"
        "NotoSansDevanagari-Regular.ttf"
    ),

    Path(
        "/usr/share/fonts/truetype/lohit-devanagari/"
        "Lohit-Devanagari.ttf"
    ),

    Path(
        "C:/Windows/Fonts/"
        "Nirmala.ttf"
    ),

    Path(
        "C:/Windows/Fonts/"
        "mangal.ttf"
    )
]

for font_path in FONT_CANDIDATES:

    try:

        if font_path.exists():

            pdfmetrics.registerFont(
                TTFont(
                    "RkDevanagari",
                    str(font_path)
                )
            )

            PDF_FONT = "RkDevanagari"

            print(
                "PDF Hindi Font:",
                font_path
            )

            break

    except Exception as font_error:

        print(
            "Font load error:",
            font_error
        )


if PDF_FONT == "Helvetica":

    print(
        "WARNING: Devanagari PDF font not found."
    )

    print(
        "Add NotoSansDevanagari-Regular.ttf "
        "next to rk_jewellers_pro.py"
    )


# ============================================================
# DATABASE
# ============================================================

def db():

    con = sqlite3.connect(
        DB,
        timeout=30
    )

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

        work TEXT DEFAULT 'Other',

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

        diamond_weight REAL DEFAULT 0,

        diamond_count INTEGER DEFAULT 0,

        fancy_diamond TEXT DEFAULT '',

        touch_weight REAL DEFAULT 0,

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

    def add_column(
        table,
        column,
        definition
    ):

        columns = {
            row["name"]
            for row in con.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        if column not in columns:

            con.execute(
                f"""
                ALTER TABLE {table}
                ADD COLUMN {column} {definition}
                """
            )


    # ========================================================
    # CUSTOMERS
    # ========================================================

    add_column(
        "customers",
        "mobile",
        "TEXT DEFAULT ''"
    )

    add_column(
        "customers",
        "address",
        "TEXT DEFAULT ''"
    )

    add_column(
        "customers",
        "notes",
        "TEXT DEFAULT ''"
    )

    add_column(
        "customers",
        "active",
        "INTEGER NOT NULL DEFAULT 1"
    )

    add_column(
        "customers",
        "created_at",
        "TEXT"
    )


    # ========================================================
    # JOBS
    # ========================================================

    add_column(
        "jobs",
        "customer_id",
        "INTEGER"
    )

    add_column(
        "jobs",
        "date",
        "TEXT DEFAULT ''"
    )

    add_column(
        "jobs",
        "jewellery",
        "TEXT DEFAULT ''"
    )

    add_column(
        "jobs",
        "work",
        "TEXT DEFAULT 'Other'"
    )

    add_column(
        "jobs",
        "status",
        "TEXT NOT NULL DEFAULT 'Pending'"
    )

    # पुराने fields केवल database compatibility के लिए

    add_column(
        "jobs",
        "maal_aaya",
        "TEXT DEFAULT ''"
    )

    add_column(
        "jobs",
        "maal_diyaa",
        "TEXT DEFAULT ''"
    )

    add_column(
        "jobs",
        "gross_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "nag_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "total_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "loss",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "final_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "stone_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "net_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "diamond_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "diamond_count",
        "INTEGER DEFAULT 0"
    )

    add_column(
        "jobs",
        "fancy_diamond",
        "TEXT DEFAULT ''"
    )

    # पुराने columns रखे हैं, लेकिन UI/calculation में नहीं
    add_column(
        "jobs",
        "touch_weight",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "quantity",
        "INTEGER DEFAULT 1"
    )

    add_column(
        "jobs",
        "taanch",
        "TEXT DEFAULT ''"
    )

    add_column(
        "jobs",
        "work_amount",
        "REAL DEFAULT 0"
    )

    add_column(
        "jobs",
        "notes",
        "TEXT DEFAULT ''"
    )

    add_column(
        "jobs",
        "created_at",
        "TEXT"
    )


    # ========================================================
    # PAYMENTS
    # ========================================================

    add_column(
        "payments",
        "mode",
        "TEXT NOT NULL DEFAULT 'Cash'"
    )

    add_column(
        "payments",
        "note",
        "TEXT DEFAULT ''"
    )

    add_column(
        "payments",
        "created_at",
        "TEXT"
    )


    con.commit()

    con.close()


def ensure_database():

    setup()


@app.before_request
def initialize_database():

    ensure_database()


# ============================================================
# HELPERS
# ============================================================

def money(value):

    try:

        value = float(
            value or 0
        )

    except Exception:

        value = 0

    return "₹ {:,.2f}".format(
        value
    )


def esc(value):

    return html.escape(
        ""
        if value is None
        else str(value)
    )


def parse_float(
    name,
    default=0.0
):

    value = request.form.get(
        name,
        ""
    ).strip()

    if value == "":

        return default

    try:

        return float(value)

    except ValueError:

        raise ValueError(
            f"{name} me valid number dalo."
        )


def parse_int(
    name,
    default=1
):

    value = request.form.get(
        name,
        ""
    ).strip()

    if value == "":

        return default

    try:

        return int(value)

    except ValueError:

        raise ValueError(
            f"{name} me valid number dalo."
        )


def login_required(view):

    @wraps(view)
    def wrapped(
        *args,
        **kwargs
    ):

        if not session.get(
            "logged_in"
        ):

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

BASE_HTML = r"""
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
        "Segoe UI",
        sans-serif;

    background:
        radial-gradient(
            circle at top left,
            #fff6c9,
            transparent 35%
        ),
        linear-gradient(
            135deg,
            #fffdf5,
            #f0d48c
        );

    color:#301b0b;
}

header{

    background:
        linear-gradient(
            135deg,
            #180b05,
            #5b3212,
            #1d0c05
        );

    color:white;

    padding:20px;

    text-align:center;

    border-bottom:
        4px solid #f5c84c;

    box-shadow:
        0 5px 25px #0005;
}

header h1{

    margin:0;

    font-size:34px;

    letter-spacing:2px;

    color:#ffd75b;

    text-shadow:
        0 0 12px #ffb30088;
}

header p{

    margin:5px 0 0;

    color:#fff2bd;
}

.layout{

    display:flex;

    min-height:
        calc(100vh - 105px);
}

nav{

    width:245px;

    flex-shrink:0;

    background:
        linear-gradient(
            180deg,
            #211006,
            #3c1c0b
        );

    padding:15px;

    box-shadow:
        5px 0 20px #0003;
}

nav a{

    display:block;

    text-decoration:none;

    color:white;

    padding:13px;

    margin:7px 0;

    border-radius:12px;

    font-weight:bold;

    transition:.2s;
}

nav a:hover{

    background:
        linear-gradient(
            90deg,
            #f0b72f,
            #ffe083
        );

    color:#241309;

    transform:
        translateX(4px);
}

.userbox{

    color:#ffe48c;

    padding:10px;

    font-size:12px;

    border-bottom:
        1px solid #8d6233;

    margin-bottom:12px;
}

main{

    flex:1;

    padding:24px;

    min-width:0;
}

.cardbox{

    display:grid;

    grid-template-columns:
        repeat(4,1fr);

    gap:15px;
}

.card{

    background:
        rgba(255,255,255,.95);

    padding:20px;

    border-radius:18px;

    box-shadow:
        0 10px 30px #6e461f33;

    border:
        1px solid #ead49d;

    border-left:
        6px solid #d6a52e;
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

    color:#43240f;
}

.panel{

    background:
        rgba(255,255,255,.96);

    padding:20px;

    margin:18px 0;

    border-radius:18px;

    box-shadow:
        0 10px 30px #6e461f33;

    border:
        1px solid #ead49d;
}

.form{

    display:grid;

    grid-template-columns:
        repeat(3,1fr);

    gap:13px;
}

input,
select,
textarea{

    width:100%;

    padding:12px;

    border:
        1px solid #d9c28f;

    border-radius:10px;

    font-size:15px;

    background:#fffdf8;

    outline:none;
}

input:focus,
select:focus,
textarea:focus{

    border-color:#d4a62b;

    box-shadow:
        0 0 0 3px #d4a62b22;
}

textarea{

    min-height:80px;
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

    padding:11px 16px;

    border-radius:10px;

    background:
        linear-gradient(
            135deg,
            #e0ad32,
            #f5d36b
        );

    color:#291506;

    font-weight:bold;

    cursor:pointer;

    text-decoration:none;

    display:inline-block;
}

button:hover,
.btn:hover{

    filter:brightness(1.08);

    transform:
        translateY(-1px);
}

.green{

    background:
        linear-gradient(
            135deg,
            #12854e,
            #25b96f
        );

    color:white;
}

.red{

    background:
        linear-gradient(
            135deg,
            #a7192d,
            #df4b5d
        );

    color:white;
}

.blue{

    background:
        linear-gradient(
            135deg,
            #2058b8,
            #4d8cf5
        );

    color:white;
}

.gray{

    background:#687078;

    color:white;
}

.whatsapp{

    background:
        linear-gradient(
            135deg,
            #128c4a,
            #28d879
        );

    color:white;
}

.small{

    padding:7px 10px;

    font-size:12px;
}

.table{

    overflow-x:auto;
}

table{

    width:100%;

    border-collapse:collapse;

    min-width:1000px;
}

th{

    background:
        linear-gradient(
            90deg,
            #3d210f,
            #6a3a15
        );

    color:#ffe69b;

    padding:11px;

    text-align:left;

    white-space:nowrap;
}

td{

    padding:10px;

    border-bottom:
        1px solid #eee1c4;

    vertical-align:top;
}

tr:hover td{

    background:#fffaf0;
}

.msg{

    background:#dff5e8;

    padding:13px;

    border-radius:11px;

    margin-bottom:15px;

    color:#17663c;

    font-weight:bold;
}

.err{

    background:#ffe1e4;

    padding:13px;

    border-radius:11px;

    margin-bottom:15px;

    color:#8b1e2b;

    font-weight:bold;
}

.badge{

    display:inline-block;

    padding:5px 9px;

    border-radius:999px;

    background:#eee;

    font-size:12px;

    font-weight:bold;
}

.badge.yellow{

    background:#fff0bd;

    color:#785b00;
}

.muted{

    color:#777;
}

.actions{

    display:flex;

    gap:6px;

    flex-wrap:wrap;
}

.balance{

    font-size:28px;

    font-weight:bold;
}

.debit{

    color:#b51f32;

    font-weight:bold;
}

.credit{

    color:#16864f;

    font-weight:bold;
}

.mobile-menu{

    display:none;

    background:#2b180d;

    color:white;

    padding:10px;

    text-align:center;
}

.search-box{

    display:flex;

    gap:8px;
}

.search-box input{

    flex:1;
}

.weight-box{

    border:
        2px solid #e1bb52;

    border-radius:15px;

    padding:15px;

    background:
        linear-gradient(
            135deg,
            #fffdf5,
            #fff3c9
        );
}

.auto-box{

    background:#fff0bc;

    border-color:#d0a52d;

    font-weight:bold;
}

@media(max-width:1050px){

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

        display:none;

        width:100%;
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
JEWELLERY JOB WORK • CUSTOMER LEDGER • ACCOUNTS
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
💎 Job Entry
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

<a href="{{ url_for('search') }}">
🔎 Search
</a>

<a href="{{ url_for('backup') }}">
💾 Backup
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
{{ m }}
</div>

{% endfor %}

{% endwith %}

{% with messages=get_flashed_messages(
    category_filter=['error']
) %}

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


def page(
    title,
    body
):

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
                🔐 R.K JEWELERS
            </h2>

            <p class="muted">
                Secure Shop Management
            </p>

            <form method="post">

                <label>
                    Username
                </label>

                <input
                    name="username"
                    autocomplete="username"
                    required
                >

                <br>

                <label>
                    Password / PIN
                </label>

                <input
                    type="password"
                    name="password"
                    autocomplete="current-password"
                    required
                >

                <br>

                <button
                    class="green"
                    type="submit"
                >
                    🔐 LOGIN
                </button>

            </form>

            <br>

            <small class="muted">
                Developer: KRISHNA
            </small>

        </div>

    </div>

    """

    return page(
        "Login",
        body
    )


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
            SUM(work_amount),
            0
        )
        FROM jobs
        """
    ).fetchone()[0]

    total_paid = con.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
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
            <h3>TOTAL PAYMENT</h3>
            <b>{money(total_paid)}</b>
        </div>

    </div>


    <div class="cardbox"
         style="margin-top:15px;">

        <div class="card">
            <h3>PENDING JOBS</h3>
            <b>{pending}</b>
        </div>

        <div class="card">
            <h3>TOTAL BAAKI</h3>
            <b class="debit">
                {money(balance)}
            </b>
        </div>

    </div>


    <div class="panel">

        <h3>
            ⚡ Quick Actions
        </h3>

        <div class="actions">

            <a
                class="btn green"
                href="{url_for('customers')}"
            >
                ➕ Customer
            </a>

            <a
                class="btn"
                href="{url_for('jobs')}"
            >
                💎 New Job
            </a>

            <a
                class="btn blue"
                href="{url_for('payments')}"
            >
                💰 Payment
            </a>

            <a
                class="btn"
                href="{url_for('reports')}"
            >
                📊 Reports
            </a>

        </div>

    </div>


    <div class="panel">

        <h3>
            ✨ R.K JEWELERS PRO
        </h3>

        <p>
            Jewellery job work, customer ledger,
            payments, automatic weight calculation,
            diamond details aur colourful PDF reports
            ek hi system me.
        </p>

        <p>
            <b>
                Developer: KRISHNA
            </b>
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

                cid = int(
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
                    (cid,)
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

        con.close()

        return redirect(
            url_for("customers")
        )

    rows = con.execute(
        """
        SELECT

            c.*,

            COUNT(j.id) AS jobs_count,

            COALESCE(
                (
                    SELECT SUM(j2.work_amount)
                    FROM jobs j2
                    WHERE j2.customer_id=c.id
                ),
                0
            ) AS total_work,

            COALESCE(
                (
                    SELECT SUM(p.amount)
                    FROM payments p
                    WHERE p.customer_id=c.id
                ),
                0
            ) AS total_paid

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
            ➕ Add Customer
        </h3>

        <form method="post">

            <input
                type="hidden"
                name="action"
                value="add"
            >

            <div class="form">

                <div>

                    <label>Name</label>

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

                <div
                    style="grid-column:1/-1"
                >

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

                <th>Name</th>

                <th>Mobile</th>

                <th>Jobs</th>

                <th>Total Kaam</th>

                <th>Paid</th>

                <th>Baaki</th>

                <th>Action</th>

            </tr>

            {% for r in rows %}

            <tr>

                <td>

                    <b>
                        {{ r["name"] }}
                    </b>

                    {% if r["address"] %}

                    <br>

                    <span class="muted">
                        {{ r["address"] }}
                    </span>

                    {% endif %}

                </td>

                <td>
                    {{ r["mobile"] }}
                </td>

                <td>
                    {{ r["jobs_count"] }}
                </td>

                <td>
                    ₹ {{
                        "%.2f"|format(
                            r["total_work"] or 0
                        )
                    }}
                </td>

                <td class="credit">
                    ₹ {{
                        "%.2f"|format(
                            r["total_paid"] or 0
                        )
                    }}
                </td>

                <td class="debit">
                    ₹ {{
                        "%.2f"|format(
                            (r["total_work"] or 0)
                            -
                            (r["total_paid"] or 0)
                        )
                    }}
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
                            📒 LEDGER
                        </a>

                        {% if r["mobile"] %}

                        <a
                            class="btn small whatsapp"
                            target="_blank"
                            href="https://wa.me/{{ r['mobile']|replace('+','')|replace(' ','')|replace('-','') }}"
                        >
                            💬 WhatsApp
                        </a>

                        {% endif %}

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
                                value="{{ r['id'] }}"
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


            # =================================================
            # WEIGHT DETAILS
            # =================================================

            weight = parse_float(
                "weight"
            )

            nag_weight = parse_float(
                "nag_weight"
            )

            loss = parse_float(
                "loss"
            )

            stone_weight = parse_float(
                "stone_weight"
            )

            diamond_weight = parse_float(
                "diamond_weight"
            )

            diamond_count = parse_int(
                "diamond_count",
                0
            )

            fancy_diamond = request.form.get(
                "fancy_diamond",
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


            # =================================================
            # AUTOMATIC CALCULATION
            # =================================================
            #
            # वजन + नग वजन = कुल वजन
            # कुल वजन - लॉस = अंतिम वजन
            # अंतिम वजन - पत्थर वजन = नेट वजन
            #

            total_weight = (
                weight +
                nag_weight
            )

            final_weight = max(
                0,
                total_weight - loss
            )

            net_weight = max(
                0,
                final_weight - stone_weight
            )


            # =================================================
            # VALIDATION
            # =================================================

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

            if weight < 0:

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

            if stone_weight < 0:

                raise ValueError(
                    "पत्थर वजन negative nahi ho sakta."
                )

            if diamond_weight < 0:

                raise ValueError(
                    "डायमंड वजन negative nahi ho sakta."
                )

            if diamond_count < 0:

                raise ValueError(
                    "डायमंड गिनती negative nahi ho sakti."
                )

            if quantity < 1:

                raise ValueError(
                    "नग kam se kam 1 hona chahiye."
                )

            if work_amount < 0:

                raise ValueError(
                    "Amount negative nahi ho sakta."
                )


            # =================================================
            # UPDATE
            # =================================================

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

                        gross_weight=?,
                        nag_weight=?,
                        total_weight=?,
                        loss=?,
                        final_weight=?,
                        stone_weight=?,
                        net_weight=?,

                        diamond_weight=?,
                        diamond_count=?,
                        fancy_diamond=?,

                        quantity=?,
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

                        weight,
                        nag_weight,
                        total_weight,
                        loss,
                        final_weight,
                        stone_weight,
                        net_weight,

                        diamond_weight,
                        diamond_count,
                        fancy_diamond,

                        quantity,
                        work_amount,
                        notes,

                        edit_id

                    )
                )

                message = (
                    "Job successfully update ho gayi."
                )


            # =================================================
            # INSERT
            # =================================================

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

                        gross_weight,
                        nag_weight,
                        total_weight,
                        loss,
                        final_weight,
                        stone_weight,
                        net_weight,

                        diamond_weight,
                        diamond_count,
                        fancy_diamond,

                        quantity,
                        work_amount,
                        notes,
                        created_at
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

                        weight,
                        nag_weight,
                        total_weight,
                        loss,
                        final_weight,
                        stone_weight,
                        net_weight,

                        diamond_weight,
                        diamond_count,
                        fancy_diamond,

                        quantity,
                        work_amount,
                        notes,

                        datetime.now().isoformat()

                    )
                )

                message = (
                    "Job successfully save ho gayi."
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
                f"Job error: {e}",
                "error"
            )


    customers_rows = con.execute(
        """
        SELECT
            id,
            name
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()


    rows = con.execute(
        """
        SELECT

            j.*,

            c.name AS customer_name,

            c.mobile AS customer_mobile

        FROM jobs j

        LEFT JOIN customers c
            ON c.id=j.customer_id

        ORDER BY
            j.date DESC,
            j.id DESC
        """
    ).fetchall()


    con.close()


    today = datetime.now().strftime(
        "%Y-%m-%d"
    )


    if edit_job:

        selected_customer = (
            edit_job["customer_id"]
        )

        form_date = (
            edit_job["date"]
        )

        form_jewellery = (
            edit_job["jewellery"]
        )

        form_work = (
            edit_job["work"]
        )

        form_status = (
            edit_job["status"]
        )

        form_weight = (
            edit_job["gross_weight"]
            or 0
        )

        form_nag_weight = (
            edit_job["nag_weight"]
            or 0
        )

        form_loss = (
            edit_job["loss"]
            or 0
        )

        form_stone_weight = (
            edit_job["stone_weight"]
            or 0
        )

        form_diamond_weight = (
            edit_job["diamond_weight"]
            or 0
        )

        form_diamond_count = (
            edit_job["diamond_count"]
            or 0
        )

        form_fancy_diamond = (
            edit_job["fancy_diamond"]
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

        button = "UPDATE JOB"


    else:

        selected_customer = ""

        form_date = today

        form_jewellery = ""

        form_work = "Other"

        form_status = "Pending"

        form_weight = 0

        form_nag_weight = 0

        form_loss = 0

        form_stone_weight = 0

        form_diamond_weight = 0

        form_diamond_count = 0

        form_fancy_diamond = ""

        form_quantity = 1

        form_amount = 0

        form_notes = ""

        heading = "💎 NEW JOB ENTRY"

        button = "SAVE JOB"


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
            value="{c['id']}"
            {selected}
        >
            {esc(c['name'])}
        </option>

        """


    body = f"""

    <h2>
        {heading}
    </h2>


    <div class="panel">

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

                <select
                    name="work"
                >

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

                <label>
                    Status
                </label>

                <select
                    name="status"
                >

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
                    डायमंड वजन
                </label>

                <input
                    type="number"
                    step="0.001"
                    min="0"
                    name="diamond_weight"
                    value="{form_diamond_weight}"
                >

            </div>


            <div>

                <label>
                    डायमंड गिनती
                </label>

                <input
                    type="number"
                    min="0"
                    name="diamond_count"
                    value="{form_diamond_count}"
                >

            </div>


            <div>

                <label>
                    फैंसी डायमंड
                </label>

                <input
                    name="fancy_diamond"
                    value="{esc(form_fancy_diamond)}"
                    placeholder="फैंसी डायमंड"
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


        <div class="weight-box">

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
                        name="weight"
                        id="weight"
                        value="{form_weight}"
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
                        value="{form_nag_weight}"
                        oninput="calculateWeight()"
                    >

                </div>


                <div>

                    <label>
                        = कुल वजन
                    </label>

                    <input
                        class="auto-box"
                        type="text"
                        id="total_weight"
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
                        class="auto-box"
                        type="text"
                        id="final_weight"
                        readonly
                    >

                </div>


                <div>

                    <label>
                        पत्थर वजन
                    </label>

                    <input
                        type="number"
                        step="0.001"
                        min="0"
                        name="stone_weight"
                        id="stone_weight"
                        value="{form_stone_weight}"
                        oninput="calculateWeight()"
                    >

                </div>


                <div>

                    <label>
                        = नेट वजन
                    </label>

                    <input
                        class="auto-box"
                        type="text"
                        id="net_weight"
                        readonly
                    >

                </div>


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
            💾 {button}
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

        <h3>
            📋 Job Records
        </h3>

        <div class="table">

        <table>

            <tr>

                <th>ID</th>

                <th>Date</th>

                <th>Customer</th>

                <th>Jewellery</th>

                <th>Work</th>

                <th>वजन विवरण</th>

                <th>डायमंड विवरण</th>

                <th>Amount</th>

                <th>Status</th>

                <th>Action</th>

            </tr>

    """


    for r in rows:

        mobile = (
            str(
                r["customer_mobile"]
                or ""
            )
            .replace("+", "")
            .replace(" ", "")
            .replace("-", "")
        )

        whatsapp = ""

        if mobile:

            whatsapp = f"""

            <a
                class="btn small whatsapp"
                target="_blank"
                href="https://wa.me/{mobile}"
            >
                💬 WhatsApp
            </a>

            """


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
                        {esc(
                            r["customer_name"]
                            or ""
                        )}
                    </b>
                </td>

                <td>
                    {esc(
                        r["jewellery"]
                    )}
                </td>

                <td>
                    {esc(
                        r["work"]
                    )}
                </td>

                <td>

                    वजन:
                    {float(
                        r["gross_weight"]
                        or 0
                    ):.3f} g

                    <br>

                    + नग वजन:
                    {float(
                        r["nag_weight"]
                        or 0
                    ):.3f} g

                    <br>

                    = कुल वजन:
                    {float(
                        r["total_weight"]
                        or 0
                    ):.3f} g

                    <br>

                    - लॉस:
                    {float(
                        r["loss"]
                        or 0
                    ):.3f} g

                    <br>

                    = अंतिम वजन:
                    {float(
                        r["final_weight"]
                        or 0
                    ):.3f} g

                    <br>

                    पत्थर वजन:
                    {float(
                        r["stone_weight"]
                        or 0
                    ):.3f} g

                    <br>

                    = नेट वजन:
                    {float(
                        r["net_weight"]
                        or 0
                    ):.3f} g

                </td>


                <td>

                    डायमंड वजन:
                    {float(
                        r["diamond_weight"]
                        or 0
                    ):.3f} g

                    <br>

                    डायमंड गिनती:
                    {int(
                        r["diamond_count"]
                        or 0
                    )}

                    <br>

                    फैंसी डायमंड:
                    {esc(
                        r["fancy_diamond"]
                        or ""
                    )}

                </td>


                <td>
                    {money(
                        r["work_amount"]
                    )}
                </td>


                <td>

                    <span class="badge yellow">
                        {esc(
                            r["status"]
                        )}
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
                                DELETE
                            </button>

                        </form>


                        {whatsapp}

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

        const weight =
            parseFloat(
                document.getElementById(
                    "weight"
                ).value
            ) || 0;


        const nag =
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


        const stone =
            parseFloat(
                document.getElementById(
                    "stone_weight"
                ).value
            ) || 0;


        const total =
            weight + nag;


        const finalWeight =
            Math.max(
                0,
                total - loss
            );


        const netWeight =
            Math.max(
                0,
                finalWeight - stone
            );


        document.getElementById(
            "total_weight"
        ).value =
            total.toFixed(3);


        document.getElementById(
            "final_weight"
        ).value =
            finalWeight.toFixed(3);


        document.getElementById(
            "net_weight"
        ).value =
            netWeight.toFixed(3);

    }


    document.addEventListener(
        "DOMContentLoaded",
        calculateWeight
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

            if amount <= 0:

                raise ValueError(
                    "Payment amount 0 se bada hona chahiye."
                )

            con.execute(
                """
                INSERT INTO payments
                (
                    customer_id,
                    date,
                    amount,
                    mode,
                    note,
                    created_at
                )
                VALUES(?,?,?,?,?,?)
                """,
                (
                    customer_id,
                    date_value,
                    amount,
                    mode,
                    note,
                    datetime.now().isoformat()
                )
            )

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


    customers_rows = con.execute(
        """
        SELECT
            id,
            name
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()


    rows = con.execute(
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


    body = """

    <h2>
        💰 Payment Entry
    </h2>


    <div class="panel">

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

                        {% for c in customers_rows %}

                        <option
                            value="{{ c['id'] }}"
                        >
                            {{ c['name'] }}
                        </option>

                        {% endfor %}

                    </select>

                </div>


                <div>

                    <label>
                        Date
                    </label>

                    <input
                        type="date"
                        name="date"
                        value="{{ today }}"
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
                        name="amount"
                        min="0.01"
                        required
                    >

                </div>


                <div>

                    <label>
                        Mode
                    </label>

                    <select
                        name="mode"
                    >

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
                            Cheque
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
            📋 Payment History
        </h3>

        <div class="table">

        <table>

            <tr>

                <th>ID</th>

                <th>Date</th>

                <th>Customer</th>

                <th>Amount</th>

                <th>Mode</th>

                <th>Note</th>

            </tr>


            {% for r in rows %}

            <tr>

                <td>
                    {{ r["id"] }}
                </td>

                <td>
                    {{ r["date"] }}
                </td>

                <td>
                    <b>
                        {{ r["customer_name"] }}
                    </b>
                </td>

                <td class="credit">
                    ₹ {{
                        "%.2f"|format(
                            r["amount"] or 0
                        )
                    }}
                </td>

                <td>
                    {{ r["mode"] }}
                </td>

                <td>
                    {{ r["note"] }}
                </td>

            </tr>


            {% else %}

            <tr>

                <td colspan="6">
                    No payments yet.
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
            rows=rows,
            today=today
        )
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
        SELECT
            id,
            name
        FROM customers
        WHERE active=1
        ORDER BY name
        """
    ).fetchall()


    selected = None

    jobs_rows = []

    payment_rows = []

    total_work = 0

    total_paid = 0


    if customer_id:

        selected = con.execute(
            """
            SELECT *
            FROM customers
            WHERE id=?
            """,
            (customer_id,)
        ).fetchone()


        if selected:

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


            total_work = con.execute(
                """
                SELECT COALESCE(
                    SUM(work_amount),
                    0
                )
                FROM jobs
                WHERE customer_id=?
                """,
                (customer_id,)
            ).fetchone()[0]


            total_paid = con.execute(
                """
                SELECT COALESCE(
                    SUM(amount),
                    0
                )
                FROM payments
                WHERE customer_id=?
                """,
                (customer_id,)
            ).fetchone()[0]


    con.close()


    balance = (
        float(total_work or 0)
        -
        float(total_paid or 0)
    )


    customer_name = (
        selected["name"]
        if selected
        else ""
    )


    body = f"""

    <h2>
        📒 Customer Ledger
    </h2>


    <div class="panel no-print">

        <form method="get">

            <label>
                Customer Select
            </label>


            <select
                name="customer_id"
                onchange="this.form.submit()"
            >

                <option value="">
                    Select Customer
                </option>


                {
                    "".join(
                        f'''
                        <option
                            value="{c["id"]}"
                            {"selected"
                                if customer_id == c["id"]
                                else ""}
                        >
                            {esc(c["name"])}
                        </option>
                        '''
                        for c in customers_rows
                    )
                }


            </select>

        </form>

    </div>

    """


    if selected:

        mobile = (
            str(
                selected["mobile"]
                or ""
            )
            .replace("+", "")
            .replace(" ", "")
            .replace("-", "")
        )


        whatsapp_button = ""


        if mobile:

            whatsapp_button = f"""

            <a
                class="btn whatsapp"
                target="_blank"
                href="https://wa.me/{mobile}"
            >
                💬 WHATSAPP
            </a>

            """


        body += f"""

        <div class="cardbox">

            <div class="card">

                <h3>
                    CUSTOMER
                </h3>

                <b>
                    {esc(customer_name)}
                </b>

            </div>


            <div class="card">

                <h3>
                    TOTAL KAAM
                </h3>

                <b>
                    {money(total_work)}
                </b>

            </div>


            <div class="card">

                <h3>
                    TOTAL PAID
                </h3>

                <b class="credit">
                    {money(total_paid)}
                </b>

            </div>


            <div class="card">

                <h3>
                    BAAKI
                </h3>

                <b class="debit">
                    {money(balance)}
                </b>

            </div>

        </div>


        <div class="panel">

            <div class="actions no-print">

                <a
                    class="btn blue"
                    href="{url_for(
                        'ledger_pdf',
                        customer_id=customer_id
                    )}"
                >
                    📄 DOWNLOAD COLOUR PDF
                </a>


                <button
                    class="btn"
                    onclick="window.print()"
                >
                    🖨️ PRINT
                </button>


                {whatsapp_button}

            </div>


            <hr>


            <h3>
                💎 Job Entries
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
                        वजन विवरण
                    </th>

                    <th>
                        डायमंड
                    </th>

                    <th>
                        Amount
                    </th>

                </tr>

        """


        for j in jobs_rows:

            body += f"""

                <tr>

                    <td>
                        {esc(
                            j["date"]
                        )}
                    </td>


                    <td>
                        {esc(
                            j["jewellery"]
                        )}
                    </td>


                    <td>
                        {esc(
                            j["work"]
                        )}
                    </td>


                    <td>

                        वजन:
                        {float(
                            j["gross_weight"]
                            or 0
                        ):.3f} g

                        <br>

                        + नग वजन:
                        {float(
                            j["nag_weight"]
                            or 0
                        ):.3f} g

                        <br>

                        = कुल वजन:
                        {float(
                            j["total_weight"]
                            or 0
                        ):.3f} g

                        <br>

                        - लॉस:
                        {float(
                            j["loss"]
                            or 0
                        ):.3f} g

                        <br>

                        = अंतिम वजन:
                        {float(
                            j["final_weight"]
                            or 0
                        ):.3f} g

                        <br>

                        पत्थर वजन:
                        {float(
                            j["stone_weight"]
                            or 0
                        ):.3f} g

                        <br>

                        = नेट वजन:
                        {float(
                            j["net_weight"]
                            or 0
                        ):.3f} g

                    </td>


                    <td>

                        वजन:
                        {float(
                            j["diamond_weight"]
                            or 0
                        ):.3f} g

                        <br>

                        गिनती:
                        {int(
                            j["diamond_count"]
                            or 0
                        )}

                        <br>

                        फैंसी:
                        {esc(
                            j["fancy_diamond"]
                            or ""
                        )}

                    </td>


                    <td class="debit">

                        {money(
                            j["work_amount"]
                        )}

                    </td>

                </tr>

            """


        body += """

            </table>

            </div>


            <br>


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
                        {esc(
                            p["date"]
                        )}
                    </td>

                    <td class="credit">
                        {money(
                            p["amount"]
                        )}
                    </td>

                    <td>
                        {esc(
                            p["mode"]
                        )}
                    </td>

                    <td>
                        {esc(
                            p["note"]
                        )}
                    </td>

                </tr>

            """


        body += """

            </table>

            </div>

        </div>

        """


    else:

        body += """

        <div class="panel">

            <h3>
                👆 Pehle customer select karo.
            </h3>

        </div>

        """


    return page(
        "Customer Ledger",
        body
    )


# ============================================================
# COLOUR PDF
# ============================================================

@app.route(
    "/ledger/pdf/<int:customer_id>"
)
@login_required
def ledger_pdf(customer_id):

    con = db()


    customer = con.execute(
        """
        SELECT *
        FROM customers
        WHERE id=?
        """,
        (customer_id,)
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


    total_work = con.execute(
        """
        SELECT COALESCE(
            SUM(work_amount),
            0
        )
        FROM jobs
        WHERE customer_id=?
        """,
        (customer_id,)
    ).fetchone()[0]


    total_paid = con.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        )
        FROM payments
        WHERE customer_id=?
        """,
        (customer_id,)
    ).fetchone()[0]


    con.close()


    balance = (
        float(total_work or 0)
        -
        float(total_paid or 0)
    )


    output = BytesIO()


    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28
    )


    styles = getSampleStyleSheet()


    # ========================================================
    # PDF STYLES WITH DEVANAGARI FONT
    # ========================================================

    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName=PDF_FONT,
        alignment=TA_CENTER,
        fontSize=21,
        leading=25,
        textColor=colors.HexColor(
            "#8A5A00"
        ),
        spaceAfter=8
    )


    subtitle_style = ParagraphStyle(
        "SubtitleCustom",
        parent=styles["Normal"],
        fontName=PDF_FONT,
        alignment=TA_CENTER,
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor(
            "#5A3718"
        ),
        spaceAfter=4
    )


    normal = ParagraphStyle(
        "NormalCustom",
        parent=styles["Normal"],
        fontName=PDF_FONT,
        fontSize=8.5,
        leading=11
    )


    small = ParagraphStyle(
        "SmallCustom",
        parent=styles["Normal"],
        fontName=PDF_FONT,
        fontSize=7.5,
        leading=9
    )


    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName=PDF_FONT,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor(
            "#8A5A00"
        ),
        spaceBefore=4,
        spaceAfter=8
    )


    footer_style = ParagraphStyle(
        "FooterStyle",
        parent=styles["Normal"],
        fontName=PDF_FONT,
        alignment=TA_CENTER,
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor(
            "#8A5A00"
        )
    )


    story = []


    # ========================================================
    # HEADER
    # ========================================================

    story.append(
        Paragraph(
            "R.K JEWELERS",
            title_style
        )
    )


    story.append(
        Paragraph(
            "JEWELLERY JOB WORK & CUSTOMER LEDGER",
            subtitle_style
        )
    )


    story.append(
        Paragraph(
            "वजन विवरण • डायमंड विवरण • भुगतान विवरण",
            subtitle_style
        )
    )


    story.append(
        Spacer(1,12)
    )


    # ========================================================
    # CUSTOMER INFORMATION
    # ========================================================

    customer_info = [

        [
            Paragraph(
                "<b>Customer</b>",
                normal
            ),

            Paragraph(
                esc(
                    customer["name"]
                ),
                normal
            )
        ],

        [
            Paragraph(
                "<b>Mobile</b>",
                normal
            ),

            Paragraph(
                esc(
                    customer["mobile"]
                ),
                normal
            )
        ],

        [
            Paragraph(
                "<b>Address</b>",
                normal
            ),

            Paragraph(
                esc(
                    customer["address"]
                ),
                normal
            )
        ]

    ]


    customer_table = Table(
        customer_info,
        colWidths=[
            100,
            400
        ]
    )


    customer_table.setStyle(
        TableStyle([

            (
                "FONTNAME",
                (0,0),
                (-1,-1),
                PDF_FONT
            ),

            (
                "BACKGROUND",
                (0,0),
                (0,-1),
                colors.HexColor(
                    "#F7D77A"
                )
            ),

            (
                "BOX",
                (0,0),
                (-1,-1),
                1,
                colors.HexColor(
                    "#B98920"
                )
            ),

            (
                "INNERGRID",
                (0,0),
                (-1,-1),
                .5,
                colors.HexColor(
                    "#DDC27B"
                )
            ),

            (
                "VALIGN",
                (0,0),
                (-1,-1),
                "TOP"
            )

        ])
    )


    story.append(
        customer_table
    )


    story.append(
        Spacer(1,15)
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    summary = [

        [
            Paragraph(
                "<b>Total Kaam</b>",
                normal
            ),

            Paragraph(
                money(
                    total_work
                ),
                normal
            )
        ],

        [
            Paragraph(
                "<b>Total Paid</b>",
                normal
            ),

            Paragraph(
                money(
                    total_paid
                ),
                normal
            )
        ],

        [
            Paragraph(
                "<b>Baaki</b>",
                normal
            ),

            Paragraph(
                money(
                    balance
                ),
                normal
            )
        ]

    ]


    summary_table = Table(
        summary,
        colWidths=[
            160,
            160
        ]
    )


    summary_table.setStyle(
        TableStyle([

            (
                "FONTNAME",
                (0,0),
                (-1,-1),
                PDF_FONT
            ),

            (
                "BACKGROUND",
                (0,0),
                (0,-1),
                colors.HexColor(
                    "#3D210F"
                )
            ),

            (
                "TEXTCOLOR",
                (0,0),
                (0,-1),
                colors.HexColor(
                    "#FFE69B"
                )
            ),

            (
                "BACKGROUND",
                (1,0),
                (1,-1),
                colors.HexColor(
                    "#FFF5D5"
                )
            ),

            (
                "BOX",
                (0,0),
                (-1,-1),
                1,
                colors.HexColor(
                    "#B98920"
                )
            ),

            (
                "INNERGRID",
                (0,0),
                (-1,-1),
                .5,
                colors.HexColor(
                    "#DDC27B"
                )
            ),

            (
                "ALIGN",
                (1,0),
                (1,-1),
                "RIGHT"
            ),

            (
                "VALIGN",
                (0,0),
                (-1,-1),
                "MIDDLE"
            )

        ])
    )


    story.append(
        summary_table
    )


    story.append(
        Spacer(1,18)
    )


    # ========================================================
    # JOB ENTRIES
    # ========================================================

    story.append(
        Paragraph(
            "JOB ENTRIES",
            heading_style
        )
    )


    if not jobs_rows:

        story.append(
            Paragraph(
                "कोई Job Entry उपलब्ध नहीं है।",
                normal
            )
        )


    for index, j in enumerate(
        jobs_rows,
        start=1
    ):

        gross_weight = float(
            j["gross_weight"]
            or 0
        )

        nag_weight = float(
            j["nag_weight"]
            or 0
        )

        total_weight = float(
            j["total_weight"]
            or (
                gross_weight +
                nag_weight
            )
        )

        loss = float(
            j["loss"]
            or 0
        )

        final_weight = float(
            j["final_weight"]
            or max(
                0,
                total_weight - loss
            )
        )

        stone_weight = float(
            j["stone_weight"]
            or 0
        )

        net_weight = float(
            j["net_weight"]
            or max(
                0,
                final_weight - stone_weight
            )
        )

        diamond_weight = float(
            j["diamond_weight"]
            or 0
        )

        diamond_count = int(
            j["diamond_count"]
            or 0
        )

        quantity = int(
            j["quantity"]
            or 0
        )

        fancy_diamond = esc(
            j["fancy_diamond"]
            or "-"
        )


        # ====================================================
        # JOB HEADER
        # ====================================================

        job_header = Table(
            [
                [
                    Paragraph(
                        f"<b>Job #{index}</b>",
                        normal
                    ),

                    Paragraph(
                        f"<b>Date:</b> {esc(j['date'])}",
                        normal
                    ),

                    Paragraph(
                        f"<b>Customer:</b> "
                        f"{esc(customer['name'])}",
                        normal
                    ),

                    Paragraph(
                        f"<b>Work:</b> "
                        f"{esc(j['work'])}",
                        normal
                    )
                ]
            ],
            colWidths=[
                55,
                90,
                195,
                90
            ]
        )


        job_header.setStyle(
            TableStyle([

                (
                    "FONTNAME",
                    (0,0),
                    (-1,-1),
                    PDF_FONT
                ),

                (
                    "BACKGROUND",
                    (0,0),
                    (-1,-1),
                    colors.HexColor(
                        "#FFF0BA"
                    )
                ),

                (
                    "BOX",
                    (0,0),
                    (-1,-1),
                    1,
                    colors.HexColor(
                        "#C79D35"
                    )
                ),

                (
                    "VALIGN",
                    (0,0),
                    (-1,-1),
                    "TOP"
                )

            ])
        )


        story.append(
            job_header
        )


        story.append(
            Spacer(1,4)
        )


        # ====================================================
        # FULL WEIGHT + DIAMOND DETAILS
        # ====================================================

        details = [

            [
                Paragraph(
                    "<b>वजन विवरण</b>",
                    normal
                ),

                Paragraph(
                    "<b>मान</b>",
                    normal
                ),

                Paragraph(
                    "<b>डायमंड विवरण</b>",
                    normal
                ),

                Paragraph(
                    "<b>मान</b>",
                    normal
                )
            ],


            [
                Paragraph(
                    "वजन",
                    normal
                ),

                Paragraph(
                    f"{gross_weight:.3f} g",
                    normal
                ),

                Paragraph(
                    "डायमंड वजन",
                    normal
                ),

                Paragraph(
                    f"{diamond_weight:.3f} g",
                    normal
                )
            ],


            [
                Paragraph(
                    "+ नग वजन",
                    normal
                ),

                Paragraph(
                    f"{nag_weight:.3f} g",
                    normal
                ),

                Paragraph(
                    "डायमंड गिनती",
                    normal
                ),

                Paragraph(
                    str(
                        diamond_count
                    ),
                    normal
                )
            ],


            [
                Paragraph(
                    "= कुल वजन",
                    normal
                ),

                Paragraph(
                    f"{total_weight:.3f} g",
                    normal
                ),

                Paragraph(
                    "फैंसी डायमंड",
                    normal
                ),

                Paragraph(
                    fancy_diamond,
                    normal
                )
            ],


            [
                Paragraph(
                    "- लॉस",
                    normal
                ),

                Paragraph(
                    f"{loss:.3f} g",
                    normal
                ),

                Paragraph(
                    "नग",
                    normal
                ),

                Paragraph(
                    str(
                        quantity
                    ),
                    normal
                )
            ],


            [
                Paragraph(
                    "= अंतिम वजन",
                    normal
                ),

                Paragraph(
                    f"{final_weight:.3f} g",
                    normal
                ),

                Paragraph(
                    "काम की रकम",
                    normal
                ),

                Paragraph(
                    money(
                        j["work_amount"]
                    ),
                    normal
                )
            ],


            [
                Paragraph(
                    "पत्थर वजन",
                    normal
                ),

                Paragraph(
                    f"{stone_weight:.3f} g",
                    normal
                ),

                Paragraph(
                    "स्टेटस",
                    normal
                ),

                Paragraph(
                    esc(
                        j["status"]
                    ),
                    normal
                )
            ],


            [
                Paragraph(
                    "= नेट वजन",
                    normal
                ),

                Paragraph(
                    f"{net_weight:.3f} g",
                    normal
                ),

                Paragraph(
                    "Jewellery",
                    normal
                ),

                Paragraph(
                    esc(
                        j["jewellery"]
                    ),
                    normal
                )
            ]

        ]


        details_table = Table(
            details,
            colWidths=[
                85,
                85,
                105,
                155
            ],
            repeatRows=1
        )


        details_table.setStyle(
            TableStyle([

                (
                    "FONTNAME",
                    (0,0),
                    (-1,-1),
                    PDF_FONT
                ),

                (
                    "BACKGROUND",
                    (0,0),
                    (1,0),
                    colors.HexColor(
                        "#4A2915"
                    )
                ),

                (
                    "BACKGROUND",
                    (2,0),
                    (3,0),
                    colors.HexColor(
                        "#17663C"
                    )
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
                    .5,
                    colors.HexColor(
                        "#C9B37D"
                    )
                ),

                (
                    "ROWBACKGROUNDS",
                    (0,1),
                    (-1,-1),
                    [
                        colors.white,
                        colors.HexColor(
                            "#FFF9EA"
                        )
                    ]
                ),

                (
                    "VALIGN",
                    (0,0),
                    (-1,-1),
                    "TOP"
                ),

                (
                    "FONTSIZE",
                    (0,0),
                    (-1,-1),
                    8
                )

            ])
        )


        story.append(
            KeepTogether(
                [
                    details_table,
                    Spacer(1,10)
                ]
            )
        )


        # ====================================================
        # NOTES
        # ====================================================

        if j["notes"]:

            notes_table = Table(
                [
                    [
                        Paragraph(
                            "<b>Notes</b>",
                            normal
                        ),
                        Paragraph(
                            esc(
                                j["notes"]
                            ),
                            normal
                        )
                    ]
                ],
                colWidths=[
                    85,
                    345
                ]
            )


            notes_table.setStyle(
                TableStyle([

                    (
                        "FONTNAME",
                        (0,0),
                        (-1,-1),
                        PDF_FONT
                    ),

                    (
                        "BACKGROUND",
                        (0,0),
                        (0,0),
                        colors.HexColor(
                            "#FFF0BA"
                        )
                    ),

                    (
                        "BOX",
                        (0,0),
                        (-1,-1),
                        .8,
                        colors.HexColor(
                            "#D1B86D"
                        )
                    ),

                    (
                        "INNERGRID",
                        (0,0),
                        (-1,-1),
                        .4,
                        colors.HexColor(
                            "#E4D6AA"
                        )
                    ),

                    (
                        "VALIGN",
                        (0,0),
                        (-1,-1),
                        "TOP"
                    )

                ])
            )


            story.append(
                notes_table
            )

            story.append(
                Spacer(1,12)
            )


    # ========================================================
    # PAYMENTS
    # ========================================================

    story.append(
        Paragraph(
            "PAYMENTS",
            heading_style
        )
    )


    payment_data = [

        [
            Paragraph(
                "<b>Date</b>",
                normal
            ),

            Paragraph(
                "<b>Amount</b>",
                normal
            ),

            Paragraph(
                "<b>Mode</b>",
                normal
            ),

            Paragraph(
                "<b>Note</b>",
                normal
            )
        ]

    ]


    for p in payment_rows:

        payment_data.append(

            [

                Paragraph(
                    esc(
                        p["date"]
                        or ""
                    ),
                    normal
                ),

                Paragraph(
                    money(
                        p["amount"]
                    ),
                    normal
                ),

                Paragraph(
                    esc(
                        p["mode"]
                        or ""
                    ),
                    normal
                ),

                Paragraph(
                    esc(
                        p["note"]
                        or ""
                    ),
                    normal
                )

            ]

        )


    if len(payment_data) == 1:

        payment_data.append(

            [

                Paragraph(
                    "-",
                    normal
                ),

                Paragraph(
                    "-",
                    normal
                ),

                Paragraph(
                    "-",
                    normal
                ),

                Paragraph(
                    "No payments",
                    normal
                )

            ]

        )


    payment_table = Table(
        payment_data,
        repeatRows=1,
        colWidths=[
            85,
            100,
            90,
            175
        ]
    )


    payment_table.setStyle(
        TableStyle([

            (
                "FONTNAME",
                (0,0),
                (-1,-1),
                PDF_FONT
            ),

            (
                "BACKGROUND",
                (0,0),
                (-1,0),
                colors.HexColor(
                    "#17663C"
                )
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
                .5,
                colors.HexColor(
                    "#B7D7C4"
                )
            ),

            (
                "ROWBACKGROUNDS",
                (0,1),
                (-1,-1),
                [
                    colors.white,
                    colors.HexColor(
                        "#F0FFF6"
                    )
                ]
            ),

            (
                "VALIGN",
                (0,0),
                (-1,-1),
                "TOP"
            ),

            (
                "FONTSIZE",
                (0,0),
                (-1,-1),
                8
            )

        ])
    )


    story.append(
        payment_table
    )


    story.append(
        Spacer(1,20)
    )


    # ========================================================
    # FOOTER
    # ========================================================

    story.append(
        Paragraph(
            "Developer: KRISHNA",
            footer_style
        )
    )


    doc.build(
        story
    )


    output.seek(0)


    safe_name = (
        str(
            customer["name"]
        )
        .replace(
            " ",
            "_"
        )
        .replace(
            "/",
            "_"
        )
    )


    return send_file(
        output,
        as_attachment=True,
        download_name=(
            f"RK_JEWELERS_{safe_name}_Ledger.pdf"
        ),
        mimetype="application/pdf"
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

        customers_rows = con.execute(
            """
            SELECT *
            FROM customers

            WHERE active=1

            AND (
                name LIKE ?
                OR mobile LIKE ?
                OR address LIKE ?
            )

            ORDER BY name
            """,

            (
                f"%{q}%",
                f"%{q}%",
                f"%{q}%"
            )
        ).fetchall()


        jobs_rows = con.execute(
            """
            SELECT

                j.*,

                c.name AS customer_name

            FROM jobs j

            LEFT JOIN customers c
                ON c.id=j.customer_id

            WHERE

                c.name LIKE ?
                OR j.jewellery LIKE ?
                OR j.work LIKE ?
                OR j.fancy_diamond LIKE ?

            ORDER BY j.id DESC
            """,

            (
                f"%{q}%",
                f"%{q}%",
                f"%{q}%",
                f"%{q}%"
            )
        ).fetchall()


    else:

        customers_rows = []

        jobs_rows = []


    con.close()


    body = f"""

    <h2>
        🔎 Search
    </h2>


    <div class="panel">

        <form
            method="get"
            class="search-box"
        >

            <input
                name="q"
                value="{esc(q)}"
                placeholder="Customer / Mobile / Jewellery / Work"
            >

            <button
                class="blue"
                type="submit"
            >
                🔍 SEARCH
            </button>

        </form>

    </div>

    """


    if q:

        body += """

        <div class="panel">

            <h3>
                👥 Customers
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
                        Address
                    </th>

                    <th>
                        Action
                    </th>

                </tr>

        """


        for c in customers_rows:

            body += f"""

                <tr>

                    <td>
                        <b>
                            {esc(
                                c["name"]
                            )}
                        </b>
                    </td>

                    <td>
                        {esc(
                            c["mobile"]
                        )}
                    </td>

                    <td>
                        {esc(
                            c["address"]
                        )}
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


        <div class="panel">

            <h3>
                💎 Jobs
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
                        Jewellery
                    </th>

                    <th>
                        Work
                    </th>

                    <th>
                        नेट वजन
                    </th>

                    <th>
                        Diamond
                    </th>

                    <th>
                        Amount
                    </th>

                </tr>

        """


        for j in jobs_rows:

            body += f"""

                <tr>

                    <td>
                        {esc(
                            j["date"]
                        )}
                    </td>

                    <td>
                        {esc(
                            j["customer_name"]
                            or ""
                        )}
                    </td>

                    <td>
                        {esc(
                            j["jewellery"]
                        )}
                    </td>

                    <td>
                        {esc(
                            j["work"]
                        )}
                    </td>

                    <td>
                        {float(
                            j["net_weight"]
                            or 0
                        ):.3f} g
                    </td>

                    <td>

                        {float(
                            j["diamond_weight"]
                            or 0
                        ):.3f} g

                        <br>

                        गिनती:
                        {int(
                            j["diamond_count"]
                            or 0
                        )}

                    </td>

                    <td>
                        {money(
                            j["work_amount"]
                        )}
                    </td>

                </tr>

            """


        body += """

            </table>

            </div>

        </div>

        """


        if (
            not customers_rows
            and
            not jobs_rows
        ):

            body += """

            <div class="panel">

                <h3>
                    ❌ Kuch nahi mila.
                </h3>

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


    jobs_count = con.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        """
    ).fetchone()[0]


    total_final_weight = con.execute(
        """
        SELECT COALESCE(
            SUM(final_weight),
            0
        )
        FROM jobs
        """
    ).fetchone()[0]


    total_stone_weight = con.execute(
        """
        SELECT COALESCE(
            SUM(stone_weight),
            0
        )
        FROM jobs
        """
    ).fetchone()[0]


    total_net_weight = con.execute(
        """
        SELECT COALESCE(
            SUM(net_weight),
            0
        )
        FROM jobs
        """
    ).fetchone()[0]


    total_diamond_weight = con.execute(
        """
        SELECT COALESCE(
            SUM(diamond_weight),
            0
        )
        FROM jobs
        """
    ).fetchone()[0]


    total_diamond_count = con.execute(
        """
        SELECT COALESCE(
            SUM(diamond_count),
            0
        )
        FROM jobs
        """
    ).fetchone()[0]


    total_work = con.execute(
        """
        SELECT COALESCE(
            SUM(work_amount),
            0
        )
        FROM jobs
        """
    ).fetchone()[0]


    total_paid = con.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        )
        FROM payments
        """
    ).fetchone()[0]


    con.close()


    balance = (
        float(total_work)
        -
        float(total_paid)
    )


    body = f"""

    <h2>
        📊 Reports
    </h2>


    <div class="cardbox">

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
                अंतिम वजन
            </h3>

            <b>
                {float(
                    total_final_weight
                ):.3f} g
            </b>

        </div>


        <div class="card">

            <h3>
                पत्थर वजन
            </h3>

            <b>
                {float(
                    total_stone_weight
                ):.3f} g
            </b>

        </div>


        <div class="card">

            <h3>
                नेट वजन
            </h3>

            <b>
                {float(
                    total_net_weight
                ):.3f} g
            </b>

        </div>

    </div>


    <div class="cardbox">

        <div class="card">

            <h3>
                डायमंड वजन
            </h3>

            <b>
                {float(
                    total_diamond_weight
                ):.3f} g
            </b>

        </div>


        <div class="card">

            <h3>
                डायमंड गिनती
            </h3>

            <b>
                {int(
                    total_diamond_count
                    or 0
                )}
            </b>

        </div>


        <div class="card">

            <h3>
                TOTAL WORK
            </h3>

            <b>
                {money(
                    total_work
                )}
            </b>

        </div>


        <div class="card">

            <h3>
                TOTAL PAID
            </h3>

            <b class="credit">
                {money(
                    total_paid
                )}
            </b>

        </div>

    </div>


    <div class="panel">

        <h3>
            💰 Overall Balance
        </h3>

        <div class="balance debit">
            {money(balance)}
        </div>

        <br>

        <button
            class="btn"
            onclick="window.print()"
        >
            🖨️ PRINT REPORT
        </button>

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

    setup()


    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    backup_file = (
        BACKUP_DIR
        /
        f"rk_jewellers_backup_{timestamp}.db"
    )


    shutil.copy2(
        DB,
        backup_file
    )


    return send_file(
        backup_file,
        as_attachment=True,
        download_name=backup_file.name,
        mimetype="application/octet-stream"
    )


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
@login_required
def about():

    body = """

    <div class="panel">

        <h2>
            💎 R.K JEWELERS
        </h2>

        <h3>
            Jewellery Job Work Management
        </h3>

        <p>
            Customer management, jewellery job,
            automatic weight calculation,
            diamond details, payment,
            ledger, reports aur PDF system.
        </p>

        <hr>

        <p>
            <b>Shop:</b>
            R.K JEWELERS
        </p>

        <p>
            <b>Developer:</b>
            KRISHNA
        </p>

        <p>
            <b>Version:</b>
            R.K JEWELERS PRO 2026
        </p>

        <p>
            <b>Calculation:</b>
            वजन + नग वजन = कुल वजन
        </p>

        <p>
            <b>Calculation:</b>
            कुल वजन - लॉस = अंतिम वजन
        </p>

        <p>
            <b>Calculation:</b>
            अंतिम वजन - पत्थर वजन = नेट वजन
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

@app.route("/dashboard")
@login_required
def dashboard():

    return redirect(
        url_for("home")
    )


# ============================================================
# START
# ============================================================

ensure_database()


if __name__ == "__main__":

    print(
        "=" * 55
    )

    print(
        "             R.K JEWELERS PRO"
    )

    print(
        "=" * 55
    )

    print(
        "Developer : KRISHNA"
    )

    print(
        "URL       : http://127.0.0.1:5000"
    )

    print(
        "Username  : admin"
    )

    print(
        "Password  : 1234"
    )

    print(
        "=" * 55
    )


    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )
