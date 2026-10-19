from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
from extensions import db, csrf
from app.models import User
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return db.session.get(User, user_id)
    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('attendance.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Invalid username or password.', 'error')
            return render_template('login.html')
        
        session.clear()
        session['user_id'] = user.id
        session['username'] = user.username
        session.permanent = True
        flash(f'Welcome back, {user.username}.', 'success')
        return redirect(url_for('attendance.dashboard'))
    
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_current_user()
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('settings.html', user=user)
        
        if len(new_password) < 8:
            flash('New password must be at least 8 characters.', 'error')
            return render_template('settings.html', user=user)
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('settings.html', user=user)
        
        user.set_password(new_password)
        db.session.commit()
        flash('Password updated successfully.', 'success')
        return redirect(url_for('auth.settings'))
    
    return render_template('settings.html', user=user)
