import { apiClient } from "./client";
import type { Submission, SubmissionManifest } from "../types/api";

export const submissionsApi = {
  listMine: async () => (await apiClient.get<Submission[]>("/submissions")).data,
  get: async (submissionId: number) => (await apiClient.get<Submission>(`/submissions/${submissionId}`)).data,
  getManifest: async (submissionId: number) =>
    (await apiClient.get<SubmissionManifest>(`/submissions/${submissionId}/manifest`)).data,
  replace: async (submissionId: number, payload: FormData | { submission_text: string }) =>
    (
      await apiClient.put<Submission>(`/submissions/${submissionId}`, payload, {
        headers: payload instanceof FormData ? { "Content-Type": "multipart/form-data" } : undefined
      })
    ).data,
  withdraw: async (submissionId: number) => apiClient.delete(`/submissions/${submissionId}`)
};
