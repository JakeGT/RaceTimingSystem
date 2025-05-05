## Requirements
This section outlines the operational requirements for the Automatic Race Timing System. It provides a
comprehensive overview of the necessary resources for both continued development and system operation, including
estimated costs where applicable.

### Hardware Requirements

#### Django Backend
- **Minimum Requirements**
  - CPU: 1 Core
  - RAM: 1GB
  - Storage: 1GB + Amount for Images
- **Recommended System**
  - CPU: 2+ Cores
  - RAM: 2GB
  - Storage: 1GB + Amount for Images

**NOTE:** System requirements will scale with number of races and users

#### Computer Vision - Bib Detector Client
- **Mininum Requirements**
  - CPU: Intel i7 8565U or AMD Ryzen 5 4500U or equivalent
  - RAM: 4GB
  - Storage: 1GB
  - USB Port or Network Access for Cameras
  - Network Access to upload results
- **Recommended System**
  - CPU: Intel i7 10875H or AMD Ryzen 7 5800H or Apple M1 or equivalent
  - RAM: 8GB
  - Storage: 64GB - When storing the recorded race footage
  - GPU: Nvidia RTX 2060
  - USB Port or Network Access for Cameras
  - Network Access to upload results


ROCm Support on AMD GPUs is handled through PyTorch. Please refer to [PyTorch Documentation](https://pytorch.org/get-started/locally)

Apple M Chips are handled through MPS in PyTorch. Please refer to [Apple Developer](https://developer.apple.com/metal/pytorch/)


- **Peripheral Devices**
  - Minimum 720p camera or mobile phone with Droidcam
  - External storage could be necessary for very large race datasets with video storage

##### Software Requirements:
- **Operating System**: Windows 10/11, macOS, or Linux (Ubuntu 20.04+ recommended)
- **Python 3.13** (Required for Django 5.x and other dependencies)
- Django 5.x: The primary framework for web development, may work on earlier versions.
- Database: SQLite
- Python dependencies can be found at `bib-detector\requirements.txt` and `running\requirements.txt` and can be installed using:
```python
pip install -r requirements.txt
```
- **RECOMMENDED**: CUDA Toolkit (or other GPU-acceleration libraries): Required for GPU-accelerated tasks (e.g., training the computer
vision model). Only necessary if using an NVIDIA GPU. For non-NVIDIA setups, consider alternatives such as ROCm (AMD)
or MPS (Apple).
- **Git**: For version control

##### Django Backend - Software Requirements:
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
  - Camera or Phone: **£300 - £500** (one-time cost)
  - Cloud Hosting: **£10 - £45/month** (depending on usage, its unlikely any more than the £10 subscription is required)
- Software:
  - Free for Django, CUDA, and open-source libraries.
- Labor Costs:
  - Maintenance: **£675 - £1350/year** for a developer or system admin.

##### Cost Sources
- Cloud Costs: Based on [AWS](https://aws.amazon.com/pricing/)/[Collab](https://colab.research.google.com/signup) pricing
- Hardware Costs: Based on Amazon/vendor pricing
- Labour Costs: Estimated at £150 days as the lower bound
