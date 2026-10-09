import { apiClient } from "./client";
import type { Assignment, CourseMaterial, Enrollment, Subject } from "../types/api";

export const subjectsApi = {
  list: async () => (await apiClient.get<Subject[]>("/subjects")).data,
  available: async () => (await apiClient.get<Subject[]>("/subjects/available")).data,
  get: async (subjectId: number) => (await apiClient.get<Subject>(`/subjects/${subjectId}`)).data,
  create: async (payload: { name: string; code: string; description?: string }) =>
    (await apiClient.post<Subject>("/subjects", payload)).data,
  update: async (subjectId: number, payload: { name?: string; description?: string }) =>
    (await apiClient.put<Subject>(`/subjects/${subjectId}`, payload)).data,
  remove: async (subjectId: number) => apiClient.delete(`/subjects/${subjectId}`),
  enroll: async (subjectId: number) => (await apiClient.post(`/subjects/${subjectId}/enroll`)).data,
  joinByCode: async (courseCode: string) =>
    (await apiClient.post<Enrollment>("/enrollments/join", { course_code: courseCode })).data,
  assignments: async (subjectId: number) =>
    (await apiClient.get<Assignment[]>(`/subjects/${subjectId}/assignments`)).data,
  materials: async (subjectId: number) =>
    (await apiClient.get<CourseMaterial[]>(`/subjects/${subjectId}/materials`)).data,
  uploadMaterial: async (subjectId: number, payload: FormData) =>
    (
      await apiClient.post<CourseMaterial>(`/subjects/${subjectId}/materials`, payload, {
        headers: { "Content-Type": "multipart/form-data" }
      })
    ).data
};
