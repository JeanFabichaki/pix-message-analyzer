import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { MotionProvider } from './motion/MotionProvider';
import { ToastProvider } from './components/ui/Toast';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MotionProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </MotionProvider>
  </React.StrictMode>
);
