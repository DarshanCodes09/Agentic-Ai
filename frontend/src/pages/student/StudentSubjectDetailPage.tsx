import { Link, useParams } from "react-router-dom";
import { downloadOrPreviewFile } from "../../api/files";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Card, CardTitle } from "../../components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";

export function StudentSubjectDetailPage() {
  const subjectId = Number(useParams().subjectId);
  const subject = useAsync(() => subjectsApi.get(subjectId), [subjectId]);
  const assignments = useAsync(() => subjectsApi.assignments(subjectId), [subjectId]);
  const materials = useAsync(() => subjectsApi.materials(subjectId), [subjectId]);

  if (subject.loading) return <LoadingState label="Loading subject" />;
  if (subject.error) return <ErrorState message={subject.error} onRetry={subject.refetch} />;

  return (
    <>
      <PageHeader
        title={subject.data?.name ?? "Subject"}
        eyebrow={subject.data?.code}
        description={subject.data?.description ?? undefined}
      />
      <div className="space-y-6">
        <Card>
          <CardTitle>Assignments</CardTitle>
          <div className="mt-4">
            {assignments.loading ? (
              <LoadingState />
            ) : assignments.data?.length ? (
              <Table
                columns={["Assignment", "Due", "Marks", "Status"]}
                rows={assignments.data.map((assignment) => [
                  <Link
                    key={assignment.id}
                    className="font-medium underline hover:text-ink"
                    to={`/student/assignments/${assignment.id}`}
                  >
                    {assignment.title}
                  </Link>,
                  formatDate(assignment.due_date),
                  assignment.max_marks,
                  <Badge tone="success">Open</Badge>,
                ])}
              />
            ) : (
              <EmptyState title="No assignments yet." />
            )}
          </div>
        </Card>

        <Card>
          <CardTitle>Course Materials & Reference Documents</CardTitle>
          <div className="mt-4">
            {materials.loading ? (
              <LoadingState />
            ) : materials.data?.length ? (
              <Table
                columns={["Title", "Filename", "Uploaded", "Actions"]}
                rows={materials.data.map((item) => [
                  item.title,
                  item.original_filename,
                  formatDate(item.created_at),
                  <div key={item.id} className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        downloadOrPreviewFile(
                          `/materials/${item.id}/file`,
                          item.original_filename,
                          true
                        )
                      }
                      className="cursor-pointer text-xs font-medium underline hover:text-ink"
                    >
                      Preview
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        downloadOrPreviewFile(
                          `/materials/${item.id}/file`,
                          item.original_filename,
                          false
                        )
                      }
                      className="cursor-pointer text-xs font-medium underline hover:text-ink"
                    >
                      Download
                    </button>
                  </div>,
                ])}
              />
            ) : (
              <EmptyState title="No course materials uploaded yet." />
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
