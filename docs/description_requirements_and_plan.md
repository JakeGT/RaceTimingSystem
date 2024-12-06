## Project Plan

### Project Aims
The aim of the project is to develop a complete system for recording and live updating the results of races. The system should provide a complete package for race organisers that is easy to use, regardless of their technical ability and provide results which lie within an acceptable degree of accuracy.


### Project objectives
- Computer vision model for recognising runners
- Computer vision model for recognising bibs
- Model to associate runners with corresponding bibs
- Model for recognising finishing times
- System for uploading results

### Stretch goals
- Multiple camera configuration for improved accuracy and occlusion reduction
- Race website
- Configurable augmented reality finish line creation

### Gantt chart
[Gantt Chart](gantt.xlsx)
#### Using the gantt chart
In order to scroll through the gantt chart, change the number in cell C7 called scrolling increment.

#### Research and Planning
 - Project Kick-off report: This is the first submissible and contains the summary, project spec, requirements, inventory, success criteria, and ethics.
 - Background Research: Initial research into the potential development pathway of the project. This includes research into the project requriements from the client.

#### Project Design
 - System Design: This is the stage where we define the overall system such as the interfaces between each component and how the project will be broken down into smaller components. 
 - Component Design: This is where the design of each individual components, such as the website and database, is completed.
 - Model Design: This is the point where the computer vision models are selected based on our background research. 

#### Implementation
 - Dataset Pre-processing: This is where videos and images from running races and cropped and handled by humans to get the bib number along with the bounding box for the runners and the bibs.
 - Model creation and training: This is where we take the dataset and start running the training process of the dataset.
 - Front-end Components Implementation: This will be the website such as live race times and race management screens.
 - Back-end Components Implementation: This would elements such as the database, race time processing, computer vision, etc. 
 - Component Integration: This is where each individual component developed is brought together into a complete system.

#### Testing and Validation
 - Unit Testing:
 - Component Testing:
 - System Testing:

#### Documentation and Reporting
 - Handover Report
 - Code Documentation

#### Presentation
 - Prepare and Deliver Presentation