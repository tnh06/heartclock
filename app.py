from flask import Flask
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heartclock.db'
app.config['SECRET_KEY'] = 'dev-secret-change-later'

db.init_app(app)

@app.route('/')
def home():
    return "Heartclock is alive"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)