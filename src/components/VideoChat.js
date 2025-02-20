import React, { useRef, useState, useEffect } from "react";
import SimplePeer from "simple-peer";
import io from 'socket.io-client';
import "./Video.css";

const VideoChat = () => {
  const [myStream, setMyStream] = useState(null);
  const [peerStream, setPeerStream] = useState(null);
  const [connection, setConnection] = useState(null);
  const [socket, setSocket] = useState(null);
  const [myEmotion, setMyEmotion] = useState("neutral");
  const [peerEmotion, setPeerEmotion] = useState("neutral");
  const [peerId, setPeerId] = useState(null);
  const myVideoRef = useRef();
  const peerVideoRef = useRef();
  const signalInputRef = useRef();

  // Initialize Socket.IO connection
  useEffect(() => {
    const newSocket = io('http://127.0.0.1:5000');
    setSocket(newSocket);

    newSocket.on('connect', () => {
      setPeerId(newSocket.id);
      console.log('Connected to Socket.IO server with ID:', newSocket.id);
    });

    newSocket.on('receiveEmotion', (data) => {
      console.log('Received peer emotion:', data.emotion, 'from peer:', data.fromPeerId);
      if (data.fromPeerId !== newSocket.id) {
        setMyEmotion(data.emotion);
      }
    });

    return () => {
      newSocket.disconnect();
    };
  }, []);

  // Start local video stream with optimized constraints
  const startStream = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      setMyStream(stream);
      myVideoRef.current.srcObject = stream;

      // Start sending frames to the API
      startSendingFrames(stream);
    } catch (err) {
      console.error("Error accessing media devices:", err);
    }
  };

  // Function to start sending frames to the API
  const startSendingFrames = (stream) => {
    const videoTrack = stream.getVideoTracks()[0];
    const imageCapture = new ImageCapture(videoTrack);

    // Create WebSocket connection to emotion detection API
    const websocket = new WebSocket("ws://127.0.0.1:8000/ws/emotion-detection"); 

    websocket.onopen = () => {
      console.log("WebSocket connection to emotion API established");
    };

    websocket.onmessage = (event) => {
      console.log("Received emotion from API:", event.data);
      setPeerEmotion(event.data);
      
      // Send emotion to peer via Socket.IO
      if (socket && peerId) {
        socket.emit('sendEmotion', { 
          emotion: event.data, 
          fromPeerId: peerId 
        });
      }
    };

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    // Capture frames at a regular interval
    const captureFrame = async () => {
      try {
        const bitmap = await imageCapture.grabFrame();
        const canvas = document.createElement("canvas");
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(bitmap, 0, 0);

        // Convert canvas to base64 image
        const base64ImageData = canvas.toDataURL("image/jpeg");

        // Send base64 image data to the WebSocket server if connected
        if (websocket.readyState === WebSocket.OPEN) {
          websocket.send(base64ImageData.split(",")[1]); // Send only the base64 part
        }
      } catch (error) {
        console.error("Error capturing frame:", error);
      }
    };

    const frameInterval = setInterval(captureFrame, 1000);

    websocket.onclose = () => {
      clearInterval(frameInterval);
      console.log("Emotion WebSocket connection closed");
    };
  };

  // Rest of the code remains the same as in the previous implementation
  // Create a new peer connection with optimized settings
  const createConnection = () => {
    if (!myStream) {
      console.error("Cannot create connection: myStream is not initialized");
      return;
    }

    const peer = new SimplePeer({
      initiator: true,
      trickle: false,
      stream: myStream,
    });

    peer.on("signal", (data) => {
      console.log("Signal data:", JSON.stringify(data));
      // alert("Share this signal with your peer:\n" + JSON.stringify(data));
      navigator.clipboard.writeText(JSON.stringify(data))
        .then(() => alert("Signal copied to clipboard! Share it with your peer."))
        .catch((err) => console.error("Failed to copy: ", err));
    });

    peer.on("stream", (stream) => {
      console.log("Peer stream received");
      setPeerStream(stream);
      if (peerVideoRef.current) {
        peerVideoRef.current.srcObject = stream;
      }
    });

    peer.on("error", (err) => {
      console.error("Peer connection error:", err);
    });

    peer.on("close", () => {
      console.log("Peer connection closed");
    });

    setConnection(peer);
  };

  // Join an existing connection using a signal
  const joinConnection = () => {
    if (!connection) {
      const peer = new SimplePeer({
        initiator: false,
        trickle: false,
        stream: myStream,
      });

      peer.on("signal", (data) => {
        // var dataSignal = JSON.stringify(data);
        console.log("Signal data:", JSON.stringify(data));
        // alert("Share this signal with your peer:\n" + JSON.stringify(data));
        navigator.clipboard.writeText(JSON.stringify(data))
        .then(() => alert("Signal copied to clipboard! Share it with your peer."))
        .catch((err) => console.error("Failed to copy: ", err));
      });

      peer.on("stream", (stream) => {
        console.log("Peer stream received");
        setPeerStream(stream);
        if (peerVideoRef.current) {
          peerVideoRef.current.srcObject = stream;
        }
      });

      setConnection(peer);
    }

    const signalData = JSON.parse(signalInputRef.current.value);
    connection.signal(signalData);
  };

  return (
    <div className="video-chat">
      <div className="video-container">
        <div>
          <h3>My Video</h3>
          <video ref={myVideoRef} autoPlay muted></video>
          <div className="emotion-display">Detected Emotion: {peerEmotion}</div>
        </div>
        <div>
          <h3>Peer Video</h3>
          <video ref={peerVideoRef} autoPlay></video>
          <div className="emotion-display">Peer's Emotion: {myEmotion}</div> 
        </div>
      </div>

      {/* Rest of the JSX remains the same */}
      <div className="controls">
        {!myStream && <button onClick={startStream}>Start My Stream</button>}
        {myStream && !connection && (
          <button onClick={createConnection}>Create Connection</button>
        )}
        {myStream && connection && (
          <>
            <textarea ref={signalInputRef} placeholder="Paste signal here"></textarea>
            <button onClick={joinConnection}>Join Connection</button>
          </>
        )}
      </div>

      <style jsx>{`
        .emotion-display {
          font-size: 24px;
          font-weight: bold;
          color: #333;
          margin-top: 10px;
          text-align: center;
        }
      `}</style>
    </div>
  );
};

export default VideoChat;
