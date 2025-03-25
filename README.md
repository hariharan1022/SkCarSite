# SK Cars - Car Marketplace Website

A Flask-based car marketplace website where users can list and browse cars for sale.

## Features

- User registration and authentication
- Create, view, edit, and delete car listings
- Upload car images directly
- Search and filter car listings by various criteria
- Responsive design using Bootstrap
- Prices displayed in Indian Rupees (₹)
- Mileage displayed in kilometers (km)

## Technologies Used

- Flask (Python web framework)
- SQLite (Database)
- Flask-SQLAlchemy (ORM)
- Flask-Login (User authentication)
- Bootstrap (Frontend styling)
- Flask-WTF (Form handling)
- Werkzeug (Password hashing and secure filename handling)

## Setup Instructions

### Local Development

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python main.py`
4. Visit `http://localhost:5000` in your browser

### Database Configuration

The application uses SQLite by default. For production, consider using PostgreSQL or MySQL.

## Project Structure

- `main.py`: Entry point for the application
- `app.py`: Contains all the route definitions and application logic
- `database.py`: Database models and configuration
- `templates/`: HTML templates
- `static/`: Static files (CSS, JS, images)
- `static/uploads/`: Directory for user-uploaded car images

## Credits

Developed as a demonstration project.