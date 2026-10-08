import { Link, useParams } from "react-router-dom";
import { assignmentsApi } from "../../api/assignments";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge, statusTone } from "../../components/ui/Badge";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";

export function FacultySubmissionsPage() {
  const assignmentId = Number(useParams().assignmentId);
  const assignment = useAsync(() => assignmentsApi.get(assignmentId), [assignmentId]);
  const submissions = useAsync(() => assignmentsApi.submissions(assignmentId), [assignmentId]);
  if (assignment.loading || submissions.loading) return <LoadingState label="Loading submissions" />;
  if (assignment.error) return <ErrorState message={assignment.error} onRetry={assignment.refetch} />;
  if (submissions.error) return <ErrorState message={submissions.error} onRetry={submissions.refetch} />;
  return (
    <>
      <PageHeader title={`${assignment.data?.title} submissions`} eyebrow="Faculty review" description="Open individual submissions to trigger or review AI assessment and finalize grades." />
      {submissions.data?.length ? <Table columns={["Student", "Submitted", "Status", "Score review"]} rows={submissions.data.map((submission) => [
        submission.student?.full_name ?? `Student #${submission.student_id}`,
        formatDate(submission.submitted_at),
        <Badge tone={statusTone(submission.status)}>{submission.status}</Badge>,
        <Link className="font-medium underline" to={`/faculty/submissions/${submission.id}/assessment`}>Open review</Link>
      ])} /> : <EmptyState title="No submissions yet." />}
    </>
  );
}
