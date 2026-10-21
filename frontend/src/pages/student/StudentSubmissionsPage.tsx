import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { submissionsApi } from "../../api/submissions";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Field, Textarea } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";
import type { Submission } from "../../types/api";

export function StudentSubmissionsPage() {
  const submissions = useAsync(submissionsApi.listMine, []);

  // Replace submission modal state
  const [replacingSubmission, setReplacingSubmission] = useState<Submission | null>(null);
  const [replaceText, setReplaceText] = useState("");
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const [replaceError, setReplaceError] = useState("");
  const [replaceLoading, setReplaceLoading] = useState(false);

  // Withdraw submission modal state
  const [withdrawingSubmission, setWithdrawingSubmission] = useState<Submission | null>(null);
  const [withdrawError, setWithdrawError] = useState("");
  const [withdrawLoading, setWithdrawLoading] = useState(false);

  function startReplace(sub: Submission) {
    setReplacingSubmission(sub);
    setReplaceText(sub.submission_text || "");
    setReplaceFile(null);
    setReplaceError("");
  }

  async function handleReplaceSubmit(e: FormEvent) {
    e.preventDefault();
    if (!replacingSubmission) return;
    if (!replaceText.trim() && !replaceFile) {
      setReplaceError("Please provide updated answer text or choose an updated file.");
      return;
    }

    setReplaceLoading(true);
    setReplaceError("");
    try {
      const form = new FormData();
      if (replaceText.trim()) form.append("submission_text", replaceText.trim());
      if (replaceFile) form.append("file", replaceFile);

      await submissionsApi.replace(replacingSubmission.id, form);
      setReplacingSubmission(null);
      submissions.refetch();
    } catch (err) {
      setReplaceError(getApiErrorMessage(err));
    } finally {
      setReplaceLoading(false);
    }
  }

  async function handleWithdrawConfirm() {
    if (!withdrawingSubmission) return;
    setWithdrawLoading(true);
    setWithdrawError("");
    try {
      await submissionsApi.withdraw(withdrawingSubmission.id);
      setWithdrawingSubmission(null);
      submissions.refetch();
    } catch (err) {
      setWithdrawError(getApiErrorMessage(err));
    } finally {
      setWithdrawLoading(false);
    }
  }

  if (submissions.loading) return <LoadingState label="Loading submissions" />;
  if (submissions.error) return <ErrorState message={submissions.error} onRetry={submissions.refetch} />;

  return (
    <>
      <PageHeader
        title="My Submissions"
        eyebrow="Academic History"
        description="Track submitted work, view finalized grades and rubrics, or replace/withdraw work before assignment deadlines."
      />

      {submissions.data?.length ? (
        <Table
          columns={["Assignment", "Submitted At", "Content", "Status", "Actions"]}
          rows={submissions.data.map((submission) => [
            <div>
              <span className="font-semibold text-ink">Assignment #{submission.assignment_id}</span>
            </div>,
            formatDate(submission.submitted_at),
            submission.original_filename ? (
              <span className="text-xs text-muted">File: {submission.original_filename}</span>
            ) : (
              <span className="text-xs text-muted">Text answer</span>
            ),
            <Badge tone={statusTone(submission.status)}>{submission.status}</Badge>,
            <div className="flex items-center gap-2">
              <Link
                className="font-medium underline hover:text-ink text-xs"
                to={`/student/submissions/${submission.id}/assessment`}
              >
                View Assessment
              </Link>
              {submission.status === "SUBMITTED" && (
                <>
                  <button
                    type="button"
                    onClick={() => startReplace(submission)}
                    className="rounded px-2 py-0.5 text-xs font-medium text-ink hover:bg-stone-100"
                  >
                    Replace
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setWithdrawingSubmission(submission);
                      setWithdrawError("");
                    }}
                    className="rounded px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50"
                  >
                    Withdraw
                  </button>
                </>
              )}
            </div>,
          ])}
        />
      ) : (
        <EmptyState title="No submissions yet." body="You have not submitted any assignments yet." />
      )}

      {/* Replace Submission Modal */}
      <Modal
        isOpen={!!replacingSubmission}
        onClose={() => setReplacingSubmission(null)}
        title="Replace submission"
        description="Submit updated work before the assignment deadline. Any pending draft AI evaluation will be cleared for reassessment."
      >
        <form onSubmit={handleReplaceSubmit} className="space-y-4">
          <Field label="Updated text answer">
            <Textarea
              placeholder="Paste or type your revised answer..."
              value={replaceText}
              onChange={(e) => setReplaceText(e.target.value)}
            />
          </Field>
          <Field
            label="Upload revised PDF or DOCX (optional)"
            hint={replaceFile ? `Selected: ${replaceFile.name}` : undefined}
          >
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setReplaceFile(e.target.files?.[0] ?? null)}
              className="focus-ring w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
            />
          </Field>

          {replaceError ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-2.5 text-xs text-red-800">
              {replaceError}
            </div>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setReplacingSubmission(null)}>
              Cancel
            </Button>
            <Button disabled={replaceLoading}>
              {replaceLoading ? "Uploading..." : "Confirm Replacement"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Withdraw Submission Modal */}
      <Modal
        isOpen={!!withdrawingSubmission}
        onClose={() => setWithdrawingSubmission(null)}
        title="Withdraw submission?"
        description="Withdrawing will completely remove your submission. You will need to submit your work again before the deadline to receive a grade."
      >
        <div className="space-y-4">
          {withdrawError ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-2.5 text-xs text-red-800">
              {withdrawError}
            </div>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setWithdrawingSubmission(null)}>
              Cancel
            </Button>
            <Button variant="danger" disabled={withdrawLoading} onClick={handleWithdrawConfirm}>
              {withdrawLoading ? "Withdrawing..." : "Confirm Withdrawal"}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
