# Automated Race Timing

# Vision-Based Race Timing System

## Executive Summary

Across the world, people compete in running races that span a variety of ages, abilities, and formats. These events 
require accurate and reliable timing systems. While professional races often use RFID-based timing, this technology is
expensive and requires specialist setup—placing it out of reach for many amateur and grassroots events.

Traditionally, these races rely on manual timing with stopwatches and clipboards, or tablets with custom apps. However,
these methods are prone to human error and can struggle when multiple runners cross the finish line simultaneously.

This project offers a modern, low-cost alternative by leveraging advances in computer vision and the widespread
availability of high-quality cameras. Our system enables organisers to time races using one or more cameras positioned
near the finish line. The system detects runners and their bib numbers from video, timestamps when they cross the line,
and posts results to a website in near real time.

The setup consists of a camera connected to a laptop. A locally running computer vision pipeline detects runners,
identifies bib numbers via OCR, and records their finishing times. These results are uploaded to a Django-based website
via a REST API, where race data can be viewed live.

Compared to RFID systems, our approach is significantly cheaper and requires minimal technical expertise. It also
compares favourably to manual timing, offering accuracy within 1-2 seconds while avoiding typical human errors. Since it
uses commonly available tools—laptops, webcams or action cams - it is accessible to organisers with little to no technical
background.

Naturally, challenges exist. Poor lighting, bad weather, or unorthodox bib placements (e.g., worn on thighs instead of
chests) can impact recognition. However, most races avoid such conditions, and the system’s performance can be enhanced 
with multi-camera setups and modest organiser training. The system is also designed to run efficiently on most modern 
laptops, reducing hardware barriers to entry.

In summary, this solution gives everyone access to reliable race timing. By blending practicality with accessible
technology, it provides an accurate, scalable, and affordable system for event organisers worldwide.

## Developers

- Jake Talling
- Max Bennett
- Angelo Palmer 
- Lucy Dechaine
- James Adams

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE. See the `LICENSE` file for details.

## Dependencies

The project relies on the following core technologies:

### Backend (Django Website)
- Python 3.10+
- Django 4.x
- SQLite (default database)
- Django REST Framework

### Frontend (Website)
- Bootstrap (for styling)
- JavaScript (basic UI interactivity)

### Computer Vision Pipeline
- YOLO (via Ultralytics)
- EasyOCR (OCR support)
- TODO

### Optional Tools
- Git (version control)

## Setup Instructions

1. Clone this repository
2. Create a virtual environment
3. Install dependencies

## Usage
TODO

## Screenshots
TODO

## Future Work
TODO

## Development Environment
For more details, check out the [development environment](docs/development_environment.md).

## Installation guide
For more details, check out the [installation guide](docs/installation.md).

## File Structure
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
