import React from 'react';
import ReactDOM from 'react-dom/client';
// Self-hosted variable font: one file covering every weight we use, served from
// our own origin so it costs no extra DNS/TLS round trip.
import '@fontsource-variable/plus-jakarta-sans';
import App from './App';
import './index.css';

const container = document.getElementById('root');
if (!container) throw new Error('Root element #root not found');

ReactDOM.createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
