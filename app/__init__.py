from flask import Flask
from config import config, Config
from extensions import db, migrate, csrf
import os


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')
    
    app.config.from_object(config.get(config_name, config['default']))
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.get_database_uri()
    
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Ensure models are registered with SQLAlchemy metadata
    from app import models  # noqa: F401
    
    # Register blueprints
    from app.auth.routes import auth_bp
    from app.attendance.routes import attendance_bp
    from app.reports.routes import reports_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    
    # Context processors
    @app.context_processor
    def inject_globals():
        from app.services.datetime_service import now_nepal, format_bs_date, format_time_24, today_nepal
        return {
            'now_nepal': now_nepal,
            'format_bs_date': format_bs_date,
            'format_time_24': format_time_24,
            'today_nepal': today_nepal
        }
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('errors/500.html'), 500
    
    # CLI commands
    @app.cli.command('init-admin')
    def init_admin():
        """Create the initial admin user from environment variables."""
        from app.models import User
        username = app.config.get('ADMIN_USERNAME') or os.environ.get('ADMIN_USERNAME')
        password = app.config.get('ADMIN_PASSWORD') or os.environ.get('ADMIN_PASSWORD')
        
        if not username or not password:
            print('Error: ADMIN_USERNAME and ADMIN_PASSWORD must be set in environment.')
            return
        
        with app.app_context():
            existing = User.query.filter_by(username=username).first()
            if existing:
                print(f'User "{username}" already exists.')
                return
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            print(f'Admin user "{username}" created successfully.')
    
    @app.cli.command('init-db')
    def init_db():
        """Create all tables."""
        with app.app_context():
            db.create_all()
            print('Database tables created.')
    

    @app.route('/offline')
    def offline():
        from flask import render_template
        return render_template('offline.html')


    @app.route('/favicon.ico')
    def favicon():
        from flask import send_from_directory
        import os
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'icons'),
            'favicon.svg',
            mimetype='image/svg+xml'
        )

    return app
