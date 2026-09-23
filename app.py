from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Couple
import secrets

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

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered"

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        new_couple = Couple(invite_code=secrets.token_hex(4))
        db.session.add(new_couple)
        db.session.commit()

        new_user = User(email=email, password_hash=password_hash, couple_id=new_couple.id)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return f"Signed up! Your invite code is {new_couple.invite_code}"

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return "Logged in successfully"
        else:
            return "Invalid email or password"

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return "Logged out"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)