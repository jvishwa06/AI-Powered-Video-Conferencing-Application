import React from "react";
import VideoChat from "./components/VideoChat";
// import React from 'react';
import { BrowserRouter as Router, Route, Routes, Link } from 'react-router-dom';
// import VideoChat from './components/VideoChat';
// import EmotionDashboard from './components/EmotionDashboard'; // Create this file later

function App() {
  return (
    <Router>
      <div className="App">
        <h3>AI-Powered Video Conferencing Application Using React & Torchserve(API)</h3>
        

        <Routes>
          <Route path="/" element={<VideoChat />} />
        
        </Routes>
      </div>
    </Router>
  );
}

export default App;
