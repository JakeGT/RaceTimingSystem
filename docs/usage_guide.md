# Usage Guide – First Steps

## Overview
The following guide covers the basic usage of the Automated Race Timing System. This will help you get started quickly
and complete a simple task to verify that the system installation works properly. 

### 1. Logging into the System

To access the system, follow these steps:

- Open a browser and navigate to the URL where the system is hosted, e.g., `http://127.0.0.1:8000/` for local
development.
- On the landing page, you will see two options: **Login** and **Register**.
  - If you already have an account, click **Login** and enter your credentials (username and password).
  - If you're a new user, click **Register** to create an account. After registration, you will be automatically logged
  in.

#### Screenshot of Login Page:

![Login Page](path/to/login_page_screenshot.png)

### 2. Uploading Race Data (JSON)

After logging in, you can upload race data in JSON format. This is an essential step for setting up race results and timings.

- Navigate to the **Upload JSON** page by going to: `Race → [Race ID] → Upload`.
- On this page, you can select the JSON file that contains race data and click **Upload**.

#### Screenshot of Upload JSON Page:

![Upload JSON](path/to/upload_json_screenshot.png)

### 3. Managing Participants

As an organiser or admin, you can manage participants' information from the **Manage Participants** page.

- Go to `Organiser Dashboard → Manage Participants`.
- On this page, you can view, edit, and delete participant records.

### 4. Viewing Race Results

After uploading race data, you can view the results on the **Race Details** page.

- Navigate to `Race → [Race ID] → Race Details`.
- This page will show the race leaderboard and the results for each participant.

#### Screenshot of Race Details Page:

![Race Results](path/to/race_results_screenshot.png)