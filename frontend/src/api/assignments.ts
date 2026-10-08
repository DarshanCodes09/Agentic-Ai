import { apiClient } from "./client";
import type { Assignment, Question, Rubric, Submission } from "../types/api";

export const assignmentsApi = {
  get: async (assignmentId: number) => (await apiClient.get<Assignment>(`/api/assignments/${assignmentId}`)).data,
  create: async (
    subjectId: number,
    payload: { title: string; description?: string; instructions?: string; due_date: string; max_marks: number }
  ) => (await apiClient.post<Assignment>(`/api/subjects/${subjectId}/assignments`, payload)).data,
  questions: async (assignmentId: number) =>
    (await apiClient.get<Question[]>(`/api/assignments/${assignmentId}/questions`)).data,
  addQuestion: async (
    assignmentId: number,
    payload: { question_number: number; question_text: string; marks: number; expected_concepts?: string[] }
  ) => (await apiClient.post<Question>(`/api/assignments/${assignmentId}/questions`, payload)).data,
  rubric: async (assignmentId: number) => (await apiClient.get<Rubric>(`/api/assignments/${assignmentId}/rubric`)).data,
  createRubric: async (
    assignmentId: number,
    payload: { name: string; description?: string; items?: { criterion: string; description?: string; max_marks: number }[] }
  ) => (await apiClient.post<Rubric>(`/api/assignments/${assignmentId}/rubric`, payload)).data,
  submit: async (assignmentId: number, payload: FormData | { submission_text: string }) =>
    (
      await apiClient.post<Submission>(`/api/assignments/${assignmentId}/submit`, payload, {
        headers: payload instanceof FormData ? { "Content-Type": "multipart/form-data" } : undefined
      })
    ).data,
  submissions: async (assignmentId: number) =>
    (await apiClient.get<Submission[]>(`/api/assignments/${assignmentId}/submissions`)).data
};
