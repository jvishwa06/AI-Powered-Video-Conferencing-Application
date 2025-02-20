import cv2
import torch
import numpy as np
import base64
import io
from PIL import Image
import torch.nn as nn
import mediapipe as mp
import timm
import torchvision.transforms as transforms
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Initialize device
device = "cpu"

# Define the transformation
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Load the model
model = timm.create_model("tf_efficientnet_b0_ns", pretrained=False)
model.classifier = nn.Sequential(nn.Linear(in_features=1280, out_features=7))
model = torch.load("22.6_AffectNet_10K_part2.pt", map_location=device, weights_only=False)
model.to(device)
model.eval()

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection

# Define emotion labels
label_dict = {
    0: "angry", 1: "disgust", 2: "fear", 
    3: "happy", 4: "neutral", 5: "sad", 6: "surprised"
}

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/emotion-detection")
async def emotion_detection_websocket(websocket: WebSocket):
    await websocket.accept()
    
    with mp_face_detection.FaceDetection(
        model_selection=0, min_detection_confidence=0.5
    ) as face_detection:
        try:
            while True:
                # Receive base64 encoded frame
                data = await websocket.receive_text()
                
                # Decode base64 to image
                image_data = base64.b64decode(data)
                image = Image.open(io.BytesIO(image_data))
                
                # Convert to numpy array
                frame = np.array(image)
                
                # Convert frame to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Process the frame and detect faces
                results = face_detection.process(rgb_frame)

                emotion = "neutral"
                if results.detections:
                    for detection in results.detections:
                        # Get bounding box
                        bboxC = detection.location_data.relative_bounding_box
                        ih, iw, _ = frame.shape
                        x, y, w, h = (
                            int(bboxC.xmin * iw),
                            int(bboxC.ymin * ih),
                            int(bboxC.width * iw),
                            int(bboxC.height * ih),
                        )

                        # Ensure valid face region
                        if x >= 0 and y >= 0 and x + w <= iw and y + h <= ih:
                            # Extract the face
                            face = frame[y:y+h, x:x+w]

                            # Convert the face to a PIL image
                            face_pil = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB))

                            # Apply transformations
                            face_tensor = transform(face_pil).unsqueeze(0).to(device)

                            # Predict emotion
                            with torch.no_grad():
                                output = model(face_tensor)
                                _, predicted = torch.max(output, 1)

                            emotion = label_dict[predicted.item()]
                
                # Send emotion back to client
                await websocket.send_text(emotion)

        except WebSocketDisconnect:
            print("WebSocket disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="10.1.58.223", port=8000)