import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { assessmentsApi } from "../../api/assessments";
import { getApiErrorMessage } from "../../api/client";
import { submissionsApi } from "../../api/submissions";
import { PageHeader } from "../../components/common/PageHeader";
import { ScoreDisplay } from "../../components/common/ScoreDisplay";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Input, Textarea } from "../../components/ui/Input";
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

  async function trigger() {
    setError("");
    try {
      await assessmentsApi.trigger(submissionId);
      assessment.refetch();
    } catch (err) {
      setError(getApiErrorMessage(err));
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
              <div className="flex flex-wrap gap-2"><Button type="button" onClick={approve}>Approve AI score</Button><Button variant="secondary" type="submit">Save modified score</Button><Button variant="ghost" type="button" onClick={trigger}>Re-run assessment</Button></div>
            </form>
          </Card>
          <Card className="lg:col-span-2">
            <CardTitle>Submission</CardTitle>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted">{submission.data?.submission_text ?? "File submission only."}</p>
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
    </>
  );
}
