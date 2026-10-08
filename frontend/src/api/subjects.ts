import { apiClient } from "./client";
import type { Assignment, CourseMaterial, Subject } from "../types/api";

export const subjectsApi = {
  list: async () => (await apiClient.get<Subject[]>("/api/subjects")).data,
  get: async (subjectId: number) => (await apiClient.get<Subject>(`/api/subjects/${subjectId}`)).data,
  create: async (payload: { name: string; code: string; description?: string }) =>
    (await apiClient.post<Subject>("/api/subjects", payload)).data,
  update: async (subjectId: number, payload: { name?: string; description?: string }) =>
    (await apiClient.put<Subject>(`/api/subjects/${subjectId}`, payload)).data,
  remove: async (subjectId: number) => apiClient.delete(`/api/subjects/${subjectId}`),
  enroll: async (subjectId: number) => (await apiClient.post(`/api/subjects/${subjectId}/enroll`)).data,
  assignments: async (subjectId: number) =>
    (await apiClient.get<Assignment[]>(`/api/subjects/${subjectId}/assignments`)).data,
  materials: async (subjectId: number) =>
    (await apiClient.get<CourseMaterial[]>(`/api/subjects/${subjectId}/materials`)).data,
  uploadMaterial: async (subjectId: number, payload: FormData) =>
    (
      await apiClient.post<CourseMaterial>(`/api/subjects/${subjectId}/materials`, payload, {
        headers: { "Content-Type": "multipart/form-data" }
      })
    ).data
};
