from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Couple, DateEntry
import secrets
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heartclock.db'
app.config['SECRET_KEY'] = 'dev-secret-change-later'

db.init_app(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return "Heartclock is alive"

@app.route('/home')
@login_required
def home_page():
    entries = DateEntry.query.filter_by(couple_id=current_user.couple_id).order_by(DateEntry.date.desc()).all()
    return render_template('home.html', entries=entries)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        invite_code = request.form.get('invite_code', '').strip()

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered"

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        if invite_code:
            couple = Couple.query.filter_by(invite_code=invite_code).first()
            if not couple:
                return "Invalid invite code"
        else:
            couple = Couple(invite_code=secrets.token_hex(4))
            db.session.add(couple)
            db.session.commit()

        new_user = User(email=email, password_hash=password_hash, couple_id=couple.id)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        if invite_code:
            print(f"{email} joined couple {couple.id}")
        else:
            print(f"{email} created couple with invite code: {couple.invite_code}")

        return redirect(url_for('home_page'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home_page'))
        else:
            return "Invalid email or password"

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return "Logged out"

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_date():
    if request.method == 'POST':
        title = request.form['title']
        date_str = request.form['date']
        location = request.form['location']
        notes = request.form['notes']

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        new_entry = DateEntry(
            couple_id=current_user.couple_id,
            title=title,
            date=date_obj,
            location=location,
            notes=notes
        )
        db.session.add(new_entry)
        db.session.commit()

        return redirect(url_for('home_page'))

    return render_template('add_date.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)