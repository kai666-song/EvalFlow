import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { CreateRunPage } from "./pages/CreateRunPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ReportPage } from "./pages/ReportPage";
import { RunDetailPage } from "./pages/RunDetailPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="runs/new" element={<CreateRunPage />} />
        <Route path="runs/:runId" element={<RunDetailPage />} />
        <Route path="runs/:runId/report" element={<ReportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
