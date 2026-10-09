import { apiClient } from "./client";
import type { CourseMaterial } from "../types/api";

export const materialsApi = {
  get: async (materialId: number) => (await apiClient.get<CourseMaterial>(`/materials/${materialId}`)).data,
  process: async (materialId: number) =>
    (await apiClient.post<CourseMaterial>(`/materials/${materialId}/process`)).data,
  remove: async (materialId: number) => apiClient.delete(`/materials/${materialId}`)
};
