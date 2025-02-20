const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const mongoose = require("mongoose");

const app = express();
const server = http.createServer(app);

const io = new Server(server, {
  cors: {
    origin: "http://localhost:3000",
    methods: ["GET", "POST"],
  },
});

// MongoDB connection
mongoose.connect("mongodb+srv://AravindG:Aravind%234@blazordb.kdp3k.mongodb.net/BlazorDB?retryWrites=true&w=majority&appName=BlazorDB", {
  useNewUrlParser: true,
  useUnifiedTopology: true,
}).then(() => {
  console.log("Connected to MongoDB");
}).catch((err) => {
  console.error("MongoDB connection error:", err);
});

// Emotion model schema
const emotionSchema = new mongoose.Schema({
    peerId: String,
    emotionCounts: {
      angry: { type: Number, default: 0 },
      disgust: { type: Number, default: 0 },
      fear: { type: Number, default: 0 },
      happy: { type: Number, default: 0 },
      neutral: { type: Number, default: 0 },
      sad: { type: Number, default: 0 },
      surprised: { type: Number, default: 0 },
    },
    timestamp: { type: Date, default: Date.now },
  });

  const EmotionSummary = mongoose.model("EmotionSummary", emotionSchema);

const clients = {};

io.on("connection", (socket) => {
  console.log("New client connected:", socket.id);

  clients[socket.id] = {
    angry: 0,
    disgust: 0,
    fear: 0,
    happy: 0,
    neutral: 0,
    sad: 0,
    surprised: 0,
  };

  socket.on("sendEmotion", async (data) => {
    console.log(`Received emotion: ${data.emotion} from peerId: ${data.fromPeerId}`);
    
    if (clients[socket.id]) {
        clients[socket.id][data.emotion] = (clients[socket.id][data.emotion] || 0) + 1;
      }

      // Broadcast to all other clients except the sender
      socket.broadcast.emit("receiveEmotion", {
        emotion: data.emotion,
        fromPeerId: data.fromPeerId,
      });
    });
  
    socket.on("disconnect", () => {
      console.log(`Client disconnected: ${socket.id}`);
    });

    //SAVE
      if (clients[socket.id]) {
        try {
          const emotionSummary = new EmotionSummary({
            peerId: socket.id,
            emotionCounts: clients[socket.id],
          });
           emotionSummary.save();
          console.log("Emotion summary saved to MongoDB for peerId:", socket.id);
        } catch (error) {
          console.error("Error saving emotion summary to MongoDB:", error);
        }
        delete clients[socket.id];
      }

});

server.listen(5000, () => {
  console.log("Socket.IO server running on http://127.0.0.1:5000");
});
