import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Performance monitoring
import { getCLS, getFID, getFCP, getLCP, getTTFB } from "web-vitals";

// Create root element
const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);

// Render the app
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Performance monitoring function
function sendToAnalytics(metric: any) {
  // In production, send metrics to your analytics service
  console.log("Web Vitals:", metric);
}

// Report web vitals
getCLS(sendToAnalytics);
getFID(sendToAnalytics);
getFCP(sendToAnalytics);
getLCP(sendToAnalytics);
getTTFB(sendToAnalytics);

// Service Worker registration (optional)
if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        console.log("SW registered: ", registration);
      })
      .catch((registrationError) => {
        console.log("SW registration failed: ", registrationError);
      });
  });
}
