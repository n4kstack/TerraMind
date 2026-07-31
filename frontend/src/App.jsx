import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Advisor from './pages/Advisor';
import Monitor from './pages/Monitor';
import Diagnosis from './pages/Diagnosis';
import GraphRAG from './pages/GraphRAG';
import Architecture from './pages/Architecture';

export default function App() {
  return (
    <Router>
      <Layout version="1.0.0">
        <Routes>
          <Route path="/" element={<Advisor />} />
          <Route path="/monitor" element={<Monitor />} />
          <Route path="/diagnosis" element={<Diagnosis />} />
          <Route path="/chatbot" element={<Navigate to="/diagnosis" replace />} />
          <Route path="/graphrag" element={<GraphRAG />} />
          <Route path="/architecture" element={<Architecture />} />
          
          {/* Fallback for deep-linked legacy paths if any */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  );
}
