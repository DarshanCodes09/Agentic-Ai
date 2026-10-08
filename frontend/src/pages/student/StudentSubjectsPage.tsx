import { Link } from "react-router-dom";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { useAsync } from "../../hooks/useAsync";

export function StudentSubjectsPage() {
  const subjects = useAsync(subjectsApi.list, []);
  async function enroll(subjectId: number) {
    await subjectsApi.enroll(subjectId);
    subjects.refetch();
  }
  if (subjects.loading) return <LoadingState label="Loading subjects" />;
  if (subjects.error) return <ErrorState message={subjects.error} onRetry={subjects.refetch} />;
  return (
    <>
      <PageHeader title="Subjects" eyebrow="Catalog" description="Browse available subjects and open enrolled subject work." />
      {subjects.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {subjects.data.map((subject) => (
            <Card key={subject.id}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-muted">{subject.code}</p>
                  <h2 className="mt-1 text-xl font-semibold">{subject.name}</h2>
                  <p className="mt-2 text-sm leading-6 text-muted">{subject.description ?? "No description provided."}</p>
                </div>
                <Button variant="secondary" onClick={() => enroll(subject.id)}>Enroll</Button>
              </div>
              <Link className="mt-5 inline-block text-sm font-medium text-ink underline" to={`/student/subjects/${subject.id}`}>Open subject</Link>
            </Card>
          ))}
        </div>
      ) : <EmptyState title="No subjects available." />}
    </>
  );
}
