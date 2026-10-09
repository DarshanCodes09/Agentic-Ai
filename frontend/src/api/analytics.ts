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
  studentOverall: async () => (await apiClient.get<StudentOverallAnalytics>("/students/me/analytics")).data,
  studentSubjects: async () => (await apiClient.get<SubjectPerformance[]>("/students/me/analytics/subjects")).data,
  studentConcepts: async () => (await apiClient.get<ConceptMasterySummary[]>("/students/me/analytics/concepts")).data,
  studentGaps: async () => (await apiClient.get<LearningGap[]>("/students/me/analytics/gaps")).data,
  studentTrends: async () => (await apiClient.get<PerformanceTrend[]>("/students/me/analytics/trends")).data,
  facultySubject: async (subjectId: number) =>
    (await apiClient.get<FacultySubjectAnalytics>(`/faculty/subjects/${subjectId}/analytics`)).data,
  facultyConcepts: async (subjectId: number) =>
    (await apiClient.get<ClassConceptAnalytics[]>(`/faculty/subjects/${subjectId}/analytics/concepts`)).data,
  facultyGaps: async (subjectId: number) =>
    (await apiClient.get<ClassLearningGap[]>(`/faculty/subjects/${subjectId}/analytics/gaps`)).data,
  assignment: async (assignmentId: number) =>
    (await apiClient.get<AssignmentAnalytics>(`/faculty/assignments/${assignmentId}/analytics`)).data
};
