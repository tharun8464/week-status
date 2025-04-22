import os
from flask import Flask
from models import db
from flask_login import LoginManager

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", os.getenv('FLASK_SECRET_KEY', 'your-secret-key'))
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
    }
    
    # Initialize database
    db.init_app(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    
    # Import models
    from models import Employee
    
    @login_manager.user_loader
    def load_user(user_id):
        return Employee.query.get(user_id)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Import and register routes
    from routes import bp
    app.register_blueprint(bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)