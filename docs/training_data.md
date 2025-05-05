# Training Data and Model Information

## Training Data

This project includes a data-driven component using a machine learning model (YOLOv8) trained to detect race bibs in
video and image inputs. 

### Dataset
The dataset was obtained from a publicly available source:
[Roboflow Dataset](https://universe.roboflow.com/edoardo-cittadini-barxf/bibracenumber)

## Trained Model

The model used in this project is YOLOv11, trained on the datasets linked above.

- **Model File**: The trained model is available at `bib-detector/best.pt`.
- **Usage Instructions**:
The model will be downloaded when the repository is cloned to your local machine. If you wish to access the model independently, you can download the model at the file path listed above.

## Model Inference and Integration

The trained model is used both in video stream processing and batch image processing modes. It integrates with EasyOCR
to extract bib numbers, which are then validated and submitted to an external timing system via
`website_api.py`.

## GitHub/Link Submission
Due to the size of the datasets, they are **not stored directly in the repository**.

Please refer to the following for external resources:

## Training Code

The IPython Notebook containing the code used to train the YOLO model can be found in:
`bib-detector/Group_Project.ipynb`.

