# Automated Race Timing

## Executive Summary

Across the world, people compete in running races that span a variety of ages, abilities, and formats. These events 
require accurate and reliable timing systems. While professional races currently use RFID-based timing systems, this
technology is out-dated, expensive and requires specialist setup — placing it out of reach for many amateur and
grassroots events.

Traditionally, the aforementioned smaller races rely on manual timing with stopwatches and clipboards, or tablets with custom
apps. However, these methods are prone to human error and can struggle when multiple runners are crossing the finish 
line simultaneously.

This project offers a modern, low-cost alternative by leveraging advances in computer vision and the widespread
availability of high-quality cameras. Our system enables organisers to time races using a camera positioned
near the finish line. The system detects runners and their bib numbers from the video feed, timestamps when they cross the
finish line, and posts results to a website in near real time, provided a stable connection to the internet.

The organiser setup consists of a single camera, connected to a nearby laptop. A locally running computer vision pipeline 
detects runners, identifies bib numbers via OCR, and records their finishing times. These results are uploaded to a 
Django-based website via REST API calls, where race data can be viewed live.

Compared to RFID systems, our approach is significantly cheaper and was designed woth non-technical users in mind. It also
compares favourably to manual timing, offering accuracy within 1-2 seconds while avoiding typical human errors. Since it
uses commonly available tools — laptops, webcams or action cams - it is accessible to organisers with little to no technical
background.

Naturally, challenges exist. Poor lighting, bad weather, or unorthodox bib placements (e.g., worn on thighs instead of
chests) can impact recognition. However, most races avoid such conditions, and the system’s performance could be further
enhanced by implementing multi-camera setups. The system is also designed to run efficiently on most modern laptops,
reducing the hardware barriers required to entry.

By making accurate race timing accessible and affordable, this solution opens the door for thousands of small and 
medium-sized events worldwide to offer professional-grade results without professional-grade costs. It combines modern
technology with practical simplicity — allowing organisers to deliver a better race experience.

## Developers

- Jake Talling
- Max Bennett
- Angelo Palmer 
- Lucy Dechaine
- James Adams

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE. See the [LICENSE](LICENSE) file for details.

## Dependencies

The project relies on the following core technologies:

### Backend (Django Website)
- Python 3.13+
- Django 4.x
- SQLite (default database)
- Django REST Framework

### Frontend (Website)
- Bootstrap (for styling)
- JavaScript (basic UI interactivity)

### Computer Vision Pipeline
- YOLO (via Ultralytics)
- EasyOCR (OCR support)
- Flask (for creating REST API calls)

### Other Tools
- Git (version control)

## Setup Instructions

1. Clone this repository:
    ```bash
    git clone https://github.com/UoE-ECMM427-202425/Running.git
    ```

2. Create a virtual environment

    For Windows:
    ```bash
    python -m venv venv
    ```
    
    For MacOs/Linux
    ```bash
    python3 -m venv venv
    ```

3. Install dependencies
   - First activate the virtual environment:
   For Windows:
     ```bash
     venv\Scripts\activate
     ```
    
     For MacOs/Linux
     ```bash
     source venv/bin/activate
     ```
     
   - Install all required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

- Django website (local):
1. Navigate to the `running` directory:
   ```bash
    cd running
    ```
2. Apply database migrations:
     ```bash
     python manage.py migrate
     ```
3. Run Django website locally:
     ```bash
     python manage.py runserver
     ```
  
- Computer Vision Script
TODO

## Screenshots
Screenshots of the product can be found in `/screenshots`

## Future Work
In order for further expansion feature could be added which include:
- Support for multiple cameras (multi-angle detection).
- Expand to include start timing + split tracking.
- Migration of computer vision script to mobile

## Development Environment
For more details, check out the [development environment](docs/development_environment.md).

## Installation guide
For more details, check out the [installation guide](docs/installation.md).

## Repository Layout and Test/CI Setup
For more details, check out the [file structure](docs/file_structure.md).

## Maintenance
For more details, check out the [maintenance](docs/maintenance.md).

## Source Code Documentation
For more details, check out the [Source Documentation](docs/source_code_documentation.md).

## System Requirements
For more details, check out the [System Requirements](docs/system_requirements.md).

## Training Data
For more details, check out the [training data](docs/training_data.md).

## Usage Guide
For more details, check out the [Usage_guide](docs/usage_guide.md).
