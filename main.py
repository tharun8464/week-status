import os
import uuid
from flask import Flask
from models import db
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    login_manager.login_view = 'main.index'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    
    # Import models
    from models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
    
    # Create tables and add admin if needed
    with app.app_context():
        db.create_all()
        create_admin_user()
    
    # Import and register routes
    from routes import bp as main_bp
    app.register_blueprint(main_bp)
    
    # Import and register admin routes
    from admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Register error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500
    
    return app

def create_admin_user():
    """Create admin user if not exists"""
    from models import User
    
    admin_email = 'admin@sbscorp.com'
    admin = User.query.filter_by(email=admin_email).first()
    
    if not admin:
        logger.info("Creating admin user...")
        hashed_password = generate_password_hash('admin123')
        admin_user = User(
            id=str(uuid.uuid4()),
            name='SBS Admin',
            email=admin_email,
            password=hashed_password,
            role='admin'
        )
        db.session.add(admin_user)
        try:
            db.session.commit()
            logger.info("Admin user created successfully!")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating admin user: {str(e)}")
    else:
        logger.info("Admin user already exists.")

app = create_app()

from flask import render_template

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)