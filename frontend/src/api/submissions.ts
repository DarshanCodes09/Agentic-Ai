import { apiClient } from "./client";
import type { Submission } from "../types/api";

export const submissionsApi = {
  listMine: async () => (await apiClient.get<Submission[]>("/submissions")).data,
  get: async (submissionId: number) => (await apiClient.get<Submission>(`/submissions/${submissionId}`)).data
};
