import { Link, useParams } from "react-router-dom";
import { assignmentsApi } from "../../api/assignments";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";

export function StudentAssignmentPage() {
  const assignmentId = Number(useParams().assignmentId);
  const assignment = useAsync(() => assignmentsApi.get(assignmentId), [assignmentId]);
  const questions = useAsync(() => assignmentsApi.questions(assignmentId), [assignmentId]);
  const rubric = useAsync(() => assignmentsApi.rubric(assignmentId), [assignmentId]);
  if (assignment.loading) return <LoadingState label="Loading assignment" />;
  if (assignment.error) return <ErrorState message={assignment.error} onRetry={assignment.refetch} />;
  const item = assignment.data;
  return item ? (
    <>
      <PageHeader
        title={item.title}
        eyebrow={`Due ${formatDate(item.due_date)}`}
        description={item.description ?? undefined}
        actions={<Link to={`/student/assignments/${item.id}/submit`}><Button>Submit work</Button></Link>}
      />
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardTitle>Instructions</CardTitle>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted">{item.instructions ?? "No additional instructions."}</p>
          <p className="mt-6 text-sm font-medium">Maximum marks: {item.max_marks}</p>
        </Card>
        <Card>
          <CardTitle>Rubric</CardTitle>
          {rubric.loading ? <LoadingState /> : rubric.data ? (
            <div className="mt-4 space-y-3">
              <p className="font-medium">{rubric.data.name}</p>
              {rubric.data.items.map((rubricItem) => <div key={rubricItem.id} className="rounded-md border border-line p-3 text-sm"><b>{rubricItem.criterion}</b><p className="text-muted">{rubricItem.description}</p><Badge>{rubricItem.max_marks} marks</Badge></div>)}
            </div>
          ) : <EmptyState title="No rubric attached." />}
        </Card>
        <Card className="lg:col-span-2">
          <CardTitle>Questions</CardTitle>
          {questions.loading ? <LoadingState /> : questions.data?.length ? (
            <Table columns={["#", "Question", "Marks", "Concepts"]} rows={questions.data.map((q) => [q.question_number, q.question_text, q.marks, q.expected_concepts?.join(", ") ?? "None"])} />
          ) : <EmptyState title="No questions yet." />}
        </Card>
      </div>
    </>
  ) : null;
}
