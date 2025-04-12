## Development Environment and its Requirements

This section provides a complete guide for setting up the development environment for the race timing system.
It covers the backend (Django server), the computer vision module, and how to run and extend the full pipeline locally.

### Prerequisites

Before starting, ensure the following are installed on your development machine:

- **Python 3.10+**
- **pip** (Python package manager)
- **Git**
- **virtualenv** *(recommended)*
- **GitHub account** (to access and clone the repo)
- **A webcam or access to video footage** 

### 1. Clone the Repository

```bash
git clone https://github.com/UoE-ECMM427-202425/Running.git
cd Running
```

### 2. Set Up Python Virtual Environment

```bash
python3 -m venv venv
venv\Scripts\activate  # On Mac: source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:

- asgiref
- cachetools
- certifi
- cffi
- charset-normalizer
- cryptography
- defusedxml
- Django
- django-environ
- dotenv
- environ
- google-auth
- idna
- oauthlib
- pillow
- pyasn1
- pyasn1_modules
- pycparser
- PyJWT
- pyotp
- python-dotenv
- python3-openid
- qrcode
- requests
- requests-oauthlib
- rsa
- social-auth-app-django
- social-auth-core
- sqlparse
- urllib3

### 4. Set Up and Run the Django Server

Apply migrations and run the server locally:

```bash
python manage.py migrate
python manage.py runserver
```

Access the local site at:  
**http://127.0.0.1:8000**

### 5. Run the Computer Vision Pipeline

TODO


### 6. Frontend Assets

- Static files are managed through Django's `collectstatic` command.
- Bootstrap is used for styling (via CDN).
- You can extend templates in `templates/` to modify UI.

### 7. Testing

Unit tests can be run with:

```bash
python manage.py test
```

Further tests can be run using:

Installing Playwright:
1. **Install Node.js:** Make sure you have Node.js installed. If not, download and install it from the official Node.js website.
2. **Install Playwright:** Run the following command in your terminal to install Playwright and its dependencies:
   
```bash
npm install playwright
```

```bash
npx playwright test
```

To see the complete results run
```bash
npx playwright show-report
```

After completing the steps above, your environment will be fully ready for extending, debugging, or testing the system.
