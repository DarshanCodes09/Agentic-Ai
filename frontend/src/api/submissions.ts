import { apiClient } from "./client";
import type { Submission } from "../types/api";

export const submissionsApi = {
  listMine: async () => (await apiClient.get<Submission[]>("/submissions")).data,
  get: async (submissionId: number) => (await apiClient.get<Submission>(`/submissions/${submissionId}`)).data,
  replace: async (submissionId: number, payload: FormData | { submission_text: string }) =>
    (
      await apiClient.put<Submission>(`/submissions/${submissionId}`, payload, {
        headers: payload instanceof FormData ? { "Content-Type": "multipart/form-data" } : undefined
      })
    ).data,
  withdraw: async (submissionId: number) => apiClient.delete(`/submissions/${submissionId}`)
};
