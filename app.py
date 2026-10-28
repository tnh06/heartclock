import os
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_wtf.csrf import CSRFError, CSRFProtect
from PIL import Image, ImageOps
from sqlalchemy import func

from models import ActiveSession, Couple, DateEntry, Photo, User, db, utc_now


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI='sqlite:///heartclock.db',
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-change-later'),
    WTF_CSRF_TIME_LIMIT=None,               # a date can run for hours, so tokens must not expire
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,   # 100 MB per form submission
)

db.init_app(app)
bcrypt = Bcrypt(app)
CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = os.path.join(app.instance_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_PHOTOS = 10
MAX_COUPLE_MEMBERS = 2
MAX_DURATION_MINUTES = 24 * 60
MIN_PASSWORD_LENGTH = 14
MAX_PASSWORD_BYTES = 72                                # bcrypt cannot hash more than this
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'     # no I, O, 0 or 1
CODE_LENGTH = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_time_range(form):
    """Read the optional start and end times from a form.
    Returns (start, end, minutes), or (None, None, None) if missing or invalid."""
    start_text = form.get('started_at', '').strip()
    end_text = form.get('ended_at', '').strip()
    if not start_text or not end_text:
        return None, None, None

    try:
        start = datetime.fromisoformat(start_text.replace('Z', ''))
        end = datetime.fromisoformat(end_text.replace('Z', ''))
    except ValueError:
        flash("Couldn't read that time range, so it was left out.")
        return None, None, None

    minutes = round((end - start).total_seconds() / 60)
    if minutes < 1 or minutes > MAX_DURATION_MINUTES:
        flash("The time range has to be between 1 minute and 24 hours, so it was left out.")
        return None, None, None
    return start, end, minutes


# Photos

def save_photo(file):
    """Resize an uploaded image and save it as a JPEG. Returns the new filename, or None."""
    try:
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')
        img.thumbnail((1600, 1600))
    except Exception:
        return None

    filename = f"{uuid.uuid4().hex}.jpg"
    img.save(os.path.join(UPLOAD_FOLDER, filename), 'JPEG', quality=85)
    return filename


def delete_photo_file(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)


def add_photos(entry, files):
    """Attach uploaded images to an entry, up to MAX_PHOTOS in total."""
    skipped = 0
    for file in files:
        if not file or not file.filename:
            continue
        if len(entry.photos) >= MAX_PHOTOS:
            skipped += 1
            continue
        filename = save_photo(file)
        if filename:
            entry.photos.append(Photo(filename=filename))
        else:
            skipped += 1

    if skipped:
        flash(f"{skipped} photo(s) were skipped (not a valid image, or over the {MAX_PHOTOS}-photo limit).")


# Invite codes and couples

def generate_invite_code():
    while True:
        code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not Couple.query.filter(func.upper(Couple.invite_code) == code).first():
            return code


def find_couple(code):
    code = code.strip().upper()
    if not code:
        return None
    return Couple.query.filter(func.upper(Couple.invite_code) == code).first()


def couple_is_full(couple):
    return User.query.filter_by(couple_id=couple.id).count() >= MAX_COUPLE_MEMBERS


# Passwords

def password_error(password):
    """Returns a message describing the first rule the password breaks, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password.encode('utf-8')) > MAX_PASSWORD_BYTES:
        return f"Password is too long. Use {MAX_PASSWORD_BYTES} characters or fewer."
    if not any(c.isupper() for c in password):
        return "Password needs at least one uppercase letter."
    if not any(c.islower() for c in password):
        return "Password needs at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return "Password needs at least one number."
    return None


def hash_password(password):
    return bcrypt.generate_password_hash(password).decode('utf-8')


def password_matches(password):
    return bcrypt.check_password_hash(current_user.password_hash, password)


# Access control

def couple_required(view):
    """Send people who aren't in a relationship to Settings to join or start one."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.couple_id:
            flash("You're not in a relationship yet. Join one or start one in Settings.")
            return redirect(url_for('settings'))
        return view(*args, **kwargs)
    return wrapper


def get_own_entry(entry_id):
    """Fetch a date entry, refusing access to entries from other couples."""
    entry = DateEntry.query.get_or_404(entry_id)
    if entry.couple_id != current_user.couple_id:
        abort(403)
    return entry

@app.context_processor
def nav_state():
    """Lets every page know whether to show the dot on the Settings tab."""
    if not current_user.is_authenticated:
        return {'needs_partner': False}
    if not current_user.couple_id:
        return {'needs_partner': True}
    members = User.query.filter_by(couple_id=current_user.couple_id).count()
    return {'needs_partner': members < MAX_COUPLE_MEMBERS}


# ---------------------------------------------------------------------------
# Landing page and accounts
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('home_page'))
    return render_template('landing.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        invite_code = request.form.get('invite_code', '').strip()
        display_name = request.form['display_name'].strip()

        error = password_error(password)
        if error:
            flash(error)
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first():
            flash("That email is already registered.")
            return redirect(url_for('signup'))

        if invite_code:
            couple = find_couple(invite_code)
            if not couple:
                flash("That invite code doesn't match any account.")
                return redirect(url_for('signup'))
            if couple_is_full(couple):
                flash("That couple already has two members.")
                return redirect(url_for('signup'))
        else:
            couple = Couple(invite_code=generate_invite_code())
            db.session.add(couple)
            db.session.flush()

        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            couple_id=couple.id,
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('home_page'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()

        if user and bcrypt.check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('home_page'))

        flash("Invalid email or password.")
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------

@app.route('/home')
@login_required
@couple_required
def home_page():
    couple_id = current_user.couple_id
    active_session = ActiveSession.query.filter_by(couple_id=couple_id).first()
    couple = db.session.get(Couple, couple_id)
    member_count = User.query.filter_by(couple_id=couple_id).count()
    return render_template('home.html', active_session=active_session,
                           couple=couple, member_count=member_count)


@app.route('/clock-in', methods=['POST'])
@login_required
@couple_required
def clock_in():
    existing = ActiveSession.query.filter_by(couple_id=current_user.couple_id).first()
    if not existing:
        db.session.add(ActiveSession(couple_id=current_user.couple_id))
        db.session.commit()
    return redirect(url_for('home_page'))


@app.route('/clock-out', methods=['POST'])
@login_required
@couple_required
def clock_out():
    active = ActiveSession.query.filter_by(couple_id=current_user.couple_id).first()
    if not active:
        return redirect(url_for('home_page'))

    started_at = active.started_at
    ended_at = utc_now()
    minutes = max(1, round((ended_at - started_at).total_seconds() / 60))

    db.session.delete(active)
    db.session.commit()

    return redirect(url_for('log_date',
                            started_at=started_at.isoformat(),
                            ended_at=ended_at.isoformat(),
                            minutes=minutes))


@app.route('/clock-status')
@login_required
@couple_required
def clock_status():
    active = ActiveSession.query.filter_by(couple_id=current_user.couple_id).first()
    return jsonify(active=bool(active))


@app.route('/log-date', methods=['GET', 'POST'])
@login_required
@couple_required
def log_date():
    if request.method == 'POST':
        try:
            entry_date = datetime.strptime(request.form.get('local_date', ''), '%Y-%m-%d').date()
        except ValueError:
            entry_date = utc_now().date()

        entry = DateEntry(
            couple_id=current_user.couple_id,
            author_id=current_user.id,
            title=request.form['title'],
            date=entry_date,
            notes=request.form['notes'],
            duration_minutes=int(request.form['minutes']),
            started_at=datetime.fromisoformat(request.form['started_at']),
            ended_at=datetime.fromisoformat(request.form['ended_at']),
        )
        db.session.add(entry)
        add_photos(entry, request.files.getlist('photos'))
        db.session.commit()
        return redirect(url_for('archive'))

    return render_template('log_date.html',
                           started_at=request.args.get('started_at'),
                           ended_at=request.args.get('ended_at'),
                           minutes=request.args.get('minutes'))


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

@app.route('/archive')
@login_required
@couple_required
def archive():
    entries = (DateEntry.query
               .filter_by(couple_id=current_user.couple_id)
               .order_by(DateEntry.date.desc())
               .all())
    return render_template('archive.html', entries=entries)


@app.route('/add', methods=['GET', 'POST'])
@login_required
@couple_required
def add_date():
    if request.method == 'POST':
        start, end, minutes = parse_time_range(request.form)

        entry = DateEntry(
            couple_id=current_user.couple_id,
            author_id=current_user.id,
            title=request.form['title'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            notes=request.form['notes'],
            started_at=start,
            ended_at=end,
            duration_minutes=minutes,
        )
        db.session.add(entry)
        add_photos(entry, request.files.getlist('photos'))
        db.session.commit()
        return redirect(url_for('archive'))

    return render_template('add_date.html')


@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
@couple_required
def edit_date(entry_id):
    entry = get_own_entry(entry_id)

    if request.method == 'POST':
        entry.title = request.form['title']
        entry.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        entry.notes = request.form['notes']

        # Only touch the times if the form has some, or the entry already had some
        start, end, minutes = parse_time_range(request.form)
        if start or entry.started_at:
            entry.started_at, entry.ended_at, entry.duration_minutes = start, end, minutes

        remove_ids = {int(i) for i in request.form.getlist('remove_photo') if i.isdigit()}
        for photo in list(entry.photos):
            if photo.id in remove_ids:
                delete_photo_file(photo.filename)
                entry.photos.remove(photo)

        add_photos(entry, request.files.getlist('photos'))
        db.session.commit()
        return redirect(url_for('archive'))

    return render_template('edit_date.html', entry=entry)


@app.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
@couple_required
def delete_date(entry_id):
    entry = get_own_entry(entry_id)

    for photo in entry.photos:
        delete_photo_file(photo.filename)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('archive'))


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

@app.route('/gallery')
@login_required
@couple_required
def gallery():
    photos = (Photo.query
              .join(DateEntry, Photo.entry_id == DateEntry.id)
              .filter(DateEntry.couple_id == current_user.couple_id)
              .order_by(DateEntry.date.desc(), Photo.id.desc())
              .all())
    return render_template('gallery.html', photos=photos)


@app.route('/photo/<filename>')
@login_required
@couple_required
def serve_photo(filename):
    # Only serve the file if one of this couple's entries owns it
    (Photo.query
     .join(DateEntry, Photo.entry_id == DateEntry.id)
     .filter(Photo.filename == filename,
             DateEntry.couple_id == current_user.couple_id)
     .first_or_404())
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route('/settings')
@login_required
def settings():
    couple = db.session.get(Couple, current_user.couple_id) if current_user.couple_id else None
    partner = None
    if couple:
        partner = User.query.filter(
            User.couple_id == couple.id,
            User.id != current_user.id,
        ).first()
    return render_template('settings.html', couple=couple, partner=partner)


@app.route('/settings/update-name', methods=['POST'])
@login_required
def update_name():
    name = request.form['display_name'].strip()
    if name:
        current_user.display_name = name
        db.session.commit()
        flash("Name updated.")
    return redirect(url_for('settings'))


@app.route('/settings/leave', methods=['POST'])
@login_required
def leave_relationship():
    current_user.couple_id = None
    db.session.commit()
    flash("You've left the relationship.")
    return redirect(url_for('settings'))


@app.route('/settings/join', methods=['POST'])
@login_required
def join_relationship():
    couple = find_couple(request.form.get('invite_code', ''))
    if not couple:
        flash("Invalid invite code.")
    elif couple_is_full(couple):
        flash("That couple already has two members.")
    else:
        current_user.couple_id = couple.id
        db.session.commit()
        flash("Joined.")
    return redirect(url_for('settings'))


@app.route('/settings/new-code', methods=['POST'])
@login_required
def new_code():
    couple = Couple(invite_code=generate_invite_code())
    db.session.add(couple)
    db.session.flush()
    current_user.couple_id = couple.id
    db.session.commit()
    return redirect(url_for('settings'))


@app.route('/settings/change-email', methods=['POST'])
@login_required
def change_email():
    new_email = request.form['email'].strip()

    if not password_matches(request.form['password']):
        flash("Incorrect password.")
    elif User.query.filter(User.email == new_email, User.id != current_user.id).first():
        flash("That email is already in use.")
    else:
        current_user.email = new_email
        db.session.commit()
        flash("Email updated.")
    return redirect(url_for('settings'))


@app.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    new_password = request.form['new_password']
    error = password_error(new_password)

    if not password_matches(request.form['current_password']):
        flash("Current password is incorrect.")
    elif error:
        flash(error)
    elif new_password != request.form['confirm_password']:
        flash("New passwords don't match.")
    else:
        current_user.password_hash = hash_password(new_password)
        db.session.commit()
        flash("Password updated.")
    return redirect(url_for('settings'))


@app.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    if not password_matches(request.form['password']):
        flash("Incorrect password.")
        return redirect(url_for('settings'))

    user = current_user._get_current_object()
    couple_id = user.couple_id
    last_member = bool(couple_id) and User.query.filter_by(couple_id=couple_id).count() == 1

    logout_user()

    # Entries this person added stay with the couple, just without an author
    DateEntry.query.filter_by(author_id=user.id).update({'author_id': None})

    if last_member:
        # Nobody is left, so remove the couple's dates, photos and timer too
        for entry in DateEntry.query.filter_by(couple_id=couple_id).all():
            for photo in entry.photos:
                delete_photo_file(photo.filename)
            db.session.delete(entry)
        ActiveSession.query.filter_by(couple_id=couple_id).delete()

    db.session.delete(user)
    if last_member:
        db.session.delete(db.session.get(Couple, couple_id))
    db.session.commit()

    flash("Your account has been deleted.")
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403, message="You don't have access to that."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, message="That page doesn't exist."), 404


@app.errorhandler(413)
def too_large(e):
    flash("That upload is too large. The limit is 100 MB per save.")
    return redirect(request.referrer or url_for('home'))


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template('error.html', code=500, message="Something went wrong on our end."), 500


@app.errorhandler(CSRFError)
def csrf_error(e):
    flash("Your session expired. Please try again.")
    return redirect(request.referrer or url_for('home'))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)