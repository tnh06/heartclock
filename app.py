from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Couple, DateEntry, ActiveSession
import secrets
import os
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heartclock.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-later')

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
    if current_user.is_authenticated:
        return redirect(url_for('home_page'))
    return render_template('landing.html')

@app.route('/home')
@login_required
def home_page():
    if not current_user.couple_id:
        flash("You're not in a relationship yet. Join one or start one below.")
        return redirect(url_for('you'))

    active_session = ActiveSession.query.filter_by(couple_id=current_user.couple_id).first()
    couple = Couple.query.get(current_user.couple_id)
    member_count = User.query.filter_by(couple_id=current_user.couple_id).count()
    return render_template('home.html', active_session=active_session,
                           couple=couple, member_count=member_count)

@app.route('/archive')
@login_required
def archive():
    if not current_user.couple_id:
        flash("You're not in a relationship yet. Join one or start one below.")
        return redirect(url_for('you'))

    entries = DateEntry.query.filter_by(couple_id=current_user.couple_id).order_by(DateEntry.date.desc()).all()
    return render_template('archive.html', entries=entries)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        invite_code = request.form.get('invite_code', '').strip()
        display_name = request.form['display_name'].strip()

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("That email already registered.")
            return redirect(url_for('signup'))

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        if invite_code:
            couple = Couple.query.filter_by(invite_code=invite_code).first()
            if not couple:
                flash("That invite code doesn't match any account.")
                return redirect(url_for('signup'))
            if User.query.filter_by(couple_id=couple.id).count() >= 2:
                flash("That couple already has two members")
                return redirect(url_for('signup'))
        else:
            couple = Couple(invite_code=secrets.token_hex(4))
            db.session.add(couple)
            db.session.commit()

        new_user = User(email=email, display_name=display_name, password_hash=password_hash, couple_id=couple.id)
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
            flash("Invalid email or password.")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_date():
    if request.method == 'POST':
        title = request.form['title']
        date_str = request.form['date']
        notes = request.form['notes']

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        new_entry = DateEntry(
            couple_id=current_user.couple_id,
            author_id=current_user.id,
            title=title,
            date=date_obj,
            notes=notes
        )
        db.session.add(new_entry)
        db.session.commit()

        return redirect(url_for('home_page'))

    return render_template('add_date.html')

@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_date(entry_id):
    entry = DateEntry.query.get_or_404(entry_id)

    if entry.couple_id != current_user.couple_id:
        return "Not authorized", 403

    if request.method == 'POST':
        entry.title = request.form['title']
        entry.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        entry.notes = request.form['notes']
        db.session.commit()
        return redirect(url_for('archive'))

    return render_template('edit_date.html', entry=entry)

@app.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_date(entry_id):
    entry = DateEntry.query.get_or_404(entry_id)

    if entry.couple_id != current_user.couple_id:
        return "Not authorized", 403

    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('archive'))

@app.route('/clock-in', methods=['POST'])
@login_required
def clock_in():
    if not current_user.couple_id:
        flash("You're not in a relationship yet. Join one or start one below.")
        return redirect(url_for('you'))

    existing = ActiveSession.query.filter_by(couple_id=current_user.couple_id).first()
    if not existing:
        session = ActiveSession(couple_id=current_user.couple_id)
        db.session.add(session)
        db.session.commit()
    return redirect(url_for('home_page'))

@app.route('/clock-out', methods=['POST'])
@login_required
def clock_out():
    if not current_user.couple_id:
        flash("You're not in a relationship yet. Join one or start one below.")
        return redirect(url_for('you'))

    active = ActiveSession.query.filter_by(couple_id=current_user.couple_id).first()
    if not active:
        return redirect(url_for('home_page'))

    ended_at = datetime.utcnow()
    elapsed = ended_at - active.started_at
    minutes = max(1, round(elapsed.total_seconds() / 60))

    db.session.delete(active)
    db.session.commit()

    return redirect(url_for('log_date',
                             started_at=active.started_at.isoformat(),
                             ended_at=ended_at.isoformat(),
                             minutes=minutes))

@app.route('/log-date', methods=['GET', 'POST'])
@login_required
def log_date():
    if request.method == 'POST':
        new_entry = DateEntry(
            couple_id=current_user.couple_id,
            author_id=current_user.id,
            title=request.form['title'],
            date=datetime.now().date(),
            notes=request.form['notes'],
            duration_minutes=int(request.form['minutes']),
            started_at=datetime.fromisoformat(request.form['started_at']),
            ended_at=datetime.fromisoformat(request.form['ended_at'])
        )
        db.session.add(new_entry)
        db.session.commit()
        return redirect(url_for('archive'))

    return render_template('log_date.html',
                           started_at=request.args.get('started_at'),
                           ended_at=request.args.get('ended_at'),
                           minutes=request.args.get('minutes'))

@app.route('/you')
@login_required
def you():
    couple = Couple.query.get(current_user.couple_id) if current_user.couple_id else None
    partner = None
    if couple:
        partner = User.query.filter(
            User.couple_id == couple.id,
            User.id != current_user.id
        ).first()
    return render_template('you.html', couple=couple, partner=partner)

@app.route('/gallery')
@login_required
def gallery():
    if not current_user.couple_id:
        flash("You're not in a relationship yet. Join one or start one below.")
        return redirect(url_for('you'))

    entries = DateEntry.query.filter(
        DateEntry.couple_id == current_user.couple_id,
        DateEntry.photo_path.isnot(None)
    ).order_by(DateEntry.date.desc()).all()
    return render_template('gallery.html', entries=entries)

@app.route('/you/update-name', methods=['POST'])
@login_required
def update_name():
    name = request.form['display_name'].strip()
    if name:
        current_user.display_name = name
        db.session.commit()
        flash("Name updated.")
    return redirect(url_for('you'))

@app.route('/you/leave', methods=['POST'])
@login_required
def leave_relationship():
    current_user.couple_id = None
    db.session.commit()
    flash("You've left the relationship.")
    return redirect(url_for('you'))

@app.route('/you/join', methods=['POST'])
@login_required
def join_relationship():
    code = request.form.get('invite_code', '').strip()
    couple = Couple.query.filter_by(invite_code=code).first()
    if not couple:
        flash("Invalid invite code.")
        return redirect(url_for('you'))
    if User.query.filter_by(couple_id=couple.id).count() >= 2:
        flash("That couple already has two members.")
        return redirect(url_for('you'))
    current_user.couple_id = couple.id
    db.session.commit()
    flash("Joined.")
    return redirect(url_for('you'))

@app.route('/you/new-code', methods=['POST'])
@login_required
def new_code():
    couple = Couple(invite_code=secrets.token_hex(4))
    db.session.add(couple)
    db.session.commit()
    current_user.couple_id = couple.id
    db.session.commit()
    return redirect(url_for('you'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)