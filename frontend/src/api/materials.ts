import { apiClient } from "./client";
import type { CourseMaterial } from "../types/api";

export const materialsApi = {
  get: async (materialId: number) => (await apiClient.get<CourseMaterial>(`/materials/${materialId}`)).data,
  update: async (materialId: number, payload: { title: string }) =>
    (await apiClient.put<CourseMaterial>(`/materials/${materialId}`, payload)).data,
  process: async (materialId: number) =>
    (await apiClient.post<CourseMaterial>(`/materials/${materialId}/process`)).data,
  remove: async (materialId: number) => apiClient.delete(`/materials/${materialId}`)
};
