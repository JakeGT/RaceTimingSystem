# Installation Guide

## Basic Installation Steps

Clone the Repository

```bash
git clone https://github.com/UoE-ECMM427-202425/Running.git
cd Running
```

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

## Django Setup

```bash
cd running
pip install -r requirements.txt
```
### 1. Set Up the Database

For development, this system uses SQLite by default. No additional setup is required for SQLite. However, if you're
using a different database (e.g., PostgreSQL or MySQL), you'll need to configure your database settings in the
`settings.py` file located in the project directory.

```bash
python manage.py migrate
```

### 2. Create a Superuser

To manage the system through the Django admin interface, create a superuser account:

```bash
python manage.py createsuperuser
```

Then follow the instructions to create a new superuser

### 3. Run the Development Server

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

## Computer Vision Installation

### Install Requirements

The bib detector requires `Python 3.13` and the requirements was built with `Python 3.13.3`

```bash
cd bib-detector
pip install -r requirements.txt
```

### Hardware Accelerators
CUDA: 
To use CUDA acceleration, install PyTorch with CUDA. For more details, refer to the [PyTorch Documentation](https://pytorch.org/get-started/locally/).

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```


Other accelerators (ROCm, MPS): 
The bib detection model was built on YOLOv11 with PyTorch. Any accelerator with PyTorch support should be supported in this application as well.


**IMPORTANT: It is recommended to use the bib detector with hardware acceleration as the accuracy of the bib tracker will decrease with lower framerates.**

### Install Droidcam to Use Phone Camera

#### Android
Connect over USB:
[Google Play Store](https://play.google.com/store/apps/details?id=com.dev47apps.obsdroidcam)

Enable USB Debugging:

1. Open settings
2. Go to about device
3. Tap build number 7 times to unlock Developer Options
4. Then go back and go to Developer Options
5. Toggle USB debugging

For more details refer to: [Android Developers](https://developer.android.com/studio/debug/dev-options)


## Third party integrations installations
### Setting Up OAuth for Social Login

The system supports social login via **Google**, **GitHub**, and **Facebook**, allowing users to log in without creating
a new password. Instead, they can use accounts they already have, which improves both user experience and security.

This guide explains how to set up OAuth credentials for each provider, how to generate a Google App Password (for
optional email integration), and how to securely store these credentials in your `.env` file.


#### Google OAuth Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or choose an existing one.
3. Navigate to **APIs & Services > Credentials**.
4. Click **Create Credentials > OAuth Client ID**.
5. Choose **Web Application** and provide the following:
   - **Authorised redirect URIs** (e.g., `http://127.0.0.1:8000/accounts/google/login/callback/`).
6. Once created, note down your:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`

##### Generating a Google App Password (for email integration)

If your Google account has two-factor authentication enabled, you'll need an App Password to allow Django to send emails using your account:

1. Visit your [Google Account Security Settings](https://myaccount.google.com/security).
2. Under **Signing in to Google**, select **App Passwords**.
3. Choose the app (e.g., "Mail") and the device (e.g., "Django"), then click **Generate**.
4. Add the password that is shown to the `.env` file for `EMAIL_HOST_PASSWORD`.

#### GitHub OAuth Setup

1. Go to [GitHub Developer Settings](https://github.com/settings/developers).
2. Click **New OAuth App**.
3. Fill out the form:
   - **Application name**: your application's name.
   - **Homepage URL**: e.g., `http://127.0.0.1:8000/`.
   - **Authorisation callback URL**:  
     `http://127.0.0.1:8000/accounts/github/login/callback/`.
4. After saving, you'll receive:
   - `GITHUB_CLIENT_ID`
   - `GITHUB_CLIENT_SECRET`

---

#### Facebook OAuth Setup

1. Go to the [Facebook Developers Console](https://developers.facebook.com/).
2. Create a new app (select the "Consumer" app type).
3. In the left menu, go to **Facebook Login > Settings** and enter:
   - **Valid OAuth Redirect URIs**:  
     `http://127.0.0.1:8000/accounts/facebook/login/callback/`.
4. Go to **Settings > Basic** to find your:
   - `FACEBOOK_APP_ID`
   - `FACEBOOK_APP_SECRET`

Note: For production use, your Facebook app may need to be reviewed and made live before it can be used by others.

#### Adding Secrets to the `.env` File

After you’ve collected your credentials, add them to the `.env` file located in `running/running/`. This file allows
Django to access your secret keys securely without exposing them in source code.

