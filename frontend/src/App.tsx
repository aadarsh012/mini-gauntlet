import { Link, Route, Routes } from "react-router-dom";
import ScanPage from "./pages/ScanPage";
import ScansPage from "./pages/ScansPage";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          Mini Gauntlet
        </Link>
        <span className="muted">Cloud posture scanner</span>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<ScansPage />} />
          <Route path="/scans/:id" element={<ScanPage />} />
          <Route path="*" element={<p className="empty">Page not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
