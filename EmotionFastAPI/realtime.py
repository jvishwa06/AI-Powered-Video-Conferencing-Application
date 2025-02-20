import cv2
import torch
import torchvision.transforms as transforms
from PIL import Image
import timm
import torch.nn as nn
import mediapipe as mp
import time
import numpy as np

device = "cpu"

transform = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)

model = timm.create_model("tf_efficientnet_b0_ns", pretrained=False)
model.classifier = nn.Sequential(nn.Linear(in_features=1280, out_features=7))
model = torch.load("22.6_AffectNet_10K_part2.pt", map_location=device, weights_only=False)
model.to(device)
model.eval()

mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

label_dict = {
    0: "angry",
    1: "disgust",
    2: "fear",
    3: "happy",
    4: "neutral",
    5: "sad",
    6: "surprised",
    7: "No_Face",
    8: "Body",  
}

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not access the webcam.")
    exit()

fps = 30 

with mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.8) as face_detection:
    prev_emotion = None
    change_list = []
    begin = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Unable to capture webcam frame.")
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = face_detection.process(rgb_frame)

        if results.detections:
            for detection in results.detections:

                bboxC = detection.location_data.relative_bounding_box
                ih, iw, _ = frame.shape
                x, y, w, h = (
                    int(bboxC.xmin * iw),
                    int(bboxC.ymin * ih),
                    int(bboxC.width * iw),
                    int(bboxC.height * ih),
                )

                if w > 0 and h > 0:
                    face = frame[y: y + h, x: x + w]

                    if face.size == 0:
                        continue

                    face_pil = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB))

                    face_tensor = transform(face_pil).unsqueeze(0).to(device)

                    with torch.no_grad():
                        output = model(face_tensor)
                        _, predicted = torch.max(output, 1)

                    current_emotion = predicted.item()
                    label = label_dict[current_emotion]

                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(
                        frame,
                        f"{label}",
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.9,
                        (255, 0, 0),
                        2,
                    )

                    if current_emotion != prev_emotion:
                        current_time = time.time() - begin
                        if prev_emotion is not None:
                            print(f"{label} at {current_time}")
                            change_list.append(f"Change detected: {label_dict[prev_emotion]} -> {label} at {current_time}")
                    prev_emotion = current_emotion

        else:
            label = label_dict[7] 
            cv2.putText(
                frame,
                f"{label}",
                (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

        cv2.imshow("Emotion Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    print("Emotion Change List:")
    for change in change_list:
        print(change)
