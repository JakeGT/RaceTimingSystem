## Requirements
This section outlines the development and operational requirements for the Automatic Race Timing System. It provides a
comprehensive overview of the necessary resources for both continued development and system operation, including
estimated costs where applicable.

#### Development Requirements

##### Hardware Requirements:
For development purposes, the following hardware is recommended:
- **Development Machine**
  - CPU: Intel i5 or equivalent (for general development tasks)
  - RAM: Minimum 8GB (16GB or more preferred for heavier tasks like model training)
  - GPU: NVIDIA GPU with CUDA support (e.g., GTX 1060 or above for GPU accelerated model building)
  - Storage: At least 1GB, for storing the website/user data, as well as storing video footage/images (for larger races
  more storage could be required)
  - OS: Any OS may be used (e.g., Windows, Linux)
- **Peripheral Devices**
  - High-resolution camera for capturing race footage
  - External storage could be necessary for very large race datasets with video storage

##### Software Requirements:
- **Operating System**: Windows 10/11, macOS, or Linux (Ubuntu 20.04+ recommended)
- **Python 3.10+** (Required for Django 5.x and other dependencies)
- Django 5.x: The primary framework for web development, may work on earlier versions.
  Install Django using pip:
```python 
pip install django
```
- Database: SQLite
- Other python dependencies must be installed using:
```python
pip install -r requirements.txt
```
- CUDA Toolkit (or other GPU-acceleration libraries): Required for GPU-accelerated tasks (e.g., training the computer
vision model). Only necessary if using an NVIDIA GPU. For non-NVIDIA setups, consider alternatives such as ROCm (AMD)
or OpenCL.
- **GitHub**: For version control

#### Operational Requirements
##### Hardware Requirements:
For running the system in a production environment, the following hardware is required:
- Laptop/PC with GPU enabled: The system will run on a machine with GPU enabled for better processing, especially for
tasks such as running the computer vision models. The laptop must also have access to the internet in order to upload
the results data to the website live.
- Server Requirements: The system shall be hosted via the university hosting service, however it is possible to perform
self-hosting this could be done in two different ways:
  - Server Requirements:
    - Processor: Intel i5 or equivalent (for general development tasks)
    - RAM: 8GB minimum
    - Storage: 64GB SSD (expandable as needed for race footage storage)
    - GPU: NVIDIA 1060 (optional for Computer Vision AI-based processing)
  - Cloud Hosting:
    - Recommended Cloud Provider: AWS, Azure, or Google Cloud

##### Software Requirements:
- Hosting Environment:
  - Cloud-hosted (AWS, Azure, or University hosting) OR on-premise server
  - Nginx or Apache for web server management
  - SQLite database for storing race and user data
- Security and Maintenance:
  - SSL/TLS encryption for secure communications
  - Regular software updates and security patches

#### Estimated Operational Costs
- Hardware Costs (Laptop/PC with GPU enabled):
  Laptop with NVIDIA GPU (e.g., NVIDIA GTX 1060 or 1660 series): Around £600 - £800 for a mid-range laptop with a decent GPU for development and basic tasks.
  For heavier operations (such as computer vision model training), the cost might increase for higher-end laptops or desktop builds with more modern GPUs (in such cases cloud subscription may be more appropriate).
- High-resolution camera: £300 however most modern phones have high resolution cameras which would be appropriate
- Cloud Subscription Costs (if applicable):
  Cloud Service (AWS, Google Cloud, or Azure): For GPU for Computer Vision model training would cost approximately £10 per month (taken from a Collab pro subscription)
- Software Licenses:
  - Django: Free and open-source.
  - CUDA and cuDNN: Free and open-source (for NVIDIA GPUs).
  - Other Libraries: Python-based libraries like TensorFlow, PyTorch, etc., are free.
- Labour Costs (Maintenance and Updates):
  Regular Maintenance (e.g., checking server health, updating dependencies or dealing with client issues):
      Estimated time: 5-10 person days per year.
      Cost per hour: £15/hour (depending on the region, seniority of the developer, and market).
      Total Annual Cost: Between £675 - £1350/year for maintaining the system.

#### Summary of Estimated Costs:
- Hardware:
  - Laptop with GPU: **£600 - £800** (one-time cost)
  - Camera: **£300 - £500** (one-time cost)
  - Cloud Hosting: **£10 - £45/month** (depending on usage, it unlikely any more than the £10 subscription is required)
- Software:
  - Free for Django, CUDA, and open-source libraries.
- Labor Costs:
  - Maintenance: **£675 - £1350/year** for a developer or system admin.

##### Cost Sources
- Cloud Costs: Based on [AWS](https://aws.amazon.com/pricing/)/[Collab](https://colab.research.google.com/signup) pricing
- Hardware Costs: Based on Amazon/vendor pricing
- Labour Costs: Estimated at £150 days as the lower bound
