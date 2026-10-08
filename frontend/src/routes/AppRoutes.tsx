import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { LoadingState } from "../components/ui/State";
import { useAuth } from "../context/AuthContext";
import type { UserRole } from "../types/api";
import { LoginPage } from "../pages/auth/LoginPage";
import { RegisterPage } from "../pages/auth/RegisterPage";
import { StudentAnalyticsPage } from "../pages/student/StudentAnalyticsPage";
import { StudentAssignmentPage } from "../pages/student/StudentAssignmentPage";
import { StudentDashboardPage } from "../pages/student/StudentDashboardPage";
import { StudentSubmissionPage } from "../pages/student/StudentSubmissionPage";
import { StudentSubmissionsPage } from "../pages/student/StudentSubmissionsPage";
import { StudentSubjectDetailPage } from "../pages/student/StudentSubjectDetailPage";
import { StudentSubjectsPage } from "../pages/student/StudentSubjectsPage";
import { FacultyAnalyticsPage } from "../pages/faculty/FacultyAnalyticsPage";
import { FacultyAssessmentReviewPage } from "../pages/faculty/FacultyAssessmentReviewPage";
import { FacultyDashboardPage } from "../pages/faculty/FacultyDashboardPage";
import { FacultyMaterialsPage } from "../pages/faculty/FacultyMaterialsPage";
import { FacultySubmissionsPage } from "../pages/faculty/FacultySubmissionsPage";
import { FacultySubjectAssignmentsPage } from "../pages/faculty/FacultySubjectAssignmentsPage";
import { FacultySubjectsPage } from "../pages/faculty/FacultySubjectsPage";

function Protected({ role }: { role: UserRole }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <LoadingState label="Checking access" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (user.role !== role) return <Navigate to={user.role === "FACULTY" ? "/faculty/dashboard" : "/student/dashboard"} replace />;
  return <AppLayout />;
}

export function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/" element={<Navigate to={user?.role === "FACULTY" ? "/faculty/dashboard" : user ? "/student/dashboard" : "/login"} />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<Protected role="STUDENT" />}>
        <Route path="/student/dashboard" element={<StudentDashboardPage />} />
        <Route path="/student/subjects" element={<StudentSubjectsPage />} />
        <Route path="/student/subjects/:subjectId" element={<StudentSubjectDetailPage />} />
        <Route path="/student/assignments/:assignmentId" element={<StudentAssignmentPage />} />
        <Route path="/student/assignments/:assignmentId/submit" element={<StudentSubmissionPage />} />
        <Route path="/student/submissions" element={<StudentSubmissionsPage />} />
        <Route path="/student/submissions/:submissionId/assessment" element={<StudentSubmissionPage assessmentMode />} />
        <Route path="/student/analytics" element={<StudentAnalyticsPage />} />
      </Route>

      <Route element={<Protected role="FACULTY" />}>
        <Route path="/faculty/dashboard" element={<FacultyDashboardPage />} />
        <Route path="/faculty/subjects" element={<FacultySubjectsPage />} />
        <Route path="/faculty/subjects/:subjectId/assignments" element={<FacultySubjectAssignmentsPage />} />
        <Route path="/faculty/subjects/:subjectId/materials" element={<FacultyMaterialsPage />} />
        <Route path="/faculty/subjects/:subjectId/analytics" element={<FacultyAnalyticsPage />} />
        <Route path="/faculty/assignments/:assignmentId/submissions" element={<FacultySubmissionsPage />} />
        <Route path="/faculty/submissions/:submissionId/assessment" element={<FacultyAssessmentReviewPage />} />
        <Route path="/faculty/analytics" element={<FacultySubjectsPage analyticsEntry />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
