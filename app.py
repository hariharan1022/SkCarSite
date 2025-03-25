import os
import sqlite3
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# File Upload Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Inject current year into all templates
@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year}

# Database helper functions
def get_db():
    if 'db' not in g:
        # Make sure to use the absolute path to the database file
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        # Enable foreign keys
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Authentication routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Form validation
        error = None
        if not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        
        # Check if username or email already exists
        if error is None:
            db = get_db()
            try:
                db.execute(
                    'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                    (username, email, generate_password_hash(password))
                )
                db.commit()
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
            except db.IntegrityError:
                error = f"User {username} or email {email} is already registered."
                
        flash(error, 'danger')
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'
            
        if error is None:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('You have successfully logged in!', 'success')
            return redirect(url_for('index'))
            
        flash(error, 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Load logged in user before each request
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()

# Car listing routes
@app.route('/')
def index():
    db = get_db()
    try:
        # Check if cars table exists
        db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cars'").fetchone()
        
        # Proceed with query if table exists
        cars = db.execute(
            'SELECT c.id, c.title, c.brand, c.model, c.year, c.price, c.mileage, c.description, c.image_url, '
            'c.created_at, u.username '
            'FROM cars c JOIN users u ON c.user_id = u.id '
            'ORDER BY c.created_at DESC'
        ).fetchall()
        
        # Get unique brands and years for filtering
        brands = db.execute('SELECT DISTINCT brand FROM cars ORDER BY brand').fetchall()
        years = db.execute('SELECT DISTINCT year FROM cars ORDER BY year DESC').fetchall()
    except Exception as e:
        # Log the error
        app.logger.error(f"Database error: {str(e)}")
        # Return empty lists if there's an error
        cars = []
        brands = []
        years = []
    
    return render_template('index.html', cars=cars, brands=brands, years=years)

@app.route('/car/<int:car_id>')
def car_detail(car_id):
    db = get_db()
    try:
        car = db.execute(
            'SELECT c.*, u.username FROM cars c JOIN users u ON c.user_id = u.id WHERE c.id = ?',
            (car_id,)
        ).fetchone()
        
        if car is None:
            flash('Car not found!', 'danger')
            return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Database error in car_detail: {str(e)}")
        flash('An error occurred while retrieving car details.', 'danger')
        return redirect(url_for('index'))
        
    return render_template('car_detail.html', car=car)

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if g.user is None:
        flash('You need to login to sell a car.', 'warning')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form['title']
        brand = request.form['brand']
        model = request.form['model']
        year = request.form['year']
        price = request.form['price']
        mileage = request.form['mileage']
        description = request.form['description']
        
        # Form validation
        error = None
        if not title:
            error = 'Title is required.'
        elif not brand:
            error = 'Brand is required.'
        elif not model:
            error = 'Model is required.'
        elif not year:
            error = 'Year is required.'
        elif not price:
            error = 'Price is required.'
        
        # Handle file upload
        image_url = None
        if 'car_image' in request.files:
            file = request.files['car_image']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    # Generate a secure filename with UUID to avoid collisions
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    # Save the file
                    file.save(file_path)
                    
                    # Set the image URL to the path relative to static folder
                    image_url = f"/static/uploads/{unique_filename}"
                else:
                    error = 'Invalid file type. Allowed types are: png, jpg, jpeg, gif.'
            
        if error is None:
            db = get_db()
            db.execute(
                'INSERT INTO cars (title, brand, model, year, price, mileage, description, image_url, user_id, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (title, brand, model, year, price, mileage, description, image_url, g.user['id'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            db.commit()
            flash('Your car listing has been created!', 'success')
            return redirect(url_for('index'))
            
        flash(error, 'danger')
            
    return render_template('sell.html')

@app.route('/my-listings')
def my_listings():
    if g.user is None:
        flash('You need to login to view your listings.', 'warning')
        return redirect(url_for('login'))
        
    db = get_db()
    try:
        cars = db.execute(
            'SELECT * FROM cars WHERE user_id = ? ORDER BY created_at DESC',
            (g.user['id'],)
        ).fetchall()
    except Exception as e:
        app.logger.error(f"Database error in my_listings: {str(e)}")
        flash('An error occurred while retrieving your listings.', 'danger')
        cars = []
    
    return render_template('my_listings.html', cars=cars)

@app.route('/edit-car/<int:car_id>', methods=['GET', 'POST'])
def edit_car(car_id):
    if g.user is None:
        flash('You need to login to edit a car listing.', 'warning')
        return redirect(url_for('login'))
        
    db = get_db()
    car = db.execute('SELECT * FROM cars WHERE id = ?', (car_id,)).fetchone()
    
    if car is None:
        flash('Car not found!', 'danger')
        return redirect(url_for('my_listings'))
        
    if car['user_id'] != g.user['id']:
        flash('You can only edit your own listings!', 'danger')
        return redirect(url_for('my_listings'))
        
    if request.method == 'POST':
        title = request.form['title']
        brand = request.form['brand']
        model = request.form['model']
        year = request.form['year']
        price = request.form['price']
        mileage = request.form['mileage']
        description = request.form['description']
        
        # Keep the existing image URL by default
        image_url = car['image_url']
        
        # Handle file upload if a new image is provided
        if 'car_image' in request.files:
            file = request.files['car_image']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    # Generate a secure filename with UUID to avoid collisions
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    # Save the file
                    file.save(file_path)
                    
                    # Set the image URL to the path relative to static folder
                    image_url = f"/static/uploads/{unique_filename}"
                else:
                    error = 'Invalid file type. Allowed types are: png, jpg, jpeg, gif.'
        
        # Form validation
        error = None
        if not title:
            error = 'Title is required.'
        elif not brand:
            error = 'Brand is required.'
        elif not model:
            error = 'Model is required.'
        elif not year:
            error = 'Year is required.'
        elif not price:
            error = 'Price is required.'
            
        if error is None:
            db.execute(
                'UPDATE cars SET title = ?, brand = ?, model = ?, year = ?, price = ?, '
                'mileage = ?, description = ?, image_url = ? WHERE id = ?',
                (title, brand, model, year, price, mileage, description, image_url, car_id)
            )
            db.commit()
            flash('Your car listing has been updated!', 'success')
            return redirect(url_for('my_listings'))
            
        flash(error, 'danger')
    
    return render_template('sell.html', car=car, edit=True)

@app.route('/delete-car/<int:car_id>', methods=['POST'])
def delete_car(car_id):
    if g.user is None:
        flash('You need to login to delete a car listing.', 'warning')
        return redirect(url_for('login'))
        
    db = get_db()
    car = db.execute('SELECT * FROM cars WHERE id = ?', (car_id,)).fetchone()
    
    if car is None:
        flash('Car not found!', 'danger')
        return redirect(url_for('my_listings'))
        
    if car['user_id'] != g.user['id']:
        flash('You can only delete your own listings!', 'danger')
        return redirect(url_for('my_listings'))
        
    db.execute('DELETE FROM cars WHERE id = ?', (car_id,))
    db.commit()
    flash('Your car listing has been deleted!', 'success')
    return redirect(url_for('my_listings'))

@app.route('/search')
def search():
    query = request.args.get('query', '')
    brand = request.args.get('brand', '')
    year = request.args.get('year', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    
    db = get_db()
    
    try:
        # Build the SQL query dynamically
        sql = 'SELECT c.id, c.title, c.brand, c.model, c.year, c.price, c.mileage, c.description, c.image_url, c.created_at, u.username FROM cars c JOIN users u ON c.user_id = u.id WHERE 1=1'
        params = []
        
        if query:
            sql += ' AND (c.title LIKE ? OR c.brand LIKE ? OR c.model LIKE ? OR c.description LIKE ?)'
            search_term = f'%{query}%'
            params.extend([search_term, search_term, search_term, search_term])
        
        if brand:
            sql += ' AND c.brand = ?'
            params.append(brand)
        
        if year:
            sql += ' AND c.year = ?'
            params.append(year)
        
        if min_price:
            sql += ' AND c.price >= ?'
            params.append(min_price)
        
        if max_price:
            sql += ' AND c.price <= ?'
            params.append(max_price)
        
        sql += ' ORDER BY c.created_at DESC'
        
        cars = db.execute(sql, params).fetchall()
        
        # Get filter options
        brands = db.execute('SELECT DISTINCT brand FROM cars ORDER BY brand').fetchall()
        years = db.execute('SELECT DISTINCT year FROM cars ORDER BY year DESC').fetchall()
    except Exception as e:
        app.logger.error(f"Database error in search: {str(e)}")
        flash('An error occurred while searching. Please try again.', 'danger')
        cars = []
        brands = []
        years = []
    
    return render_template('index.html', cars=cars, brands=brands, years=years, 
                          search_query=query, selected_brand=brand, selected_year=year,
                          min_price=min_price, max_price=max_price)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
