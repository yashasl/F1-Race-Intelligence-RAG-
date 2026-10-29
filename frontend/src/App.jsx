import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage.jsx";
import AIRaceChat from "./pages/AIRaceChat.jsx";
import RaceExplorer from "./pages/RaceExplorer.jsx";
import DriverComparison from "./pages/DriverComparison.jsx";
import AboutPage from "./pages/AboutPage.jsx";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/race-explorer", label: "Race Explorer" },
  { to: "/driver-comparison", label: "Driver Comparison" },
  { to: "/chat", label: "AI Race Chat" },
  { to: "/about", label: "About" },
];

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-dark">
        <header className="sticky top-0 z-10 border-b border-gray-800 bg-dark/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
            <NavLink to="/" className="text-lg font-bold tracking-tight text-white">
              F1 <span className="text-accent">Performance</span> Analytics
            </NavLink>
            <nav className="flex flex-wrap gap-1 text-sm">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 ${
                      isActive
                        ? "bg-accent/15 text-accent"
                        : "text-gray-400 hover:bg-gray-800 hover:text-white"
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl px-4 py-8">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/chat" element={<AIRaceChat />} />
            <Route path="/race-explorer" element={<RaceExplorer />} />
            <Route path="/driver-comparison" element={<DriverComparison />} />
            <Route path="/about" element={<AboutPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
