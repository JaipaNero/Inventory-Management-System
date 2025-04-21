# Inventory Management System

A secure and modular Flask application for inventory management with authentication, role-based access control, and comprehensive security features.

## Project Overview

This inventory management system helps businesses track products, manage stock levels, handle transactions, and generate reports. The application follows modern security practices and is built with a modular structure for maintainability and scalability.

## Requirements

- Python 3.8 or higher
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Project Structure

- `/app`: Main application package
  - `/blueprints`: Feature-specific modules
    - `/auth`: Authentication functionality
    - `/inventory`: Inventory management
    - `/main`: Dashboard and general pages
    - `/admin`: Administrative functions
  - `/static`: Static assets (CSS, JS, images)
  - `/templates`: HTML templates
- `/instance`: Instance-specific configuration
- `/logs`: Application logs

## Security Features

- CSRF protection via Flask-WTF
- Argon2 password hashing
- Rate limiting with Flask-Limiter
- Secure HTTP headers
- Secure cookie settings
- Error handling and logging

## Running the Application

```
flask run
```

## Development Notes

- The application uses Flask Blueprints for modular organization
- Security settings like HSTS and CSP are prepared for HTTPS deployment
- Flask-Login handles user session management