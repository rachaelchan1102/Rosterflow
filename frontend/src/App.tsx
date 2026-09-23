import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import ControlTower from "./pages/ControlTower";
import ScenarioPlanner from "./pages/ScenarioPlanner";
import WorkingTools from "./pages/WorkingTools";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ControlTower />} />
          <Route path="scenario" element={<ScenarioPlanner />} />
          <Route path="tools" element={<WorkingTools />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
