import React from "react";
import ReactDOM from "react-dom/client";
import { SignalDashboard } from "./components/SignalDashboard";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SignalDashboard />
  </React.StrictMode>
);
