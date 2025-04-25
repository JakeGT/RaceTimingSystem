# Database Schema

## 1. Participants Table
| Field Name   | Data Type    | Description                                                          |
|--------------|--------------|----------------------------------------------------------------------|
| id           | Integer (PK) | Primary key for each participant                                     |
| user         | Integer (FK) | Foreign key linking to the user model (can be blank)                 |
| race         | Integer (FK) | Foreign key linking to the Race table                                |
| name         | Varchar(100) | Name of the participant                                              |
| race_number  | Varchar(10)  | Unique race number or bib number                                     |
| age          | Integer      | Age of the participant                                               |
| gender       | Varchar(10)  | Gender of the participant (choices: "Male", "Female", "Other")       |
| club_name    | Varchar(100) | Name of the club the participant belongs to (optional)               |
| team_name    | Varchar(100) | Name of the team the participant belongs to (optional)               |
| age_category | Varchar(50)  | Age category of the participant (e.g., "Veteran", "Elite", "Others") |
| status       | Varchar(10)  | Status of the participant (choices: "Pending", "Approved", "Denied") |

## 2. RaceResults Table
| Field Name     | Data Type    | Description                                                                         |
|----------------|--------------|-------------------------------------------------------------------------------------|
| id             | Integer (PK) | Primary key for each race result                                                    |
| participant_id | Integer (FK) | Foreign key linking to the Participants table (a participant can have many results) |
| race_id        | Integer (FK) | Foreign key linking to the Races table                                              |
| total_time     | Varchar(10)  | Total race time                                                                     |

## 3. Races Table
| Field Name             | Data Type    | Description                                                  |
|------------------------|--------------|--------------------------------------------------------------|
| id                     | Integer (PK) | Primary key for each race                                    |
| name                   | Varchar(255) | Name of the race                                             |
| date                   | Date         | Date of the race                                             |
| start_time             | Time         | Start time of the race                                       |
| race_category          | Integer (FK) | Foreign key linking to the RaceCategory table (can be null)  |
| participant_categories | Many-to-Many | Many-to-many relationship with the ParticipantCategory table |
| organiser              | Many-to-Many | Many-to-many relationship with the User model (can be blank) |
| participants           | Many-to-Many | Many-to-many relationship with the Participant model         |
| is_completed           | Boolean      | Flag indicating if the race has been completed               |
| address                | Varchar(255) | Address of the race (optional)                               |
| latitude               | Float        | Latitude of the race location (optional)                     |
| longitude              | Float        | Longitude of the race location (optional)                    |
| organiser_website      | URLField     | Website URL of the organiser (optional)                      |
| social_twitter         | URLField     | Twitter URL of the organiser (optional)                      |
| social_instagram       | URLField     | Instagram URL of the organiser (optional)                    |
| social_facebook        | URLField     | Facebook URL of the organiser (optional)                     |
| token                  | Varchar(100) | Unique token for race (optional)                             |
| stream_url             | URLField     | URL for live stream (YouTube, Twitch, etc.)                  |

## 4. RaceCategory Table
| Field Name | Data Type    | Description                                               |
|------------|--------------|-----------------------------------------------------------|
| id         | Integer (PK) | Primary key for each race category                        |
| name       | Varchar(100) | Name of the race category (e.g., "5k", "10k", "Marathon") |

## 5. ParticipantCategory Table
| Field Name | Data Type    | Description                                                  |
|------------|--------------|--------------------------------------------------------------|
| id         | Integer (PK) | Primary key for each participant category                    |
| name       | Varchar(100) | Name of the participant category (e.g., "Veteran", "Junior") |

## 6. Profile Table
| Field Name          | Data Type    | Description                                |
|---------------------|--------------|--------------------------------------------|
| id                  | Integer (PK) | Primary key for the profile                |
| user                | Integer (FK) | Foreign key linking to the User model      |
| notify_race_updates | Boolean      | Flag to notify the user about race updates |

## 7. OrganiserApplication Table
| Field Name | Data Type    | Description                                                          |
|------------|--------------|----------------------------------------------------------------------|
| id         | Integer (PK) | Primary key for each organiser application                           |
| user       | Integer (FK) | Foreign key linking to the User model                                |
| race       | Integer (FK) | Foreign key linking to the Race table                                |
| message    | Text         | Message from the user applying to become an organiser                |
| status     | Varchar(10)  | Status of the application (choices: "Pending", "Approved", "Denied") |
| created_at | DateTime     | Timestamp of when the application was created                        |
