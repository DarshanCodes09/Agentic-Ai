import { Link } from "react-router-dom";
import { submissionsApi } from "../../api/submissions";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge, statusTone } from "../../components/ui/Badge";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";

export function StudentSubmissionsPage() {
  const submissions = useAsync(submissionsApi.listMine, []);
  if (submissions.loading) return <LoadingState label="Loading submissions" />;
  if (submissions.error) return <ErrorState message={submissions.error} onRetry={submissions.refetch} />;
  return (
    <>
      <PageHeader title="Submissions" eyebrow="Submitted work" description="Track submitted work and open faculty-reviewed assessment details." />
      {submissions.data?.length ? (
        <Table columns={["Assignment", "Submitted", "File", "Status", "Assessment"]} rows={submissions.data.map((submission) => [
          `#${submission.assignment_id}`,
          formatDate(submission.submitted_at),
          submission.original_filename ?? "Text response",
          <Badge tone={statusTone(submission.status)}>{submission.status}</Badge>,
          <Link className="font-medium underline" to={`/student/submissions/${submission.id}/assessment`}>Open</Link>
        ])} />
      ) : <EmptyState title="No submissions yet." />}
    </>
  );
}
