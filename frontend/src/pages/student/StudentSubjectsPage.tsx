import { useState } from "react";
import { Link } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { useAsync } from "../../hooks/useAsync";

export function StudentSubjectsPage() {
  const subjects = useAsync(subjectsApi.list, []);
  const available = useAsync(subjectsApi.available, []);
  const [joiningId, setJoiningId] = useState<number | null>(null);
  const [joinError, setJoinError] = useState("");

  async function enroll(subjectId: number) {
    setJoiningId(subjectId);
    setJoinError("");
    try {
      await subjectsApi.enroll(subjectId);
      subjects.refetch();
      available.refetch();
    } catch (err) {
      setJoinError(getApiErrorMessage(err));
    } finally {
      setJoiningId(null);
    }
  }

  if (subjects.loading) return <LoadingState label="Loading courses" />;
  if (subjects.error) return <ErrorState message={subjects.error} onRetry={subjects.refetch} />;
  return (
    <>
      <PageHeader title="Subjects" eyebrow="My Courses" description="Courses appear here only after you join them with a faculty-provided course code." />
      <section>
        <CardTitle>My Courses</CardTitle>
        <div className="mt-4">
          {subjects.data?.length ? (
            <div className="grid gap-4 md:grid-cols-2">
              {subjects.data.map((subject) => (
                <CourseCard key={subject.id} subject={subject} action={<Link className="text-sm font-medium text-ink underline" to={`/student/subjects/${subject.id}`}>Open subject</Link>} />
              ))}
            </div>
          ) : <EmptyState title="No joined courses yet." body="Ask your faculty member for a course code, then join below." />}
        </div>
      </section>
      <section className="mt-8">
        <CardTitle>Available Courses</CardTitle>
        <p className="mt-2 text-sm text-muted">This catalog is separate from My Courses. Joining is always explicit.</p>
        {joinError ? <p className="mt-4 text-sm text-red-700">{joinError}</p> : null}
        <div className="mt-4">
          {available.loading ? <LoadingState /> : available.error ? <ErrorState message={available.error} onRetry={available.refetch} /> : available.data?.length ? (
            <div className="grid gap-4 md:grid-cols-2">
              {available.data.map((subject) => (
                <CourseCard
                  key={subject.id}
                  subject={subject}
                  action={<Button variant="secondary" disabled={joiningId === subject.id} onClick={() => enroll(subject.id)}>{joiningId === subject.id ? "Joining..." : "Join"}</Button>}
                />
              ))}
            </div>
          ) : <EmptyState title="No available courses." body="New faculty-created courses will appear here until you join them." />}
        </div>
      </section>
    </>
  );
}

function CourseCard({
  subject,
  action
}: {
  subject: { id: number; code: string; name: string; description: string | null };
  action: React.ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-muted">{subject.code}</p>
          <h2 className="mt-1 text-xl font-semibold">{subject.name}</h2>
          <p className="mt-2 text-sm leading-6 text-muted">{subject.description ?? "No description provided."}</p>
        </div>
        {action}
      </div>
    </Card>
  );
}
