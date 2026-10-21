import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { assignmentsApi } from "../../api/assignments";
import { assessmentsApi } from "../../api/assessments";
import { getApiErrorMessage } from "../../api/client";
import { downloadOrPreviewFile } from "../../api/files";
import { submissionsApi } from "../../api/submissions";
import { PageHeader } from "../../components/common/PageHeader";
import { ScoreDisplay } from "../../components/common/ScoreDisplay";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Textarea } from "../../components/ui/Input";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";

export function StudentSubmissionPage({ assessmentMode = false }: { assessmentMode?: boolean }) {
  const assignmentId = Number(useParams().assignmentId);
  const submissionId = Number(useParams().submissionId);
  if (assessmentMode) return <StudentAssessmentView submissionId={submissionId} />;

  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      if (text) form.append("submission_text", text);
      if (file) form.append("file", file);
      const submission = await assignmentsApi.submit(assignmentId, form);
      navigate(`/student/submissions/${submission.id}/assessment`);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Submit assignment"
        eyebrow="Student submission"
        description="Upload PDF/DOCX work, text answers, or both. Backend validation remains authoritative."
      />
      <form onSubmit={onSubmit} className="max-w-3xl space-y-5 rounded-lg border border-line bg-white p-6 shadow-soft">
        <Field label="Submission text">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste or type your answer..."
          />
        </Field>
        <Field
          label="PDF or DOCX upload"
          hint={file ? `Selected: ${file.name}` : "Accepted file types are validated by the backend."}
        >
          <input
            className="focus-ring w-full rounded-md border border-line bg-white px-3 py-2.5 text-sm"
            type="file"
            accept=".pdf,.docx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        <Button disabled={loading}>{loading ? "Submitting..." : "Submit work"}</Button>
      </form>
    </>
  );
}

function StudentAssessmentView({ submissionId }: { submissionId: number }) {
  const submission = useAsync(() => submissionsApi.get(submissionId), [submissionId]);
  const assessment = useAsync(() => assessmentsApi.getBySubmission(submissionId), [submissionId]);

  if (submission.loading || assessment.loading) return <LoadingState label="Loading assessment" />;
  if (submission.error) return <ErrorState message={submission.error} onRetry={submission.refetch} />;

  return (
    <>
      <PageHeader
        title="Assessment result"
        eyebrow="Official Faculty Evaluation"
        description="Academic score and personalized feedback finalized and released by your course faculty."
      />
      {assessment.error ? (
        <EmptyState
          title="Evaluation pending release"
          body={
            assessment.error ||
            "Your submission is recorded and currently under review. Evaluated grades and feedback will be published here once released by your instructor."
          }
        />
      ) : assessment.data ? (
        <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <Card>
            <ScoreDisplay
              value={assessment.data.final_score}
              max={assessment.data.max_score}
              label="Official grade"
            />
            <div className="mt-5">
              <Badge tone={statusTone(assessment.data.status)}>{assessment.data.status}</Badge>
            </div>
          </Card>

          <Card>
            <CardTitle>Instructor Feedback</CardTitle>
            <p className="mt-3 text-sm leading-6 text-muted">
              {assessment.data.feedback?.summary ?? "No feedback summary."}
            </p>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
              {assessment.data.feedback?.detailed_feedback}
            </p>
          </Card>

          {/* Student Submitted File Preview/Download */}
          {submission.data?.original_filename ? (
            <Card className="lg:col-span-2">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <span className="text-xs font-semibold uppercase text-muted">Submitted File</span>
                  <p className="text-sm font-medium text-ink">{submission.data.original_filename}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      downloadOrPreviewFile(
                        `/submissions/${submissionId}/file`,
                        submission.data?.original_filename ?? "submission.pdf",
                        true
                      )
                    }
                    className="cursor-pointer rounded border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink hover:bg-stone-50"
                  >
                    Preview File
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      downloadOrPreviewFile(
                        `/submissions/${submissionId}/file`,
                        submission.data?.original_filename ?? "submission.pdf",
                        false
                      )
                    }
                    className="cursor-pointer rounded bg-ink px-2.5 py-1 text-xs font-medium text-white hover:bg-ink/90"
                  >
                    Download File
                  </button>
                </div>
              </div>
            </Card>
          ) : null}

          {/* Rubric Criteria Breakdown */}
          {assessment.data.criteria_scores?.length ? (
            <Card className="lg:col-span-2">
              <CardTitle>Rubric Criteria Evaluation</CardTitle>
              <div className="mt-4">
                <Table
                  columns={["Criterion", "Score", "Reasoning"]}
                  rows={assessment.data.criteria_scores.map((item) => [
                    item.criterion,
                    `${item.score} / ${item.max_marks}`,
                    item.reasoning,
                  ])}
                />
              </div>
            </Card>
          ) : null}

          <Card>
            <CardTitle>Strengths</CardTitle>
            <List items={assessment.data.strengths} empty="No strengths listed." />
          </Card>

          <Card>
            <CardTitle>Areas for Improvement</CardTitle>
            <List items={assessment.data.weaknesses} empty="No weaknesses listed." />
          </Card>

          {assessment.data.concept_mastery?.length ? (
            <Card className="lg:col-span-2">
              <CardTitle>Concept Mastery</CardTitle>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {assessment.data.concept_mastery.map((item) => (
                  <div key={item.concept} className="rounded-md border border-line p-3">
                    <div className="flex justify-between gap-3">
                      <b>{item.concept}</b>
                      <Badge tone={statusTone(item.mastery_level)}>{item.mastery_level}</Badge>
                    </div>
                    <p className="mt-2 text-sm text-muted">{item.evidence}</p>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}

          <div className="lg:col-span-2">
            <Link className="text-sm font-medium underline hover:text-ink" to="/student/submissions">
              ← Back to submissions
            </Link>
          </div>
        </div>
      ) : null}
    </>
  );
}

function List({ items, empty }: { items: string[]; empty: string }) {
  return items.length ? (
    <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-muted">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  ) : (
    <EmptyState title={empty} />
  );
}
