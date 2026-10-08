import { apiClient } from "./client";
import type { Submission } from "../types/api";

export const submissionsApi = {
  listMine: async () => (await apiClient.get<Submission[]>("/api/submissions")).data,
  get: async (submissionId: number) => (await apiClient.get<Submission>(`/api/submissions/${submissionId}`)).data
};
