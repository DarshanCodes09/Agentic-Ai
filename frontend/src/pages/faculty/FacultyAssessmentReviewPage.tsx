import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { assessmentsApi } from "../../api/assessments";
import { getApiErrorMessage } from "../../api/client";
import { downloadOrPreviewFile } from "../../api/files";
import { submissionsApi } from "../../api/submissions";

import { PageHeader } from "../../components/common/PageHeader";
import { ScoreDisplay } from "../../components/common/ScoreDisplay";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Input, Textarea } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";

export function FacultyAssessmentReviewPage() {
  const submissionId = Number(useParams().submissionId);
  const submission = useAsync(() => submissionsApi.get(submissionId), [submissionId]);
  const assessment = useAsync(() => assessmentsApi.getBySubmission(submissionId), [submissionId]);
  const [finalScore, setFinalScore] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [reassessModalOpen, setReassessModalOpen] = useState(false);
  const [reassessLoading, setReassessLoading] = useState(false);

  async function trigger() {
    setError("");
    try {
      await assessmentsApi.trigger(submissionId);
      assessment.refetch();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  }

  async function executeReassessment() {
    setReassessLoading(true);
    setError("");
    try {
      await assessmentsApi.trigger(submissionId, true);
      setReassessModalOpen(false);
      assessment.refetch();
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setReassessLoading(false);
    }
  }

  async function approve() {
    if (!assessment.data) return;
    await assessmentsApi.approve(assessment.data.id, notes || undefined);
    assessment.refetch();
  }

  async function modify(event: FormEvent) {
    event.preventDefault();
    if (!assessment.data) return;
    await assessmentsApi.modify(assessment.data.id, Number(finalScore), notes || undefined);
    assessment.refetch();
  }

  if (submission.loading) return <LoadingState label="Loading review" />;
  if (submission.error) return <ErrorState message={submission.error} onRetry={submission.refetch} />;
  const data = assessment.data;
  return (
    <>
      <PageHeader title="Human review" eyebrow={submission.data?.student?.full_name ?? `Submission #${submissionId}`} description="AI supports the review process. Faculty approval or modification determines the final academic grade." />
      {error ? <ErrorState message={error} /> : null}
      {assessment.error ? (
        <Card>
          <EmptyState title="No AI assessment yet." body="Trigger assessment to generate advisory scoring and feedback." />
          <div className="mt-5"><Button onClick={trigger}>Run AI assessment</Button></div>
        </Card>
      ) : data ? (
        <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
          <Card>
            <ScoreDisplay value={data.ai_score} max={data.max_score} label="AI suggested score" />
            <div className="mt-6 border-t border-line pt-5"><ScoreDisplay value={data.final_score} max={data.max_score} label="Final faculty score" /></div>
            <div className="mt-5"><Badge tone={statusTone(data.status)}>{data.status}</Badge></div>
          </Card>
          <Card>
            <CardTitle>Faculty decision</CardTitle>
            <form onSubmit={modify} className="mt-4 space-y-4">
              <Field label="Final score"><Input type="number" min={0} max={data.max_score} step="0.1" value={finalScore} onChange={(e) => setFinalScore(e.target.value)} placeholder={String(data.ai_score)} /></Field>
              <Field label="Faculty notes"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={approve}>Approve AI score</Button>
                <Button variant="secondary" type="submit">Save modified score</Button>
                <Button variant="ghost" type="button" onClick={() => setReassessModalOpen(true)}>Re-run assessment</Button>
              </div>
            </form>
          </Card>
          <Card className="lg:col-span-2">
            <CardTitle>Submission</CardTitle>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted">{submission.data?.submission_text ?? "File submission only."}</p>
            {submission.data?.original_filename ? (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-stone-50/70 p-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold uppercase text-muted">Submitted File:</span>
                  <span className="text-sm font-medium text-ink">{submission.data.original_filename}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    className="text-xs"
                    onClick={() =>
                      downloadOrPreviewFile(
                        `/submissions/${submissionId}/file`,
                        submission.data?.original_filename ?? "submission.pdf",
                        true
                      )
                    }
                  >
                    Preview File
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    className="text-xs"
                    onClick={() =>
                      downloadOrPreviewFile(
                        `/submissions/${submissionId}/file`,
                        submission.data?.original_filename ?? "submission.pdf",
                        false
                      )
                    }
                  >
                    Download File
                  </Button>
                </div>
              </div>
            ) : null}
          </Card>

          <Card>
            <CardTitle>Reasoning and feedback</CardTitle>
            <p className="mt-3 text-sm leading-6 text-muted">{data.feedback?.summary}</p>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{data.feedback?.detailed_feedback}</p>
          </Card>
          <Card>
            <CardTitle>Strengths and areas to improve</CardTitle>
            <div className="mt-3 text-sm"><b>Strengths</b><ul className="mt-2 list-disc pl-5 text-muted">{data.strengths.map((item) => <li key={item}>{item}</li>)}</ul><b className="mt-4 block">Areas to improve</b><ul className="mt-2 list-disc pl-5 text-muted">{data.weaknesses.map((item) => <li key={item}>{item}</li>)}</ul></div>
          </Card>
          <Card className="lg:col-span-2">
            <CardTitle>Criteria scores</CardTitle>
            <div className="mt-4"><Table columns={["Criterion", "Score", "Reasoning"]} rows={data.criteria_scores.map((item) => [item.criterion, `${item.score} / ${item.max_marks}`, item.reasoning])} /></div>
          </Card>
        </div>
      ) : <LoadingState />}

      {/* Reassessment Confirmation Modal */}
      <Modal
        isOpen={reassessModalOpen}
        onClose={() => setReassessModalOpen(false)}
        title="Confirm Reassessment?"
        description="An evaluation already exists for this submission. Re-running will recalculate scores and feedback using the AI evaluation pipeline. The result will return to COMPLETED status and require your review and approval before release to the student."
      >
        <div className="space-y-4">
          {data ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <p className="font-semibold">Note on Existing Assessment</p>
              <p className="mt-1">
                Current evaluation (Score: {data.final_score} / {data.max_score}, status: {data.status}) will be overwritten with freshly generated AI scores.
              </p>
            </div>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setReassessModalOpen(false)}>
              Cancel
            </Button>
            <Button disabled={reassessLoading} onClick={executeReassessment}>
              {reassessLoading ? "Reassessing..." : "Confirm & Re-evaluate"}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
