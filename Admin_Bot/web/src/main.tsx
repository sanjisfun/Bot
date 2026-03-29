import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

/** Должен совпадать с `<div id="...">` в `index.html`. */
const ROOT_ID = "root";

const container = document.getElementById(ROOT_ID);
if (!container) {
  throw new Error(`В index.html нет контейнера #${ROOT_ID}`);
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>
);
