from flask import Flask, render_template, request, redirect
import sqlite3
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secretkey123'
app.jinja_env.autoescape = True

# ---------- Flask-Login Setup ----------
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# ---------- User Class ----------
class User(UserMixin):
    def __init__(self, id_, username, password):
        self.id = id_
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

# ---------- Initialize Database ----------
def init_db():
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Expenses table
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            date TEXT,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Budget table
    c.execute('''
        CREATE TABLE IF NOT EXISTS budget (
            user_id INTEGER PRIMARY KEY,
            amount REAL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

# ---------- Routes ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('expenses.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username already exists"
        conn.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('expenses.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            user_obj = User(user[0], user[1], user[2])
            login_user(user_obj)
            return redirect('/')
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
    amount = request.form['budget']
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()
    c.execute("REPLACE INTO budget (user_id, amount) VALUES (?, ?)", (current_user.id, amount))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = sqlite3.connect('expenses.db')
    c = conn.cursor()

    # Add expense
    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']
        note = request.form['note']
        c.execute("INSERT INTO expenses (user_id, amount, category, date, note) VALUES (?, ?, ?, ?, ?)",
                  (current_user.id, amount, category, date, note))
        conn.commit()

    # Date filter logic
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date and end_date:
        c.execute("SELECT * FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC",
                  (current_user.id, start_date, end_date))
        data = c.fetchall()

        c.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?", 
                  (current_user.id, start_date, end_date))
        total_spent = c.fetchone()[0] or 0

        c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? GROUP BY category",
                  (current_user.id, start_date, end_date))
        category_data = c.fetchall()

        c.execute("SELECT date, SUM(amount) FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? GROUP BY date",
                  (current_user.id, start_date, end_date))
        daily_data = c.fetchall()
    else:
        # No filter: show all
        c.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (current_user.id,))
        data = c.fetchall()

        c.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (current_user.id,))
        total_spent = c.fetchone()[0] or 0

        c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY category", (current_user.id,))
        category_data = c.fetchall()

        c.execute("SELECT date, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY date", (current_user.id,))
        daily_data = c.fetchall()

    # 📅 Monthly Budget & Spend
    this_month = datetime.now().strftime('%Y-%m')
    c.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date LIKE ?", (current_user.id, f"{this_month}%",))
    monthly_spent = c.fetchone()[0] or 0

    c.execute("SELECT amount FROM budget WHERE user_id = ?", (current_user.id,))
    row = c.fetchone()
    budget = row[0] if row else 0

    conn.close()

    return render_template("index.html",
                           data=data,
                           total_spent=total_spent,
                           category_data=category_data,
                           daily_data=daily_data,
                           monthly_spent=monthly_spent,
                           budget=budget)

# ---------- Run ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

