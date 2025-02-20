import torch
import torch.nn.functional as F
from fastapi import FastAPI, UploadFile, File
from torchvision import transforms
from PIL import Image
import io
import uvicorn

app = FastAPI()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = torch.load("22.6_AffectNet_10K_part2.pt", map_location=device, weights_only=False)
model.eval()

labels = ["Neutral", "Happy", "Sad", "Surprise", "Anger"]

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        image = preprocess(image).unsqueeze(0).to(device)

        with torch.no_grad():
            output = model(image)
            probabilities = F.softmax(output, dim=1)
            predicted_class = torch.argmax(probabilities, dim=1).item()

        return {"prediction": labels[predicted_class]}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
