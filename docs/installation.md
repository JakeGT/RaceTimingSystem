# Installation Guide

## Basic Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/UoE-ECMM427-202425/Running.git
cd Running
```

### 2. Create a Virtual Environment

For **Linux/macOS**:

```bash
python3 -m venv venv
source venv/bin/activate
```

For **Windows**:

```bash
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install Required Python Packages

```bash
pip install -r requirements.txt
```

### 4. Set Up the Database

For development, this system uses SQLite by default. No additional setup is required for SQLite. However, if you're
using a different database (e.g., PostgreSQL or MySQL), you'll need to configure your database settings in the
`settings.py` file located in the project directory.

```bash
python manage.py migrate
```

### 5. Create a Superuser

To manage the system through the Django admin interface, create a superuser account:

```bash
python manage.py createsuperuser
```

Then follow the instructions to create a new superuser

### 6. Run the Development Server

```bash
python manage.py runserver
```

You can access the system by navigating to `http://127.0.0.1:8000/` in your browser.

## Additional Configuration

### Configuring the Database

If you want to use a different database (e.g., PostgreSQL or MySQL), you need to modify the database settings in the
`settings.py` file. Below is an example for PostgreSQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'database_name',
        'USER': 'database_user',
        'PASSWORD': 'database_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

After modifying the database configuration, run the migrations again:

```bash
python manage.py migrate
```

## Environment Variables

Certain environment variables are needed in the production environment, such as `SECRET_KEY`, `EMAIL_HOST_USER`,
and database credentials. These this should be set in a `.env` file within the inner running directory. An example
.env file can be found within the examples directory, simply fill this out with your data/secrets. These secrets will
not be uploaded to the github repository and will not be accessible to people via the frontend.

## Computer vision installation
TODO - discuss how to install the cv models

## third party integrations installations
TODO - discuss how  to set up facebook, github and google sign in. Discuss how to generate google app passwords, and
putting both in the .env
