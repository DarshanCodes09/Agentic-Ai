import { apiClient } from "./client";
import type { Assessment } from "../types/api";

export const assessmentsApi = {
  getBySubmission: async (submissionId: number) =>
    (await apiClient.get<Assessment>(`/api/submissions/${submissionId}/assessment`)).data,
  trigger: async (submissionId: number, force = false) =>
    (await apiClient.post<Assessment>(`/api/submissions/${submissionId}/assess?force_reassess=${force}`)).data,
  approve: async (assessmentId: number, faculty_notes?: string) =>
    (await apiClient.post<Assessment>(`/api/assessments/${assessmentId}/approve`, { faculty_notes })).data,
  modify: async (assessmentId: number, final_score: number, faculty_notes?: string) =>
    (await apiClient.put<Assessment>(`/api/assessments/${assessmentId}`, { final_score, faculty_notes })).data
};
