# Training Data and Model Information

## Training Data

This project includes a data-driven component using a machine learning model (YOLOv8) trained to detect race bibs in
video and image inputs. 

### Dataset
TODO

## Trained Model

The model used in this project is YOLOv8, fine-tuned on the datasets described above.

- **Model File**: The trained model is available as `best.pt`.
- **Usage Instructions**:
  1. Download the most up to date `best.pt` file and place it in the bib-detector directory.
  2. Ensure dependencies listed in `requirements.txt` are installed.
  3. The model will be automatically loaded by the YOLOv8 code via:  
     ```python
     model = YOLO("best.pt")
     ```

## Model Inference and Integration

The trained model is used both in video stream processing and batch image processing modes. It integrates with EasyOCR
to extract bib numbers, which are then validated and optionally submitted to an external timing system via
`website_api.py`.

## GitHub/Link Submission
Due to the size of the datasets, they are **not stored directly in the repository**.

Please refer to the following for external resources:
TODO - link datasets used

