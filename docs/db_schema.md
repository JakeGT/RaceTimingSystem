# Database Schema

### 1. Participants Table

| Field Name  | Data Type    | Description                                                      |
|-------------|--------------|------------------------------------------------------------------|
| id          | Integer (PK) | Primary key for each participant                                 |
| name        | Varchar(20)  | Name of the participant                                          |
| race_number | Varchar(10)  | Unique race number or bib number                                 |
| age         | Integer      | Age of the participant                                           |
| gender      | Varchar(10)  | Gender of the participant                                        |
| category    | Varchar(50)  | Category of the participant (e.g., "Veteran", "Elite", "Others") |

### 2. RaceResults Table

| Field Name     | Data Type    | Description                                                                         |
|----------------|--------------|-------------------------------------------------------------------------------------|
| id             | Integer (PK) | Primary key for each race result                                                    |
| participant_id | Integer (FK) | Foreign key linking to the Participants table (a participant can have many results) |
| start_time     | DateTime     | Timestamp when the participant crossed the starting line                            |
| end_time       | DateTime     | Timestamp when the participant crossed the finish line                              |
| total_time     | Time         | Total race time                                                                     |
| race_id        | Integer (FK) | Foreign key linking to the Races table                                              |
| category       | Text         | Race category the participant belongs to (e.g., 5k, 10k, Marathon)                  |

### 3. Races Table

| Field Name | Data Type    | Description                                                          |
|------------|--------------|----------------------------------------------------------------------|
| id         | Integer (PK) | Primary key for each race                                            |
| name       | Varchar(255) | Name of the race                                                     |
| date       | Date         | Date of the race                                                     |
| start_time | Time         | Start time of the race                                               |
| categories | Text         | JSON or CSV containing available race categories (e.g., "5k", "10k") |

