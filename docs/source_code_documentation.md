## Important API Endpoints

These are the primary endpoints of the application. Most are page-rendering views, while some perform data uploads or
POST operations.

| Endpoint                             | Method     | Description                                             |
|--------------------------------------|------------|---------------------------------------------------------|
| `/race/<race_id>/upload`             | `POST`     | Uploads race result data (JSON) for the specified race. |
| `/dashboard/`                        | `GET`      | Displays the race dashboard.                            |
| `/race-config/`                      | `GET`      | Allows configuration of race parameters.                |
| `/upload-participants/`              | `POST`     | Uploads a list of participants for a race.              |
| `/upload-results/`                   | `POST`     | Uploads race results data.                              |
| `/register/`                         | `GET/POST` | Registers a new user.                                   |
| `/login/`                            | `GET/POST` | Logs in an existing user.                               |
| `/password_reset/`                   | `GET/POST` | Initiates password reset process.                       |
| `/race/<race_id>/`                   | `GET`      | Shows race detail and leaderboard.                      |
| `/race/<race_id>/adjust_start_time/` | `POST`     | Adjusts start time of race for time calculations.       |
| `/upload-image/`                     | `POST`     | Uploads an image (e.g., for manual bib recognition).    |
| `/race/<race_id>/delete/`            | `POST`     | Deletes a race as an organiser.                         |
| `/organiser/apply/`                  | `POST`     | Allows users to apply as race organisers.               |
| `/verify-2fa/`                       | `POST`     | Endpoint for verifying two-factor authentication.       |

Most endpoints are protected and require authentication.

## SPDX License Identifier
TODO
