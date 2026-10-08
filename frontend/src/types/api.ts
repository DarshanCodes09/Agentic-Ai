export type UserRole = "STUDENT" | "FACULTY";

export interface UserBrief {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface Subject {
  id: number;
  name: string;
  code: string;
  description: string | null;
  faculty_id: number;
  faculty?: UserBrief | null;
  created_at: string;
  updated_at: string;
}

export interface Assignment {
  id: number;
  subject_id: number;
  title: string;
  description: string | null;
  instructions: string | null;
  due_date: string;
  max_marks: number;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface Question {
  id: number;
  assignment_id: number;
  question_number: number;
  question_text: string;
  marks: number;
  expected_concepts: string[] | null;
  created_at: string;
}

export interface RubricItem {
  id: number;
  rubric_id: number;
  criterion: string;
  description: string | null;
  max_marks: number;
  created_at: string;
}

export interface Rubric {
  id: number;
  assignment_id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  items: RubricItem[];
}

export type SubmissionStatus = "SUBMITTED" | "EVALUATED" | "LATE" | "DRAFT";

export interface Submission {
  id: number;
  assignment_id: number;
  student_id: number;
  submission_text: string | null;
  file_path: string | null;
  original_filename: string | null;
  submitted_at: string;
  status: SubmissionStatus;
  created_at: string;
  updated_at: string;
  student?: UserBrief | null;
}

export type AssessmentStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "APPROVED" | "MODIFIED";

export interface CriterionEvaluation {
  rubric_item_id?: number | null;
  criterion: string;
  score: number;
  max_marks: number;
  reasoning: string;
}

export interface ConceptMasteryItem {
  concept: string;
  mastery_level: string;
  evidence: string;
}

export interface AssessmentFeedback {
  id: number;
  summary: string;
  detailed_feedback: string | null;
  actionable_steps: string[];
  suggested_topics: string[];
  created_at: string;
  updated_at: string;
}

export interface Assessment {
  id: number;
  submission_id: number;
  ai_score: number;
  final_score: number;
  max_score: number;
  status: AssessmentStatus;
  criteria_scores: CriterionEvaluation[];
  concept_mastery: ConceptMasteryItem[];
  retrieved_context: Record<string, unknown>[];
  strengths: string[];
  weaknesses: string[];
  faculty_notes: string | null;
  model_name: string | null;
  feedback: AssessmentFeedback | null;
  created_at: string;
  updated_at: string;
}

export interface CourseMaterial {
  id: number;
  subject_id: number;
  uploaded_by: number;
  title: string;
  original_filename: string;
  stored_filename: string;
  file_type: string;
  file_size: number;
  processing_status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  created_at: string;
  updated_at: string;
}

export interface StudentOverallAnalytics {
  student_id: number;
  total_assessments_evaluated: number;
  total_marks_obtained: number;
  total_max_marks: number;
  overall_percentage: number;
  average_score: number;
  average_confidence: number | null;
  enrolled_subjects_count: number;
  strongest_concepts: ConceptMasterySummary[];
  weakest_concepts: ConceptMasterySummary[];
}

export interface ConceptMasterySummary {
  concept: string;
  assessment_count: number;
  mastery_score: number;
  mastery_level: string;
  supporting_evidence: string[];
}

export interface LearningGap {
  concept: string;
  subject_id: number | null;
  subject_name: string | null;
  severity: string;
  mastery_score: number;
  evidence: string[];
  occurrence_count: number;
}

export interface PerformanceTrend {
  assessment_id: number;
  assignment_id: number;
  assignment_title: string;
  subject_id: number;
  subject_name: string;
  score: number;
  max_score: number;
  percentage: number;
  evaluated_at: string;
}

export interface SubjectPerformance {
  subject_id: number;
  subject_name: string;
  subject_code: string;
  assessments_count: number;
  total_score: number;
  total_max_score: number;
  percentage: number;
  average_score: number;
}

export interface FacultySubjectAnalytics {
  subject_id: number;
  subject_name: string;
  subject_code: string;
  enrolled_student_count: number;
  students_with_submissions: number;
  evaluated_submissions_count: number;
  total_submissions_count: number;
  assignment_count: number;
  average_score: number;
  average_percentage: number;
  highest_percentage: number;
  lowest_percentage: number;
  median_percentage: number;
  completion_rate: number;
  performance_distribution: Record<string, number>;
  strong_concepts: string[];
  weak_concepts: string[];
}

export interface AssignmentAnalytics {
  assignment_id: number;
  assignment_title: string;
  subject_id: number;
  subject_name: string;
  max_marks: number;
  enrolled_count: number;
  submission_count: number;
  evaluated_count: number;
  average_score: number;
  average_percentage: number;
  highest_score: number;
  lowest_score: number;
  completion_rate: number;
}

export interface ClassConceptAnalytics {
  concept: string;
  average_mastery: number;
  mastery_level: string;
  assessed_student_count: number;
  total_occurrences: number;
}

export interface ClassLearningGap {
  concept: string;
  average_mastery: number;
  affected_student_count: number;
  total_occurrences: number;
  severity: string;
  sample_evidence: string[];
}
