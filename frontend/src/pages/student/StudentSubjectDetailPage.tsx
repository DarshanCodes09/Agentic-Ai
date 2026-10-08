import { Link, useParams } from "react-router-dom";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";

export function StudentSubjectDetailPage() {
  const subjectId = Number(useParams().subjectId);
  const subject = useAsync(() => subjectsApi.get(subjectId), [subjectId]);
  const assignments = useAsync(() => subjectsApi.assignments(subjectId), [subjectId]);
  if (subject.loading) return <LoadingState label="Loading subject" />;
  if (subject.error) return <ErrorState message={subject.error} onRetry={subject.refetch} />;
  return (
    <>
      <PageHeader title={subject.data?.name ?? "Subject"} eyebrow={subject.data?.code} description={subject.data?.description ?? undefined} />
      <Card>
        <h2 className="mb-4 text-lg font-semibold">Assignments</h2>
        {assignments.loading ? <LoadingState /> : assignments.data?.length ? (
          <Table
            columns={["Assignment", "Due", "Marks", "Status"]}
            rows={assignments.data.map((assignment) => [
              <Link className="font-medium underline" to={`/student/assignments/${assignment.id}`}>{assignment.title}</Link>,
              formatDate(assignment.due_date),
              assignment.max_marks,
              <Badge>Open</Badge>
            ])}
          />
        ) : <EmptyState title="No assignments yet." />}
      </Card>
    </>
  );
}
