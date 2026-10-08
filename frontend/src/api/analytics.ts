import { apiClient } from "./client";
import type {
  AssignmentAnalytics,
  ClassConceptAnalytics,
  ClassLearningGap,
  ConceptMasterySummary,
  FacultySubjectAnalytics,
  LearningGap,
  PerformanceTrend,
  StudentOverallAnalytics,
  SubjectPerformance
} from "../types/api";

export const analyticsApi = {
  studentOverall: async () => (await apiClient.get<StudentOverallAnalytics>("/api/students/me/analytics")).data,
  studentSubjects: async () => (await apiClient.get<SubjectPerformance[]>("/api/students/me/analytics/subjects")).data,
  studentConcepts: async () => (await apiClient.get<ConceptMasterySummary[]>("/api/students/me/analytics/concepts")).data,
  studentGaps: async () => (await apiClient.get<LearningGap[]>("/api/students/me/analytics/gaps")).data,
  studentTrends: async () => (await apiClient.get<PerformanceTrend[]>("/api/students/me/analytics/trends")).data,
  facultySubject: async (subjectId: number) =>
    (await apiClient.get<FacultySubjectAnalytics>(`/api/faculty/subjects/${subjectId}/analytics`)).data,
  facultyConcepts: async (subjectId: number) =>
    (await apiClient.get<ClassConceptAnalytics[]>(`/api/faculty/subjects/${subjectId}/analytics/concepts`)).data,
  facultyGaps: async (subjectId: number) =>
    (await apiClient.get<ClassLearningGap[]>(`/api/faculty/subjects/${subjectId}/analytics/gaps`)).data,
  assignment: async (assignmentId: number) =>
    (await apiClient.get<AssignmentAnalytics>(`/api/faculty/assignments/${assignmentId}/analytics`)).data
};
