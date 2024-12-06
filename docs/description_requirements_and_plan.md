1	Business Proposal and Background

The proposed project addresses the challenges faced by race organisers in timing race events. Throughout history, there have been a number of methods for timing races, from an officiant manually taking down the time of each runner to the most recent RFID based systems. The proposed project offers a viable alternative method to these through the advancing technology of computer vision to read race numbers as they cross the finish line and provide highly accurate race timings and relative positioning.
The solution aims to be cheaper and easier to set up than RFID systems and less prone to human error than manual stopwatch timing. Utilising one or more cameras to record a video of the race, the system will employ computer vision methods to extract the position of each runner and the number on their race bibs to then be associated with the current time in order to determine their finishing time. In addition to this, there will be the construction of a leaderboard and race organisation website that will handle the features such as race creation, runner data, live race times, and other such things, which can then be easily integrated into any organisation’s existing website.

2	Project Specification

The project specification is split into the computer vision and website components of the project. Within these components is a brief overview of the purpose of these components, and the requirements for each possible level of final product.
Items Minimum Viable Product will have the highest priority, and items in stretch goals will have the lowest priority.

2.1	Computer Vision

The computer vision component of this project is broken down into 3 distinct pieces. Runner detection, race bib detection, and race bib optical character recognition.
In this part of the project, the main goal would be to use a framework such as YOLO (possibly with the help of OCR Viola-Jones) to build a model to detect runners in real time. This would require a dataset of runners to train the model on.

2.1.1	Minimum Viable Product
  1.	The software should be able to identify and read bibs using either YOLO or OCR Viola-Jones
  2.	It should detect when the bib finishes the race i.e. leaves screen or crosses a line defined by theuser

2.1.2	Ideal Product
  1.	The software should identify the full runner, to allow for more accurate timing
  2.	It should be able to identify runners whose bibs cannot be read, and store frames when therunner is visible to allow user to review and identify them by hand

2.1.3	Stretch Goals
  1. The software should implement a 2 camera system that each independently detects and times, and then balance each other out to provide a more accurate system

2.2	Website

The project also requires a website that allows runners to access their finish times in near real time. The website should have a number of features and design choices that will need to be implemented.

2.2.1	Minimum Viable Product
  1.	The website must post the times to a leaderboard soon after the race concludes
  2.	The leaderboard must display the correct order for race finishers
  3.	The organiser must have access to the video of the finishers in order to comply with GDPR

2.2.2	Ideal Product
  1.	The website should post the times for each individual runner shortly after the runner has finishedthe race and the computer vision has determined the time and position
  2.	The website should allow the videos of unidentified runners to be looked over by an admin formanual identification, with the times for that runner being posted once that is completed
  3.	The website should correctly connect bib numbers to a database of racers names, age categoriesand other useful leaderboard information

2.2.3	Stretch Goals
  1.	The website could provide an API for the race organiser to integrate the race results into theirown website
  2.	Each time entry should also have a link for the runner to view the video of them crossing theline
  3.	The leaderboard should allow users to filter by runner categories

3	Success Criteria

3.1	Minimum Viable Product
  1.	The race recording program can run on a high-end laptop with good specifications
  2.	Able to identify runner bibs within an acceptable error margin
  3.	Able to read the runner bibs where the number is clear in the image
  4.	Able to record a correct time for when the bib finished, within a 2 second accuracy
  5.	Able to post results to an online leaderboard
  6.	Able to correctly format the leaderboard to show the runners in the correct order
  7.	Able to retrieve any stored video or images for the purposes for complying with GDPR

3.2	Ideal Project
  1.	The race recording program can run on the average laptop
  2.	Able to identify the full runner’s body, and connect them to the correct bib
  3.	Able to save video where the runner’s bib cannot be read for future manual verification
  4.	The user can view videos for unidentified runners and manually input their bib number
  5.	Leaderboard is updated in near real-time
  6.	Fill out leaderboard with correct runner information such as name, position, and other desiredmetrics

3.3	Stretch Goals
  1.	The race recording program can be run on the vast majority of laptops, encompassing even someof the lowest-spec systems
  2.	Able to run a multi-camera system
  3.	Able to use the multi-camera system to improve timing and bib reading accuracy
  4.	Runners can view the video of their finish time
  5.	The leaderboard can be attached to the organisers website
  6.	The leaderboard can be filtered by runner categories like age group or gender


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
This will consist of unit tests, component tests and system tests. This means testing individual functions, individual components and then the system as a whole.

#### Documentation and Reporting
 - Handover Report
 - Code Documentation

#### Presentation
 - Prepare and Deliver Presentation
