# Maintenance

To ensure the continued reliability and security of the Automatic Race Timing System, regular maintenance tasks must be
performed. Below are the recommended maintenance practices.

The bib detector client is self-contained and does not require regular maintenance.

## 1. **Regular Backups**

It's crucial to back up both the application data and database to prevent data loss.

- **Database Backup**: Regularly back up the SQLite database (or any other database used). this can be automated by 
setting up cron jobs or using database management tools.
  - For SQLite, simply copy the `.db` file to a backup location.
  - For PostgreSQL or MySQL, use the database's built-in backup tools (`pg_dump` for PostgreSQL or `mysqldump` for
  MySQL).

- **File Backup**: If the system is being used to store large files (e.g., high number of race images), ensure you back 
up the media files in `media/` directory regularly.

### 2. **User Management**

To keep the system secure, manage users regularly:
  
- **Adding Users**: Admins can add users via the Django admin interface by navigating to the **Users** section. You can
assign roles such as "Admin," "Organiser," or "Participant."
  
- **Removing Users**: If a user no longer requires access, delete their account via the admin panel.

- **Password Resets**: Allow users to reset their passwords securely. This can be done via the **Password Reset** page,
in order for this to, google app passwords should be configured in the .env file. For more details see 
[Usage_guide](usage_guide.md).

### 3. **System and Software Updates**

To ensure the system remains secure, it's important to apply security patches and updates regularly:

- **Django & Python Libraries**: Periodically check for updates to Django and other Python dependencies by running the
following command: 
```
  pip list --outdated
  pip install --upgrade <library_name>
```

- **Operating System Updates**: Keep your operating system updated with the latest security patches.

### 4. **Database Maintenance**

Perform regular maintenance on the database to ensure optimal performance:

- **Optimise Database**: Run optimisation commands periodically to clean up unused data and indexes. For SQLite, this 
can be done with the `VACUUM` command:
  
```
  python manage.py dbshell
  VACUUM;
```

- **Database Migrations**: Keep track of migrations for any changes to the database schema. Run migrations whenever you
add new models or make changes to existing ones:

```
  python manage.py makemigrations
  python manage.py migrate
```

### 5. **Log Monitoring**

Monitor the application logs regularly to identify any issues or abnormal behavior.

- Logs can be accessed in the `logs/` directory

- Regularly check logs for errors related to database connectivity, user authentication, and file uploads.

### 6. **Security Practices**

Ensure your system is secure by regularly reviewing security practices:

- **Secure Configuration**: Ensure that the `SECRET_KEY` cannot be found in `settings.py` and only in the .env

- **Two-Factor Authentication (2FA)**: For extra security accounts should enable 2-factor authentication via the profile 
page
