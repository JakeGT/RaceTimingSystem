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


## third party integrations installations
TODO - discuss how  to set up facebook, github and google sign in. Discuss how to generate google app passwords, and
putting both in the .env
