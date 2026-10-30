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
  const manifest = useAsync(() => submissionsApi.getManifest(submissionId), [submissionId]);
  const [finalScore, setFinalScore] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [reassessModalOpen, setReassessModalOpen] = useState(false);
  const [reassessLoading, setReassessLoading] = useState(false);

  function getExecutionTone(status?: string): "positive" | "attention" | "critical" | "neutral" {
    switch (status) {
      case "COMPLETE":
        return "positive";
      case "PARTIAL":
        return "attention";
      case "ERRORED":
        return "critical";
      default:
        return "neutral";
    }
  }

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
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle>Submission & Deliverables</CardTitle>
              {manifest.data?.file_format && (
                <span className="rounded bg-stone-100 px-2 py-0.5 font-mono text-xs font-semibold text-ink">
                  {manifest.data.file_format}
                </span>
              )}
            </div>

            {submission.data?.submission_text && (
              <div className="mt-3 rounded-md bg-stone-50 p-3 text-sm leading-6 text-ink">
                <span className="mb-1 block text-xs font-semibold uppercase text-muted">Student Answer / Notes</span>
                <p className="whitespace-pre-wrap">{submission.data.submission_text}</p>
              </div>
            )}

            {submission.data?.original_filename ? (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-stone-50/70 p-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold uppercase text-muted">Submitted File:</span>
                  <span className="text-sm font-medium text-ink">{submission.data.original_filename}</span>
                  {manifest.data?.file_size && (
                    <span className="text-xs text-muted">({(manifest.data.file_size / 1024).toFixed(1)} KB)</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    className="text-xs"
                    onClick={() =>
                      downloadOrPreviewFile(
                        `/submissions/${submissionId}/file`,
                        submission.data?.original_filename ?? "submission",
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
                        submission.data?.original_filename ?? "submission",
                        false
                      )
                    }
                  >
                    Download File
                  </Button>
                </div>
              </div>
            ) : null}

            {/* Notebook Execution Audit */}
            {manifest.data?.execution_audit && (
              <div className="mt-5 rounded-md border border-line p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">
                    Jupyter Notebook Execution Audit
                  </h4>
                  <Badge tone={getExecutionTone(manifest.data.execution_audit.execution_status)}>
                    {manifest.data.execution_audit.execution_status}
                  </Badge>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded border border-line/60 bg-stone-50/50 p-2.5">
                    <span className="text-[11px] font-medium text-muted">Total Cells</span>
                    <p className="text-base font-semibold text-ink">{manifest.data.execution_audit.total_cells}</p>
                  </div>
                  <div className="rounded border border-line/60 bg-stone-50/50 p-2.5">
                    <span className="text-[11px] font-medium text-muted">Executed Code Cells</span>
                    <p className="text-base font-semibold text-emerald-700">
                      {manifest.data.execution_audit.executed_code_cells} / {manifest.data.execution_audit.code_cells}
                    </p>
                  </div>
                  <div className="rounded border border-line/60 bg-stone-50/50 p-2.5">
                    <span className="text-[11px] font-medium text-muted">Unexecuted Cells</span>
                    <p className={`text-base font-semibold ${manifest.data.execution_audit.unexecuted_code_cells > 0 ? "text-amber-700" : "text-ink"}`}>
                      {manifest.data.execution_audit.unexecuted_code_cells}
                    </p>
                  </div>
                  <div className="rounded border border-line/60 bg-stone-50/50 p-2.5">
                    <span className="text-[11px] font-medium text-muted">Cell Runtime Errors</span>
                    <p className={`text-base font-semibold ${manifest.data.execution_audit.cells_with_errors > 0 ? "text-red-700" : "text-ink"}`}>
                      {manifest.data.execution_audit.cells_with_errors}
                    </p>
                  </div>
                </div>

                {manifest.data.execution_audit.execution_order_anomaly && (
                  <p className="mt-2.5 text-xs text-amber-700">
                    ⚠️ Cell execution counts are non-linear or out of order. Saved output evidence may reflect an older or partial run.
                  </p>
                )}
                {manifest.data.execution_audit.cells_with_errors > 0 && (
                  <p className="mt-1 text-xs text-red-700">
                    ⚠️ Runtime error traces were found in saved cell outputs and flagged to the AI evaluator.
                  </p>
                )}
              </div>
            )}

            {/* Project Archive File Manifest */}
            {manifest.data?.file_manifest?.files?.length ? (
              <div className="mt-5">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">
                    Project Archive File Manifest ({manifest.data.file_manifest.total_files} files)
                  </h4>
                  <div className="flex gap-2 text-xs">
                    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${manifest.data.file_manifest.has_readme ? "bg-emerald-50 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>
                      README: {manifest.data.file_manifest.has_readme ? "✓" : "✗"}
                    </span>
                    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${manifest.data.file_manifest.has_tests ? "bg-emerald-50 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>
                      Tests: {manifest.data.file_manifest.has_tests ? "✓" : "✗"}
                    </span>
                    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${manifest.data.file_manifest.has_manifest ? "bg-emerald-50 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>
                      Manifest: {manifest.data.file_manifest.has_manifest ? "✓" : "✗"}
                    </span>
                  </div>
                </div>

                <div className="max-h-72 overflow-y-auto rounded-md border border-line">
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 border-b border-line bg-stone-50 text-muted">
                      <tr>
                        <th className="px-3 py-2 font-medium">Path</th>
                        <th className="px-3 py-2 font-medium">Category</th>
                        <th className="px-3 py-2 font-medium">Size</th>
                        <th className="px-3 py-2 font-medium text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line bg-white">
                      {manifest.data.file_manifest.files.map((file) => (
                        <tr key={file.rel_path} className="hover:bg-stone-50/50">
                          <td className="px-3 py-2 font-mono text-[11px] text-ink">{file.rel_path}</td>
                          <td className="px-3 py-2">
                            <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] font-medium text-ink">
                              {file.category}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-muted">{(file.size / 1024).toFixed(1)} KB</td>
                          <td className="px-3 py-2 text-right">
                            <div className="flex justify-end gap-1">
                              <button
                                type="button"
                                className="cursor-pointer rounded px-2 py-0.5 text-[11px] font-medium text-ink hover:bg-stone-100"
                                onClick={() =>
                                  downloadOrPreviewFile(
                                    `/submissions/${submissionId}/file`,
                                    file.rel_path.split("/").pop() || "file",
                                    true,
                                    { subpath: file.rel_path }
                                  )
                                }
                              >
                                Preview
                              </button>
                              <button
                                type="button"
                                className="cursor-pointer rounded px-2 py-0.5 text-[11px] font-medium text-muted hover:text-ink"
                                onClick={() =>
                                  downloadOrPreviewFile(
                                    `/submissions/${submissionId}/file`,
                                    file.rel_path.split("/").pop() || "file",
                                    false,
                                    { subpath: file.rel_path }
                                  )
                                }
                              >
                                Download
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
