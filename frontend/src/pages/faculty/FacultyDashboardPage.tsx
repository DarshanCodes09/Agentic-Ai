import { Link } from "react-router-dom";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { useAuth } from "../../context/AuthContext";
import { useAsync } from "../../hooks/useAsync";

export function FacultyDashboardPage() {
  const { user } = useAuth();
  const subjects = useAsync(subjectsApi.list, []);
  if (subjects.loading) return <LoadingState label="Loading faculty overview" />;
  if (subjects.error) return <ErrorState message={subjects.error} onRetry={subjects.refetch} />;
  return (
    <>
      <PageHeader title="Faculty overview" eyebrow={user?.full_name} description="A calm command center for courses, assignments, materials, submissions, and class analytics." />
      <div className="grid gap-6 md:grid-cols-3">
        <Card><p className="text-xs uppercase tracking-wide text-muted">Subjects</p><p className="mt-2 text-4xl font-semibold">{subjects.data?.length ?? 0}</p></Card>
        <Card><p className="text-xs uppercase tracking-wide text-muted">Assignments</p><p className="mt-2 text-4xl font-semibold">Open</p></Card>
        <Card><p className="text-xs uppercase tracking-wide text-muted">Review queue</p><p className="mt-2 text-sm text-muted">Open a subject assignment to review submissions.</p></Card>
      </div>
      <section className="mt-8">
        <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Owned subjects</h2><Link to="/faculty/subjects"><Button variant="secondary">Manage subjects</Button></Link></div>
        {subjects.data?.length ? <div className="grid gap-4 md:grid-cols-2">{subjects.data.slice(0, 4).map((subject) => <SubjectCard key={subject.id} subject={subject} />)}</div> : <EmptyState title="No subjects yet." body="Create a subject to start building assignments." />}
      </section>
    </>
  );
}

function SubjectCard({ subject }: { subject: { id: number; code: string; name: string; description: string | null } }) {
  return (
    <Card>
      <p className="text-sm font-semibold text-muted">{subject.code}</p>
      <h3 className="mt-1 text-xl font-semibold">{subject.name}</h3>
      <p className="mt-2 text-sm text-muted">{subject.description ?? "No description."}</p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link to={`/faculty/subjects/${subject.id}/assignments`}><Button variant="secondary">Assignments</Button></Link>
        <Link to={`/faculty/subjects/${subject.id}/materials`}><Button variant="secondary">Materials</Button></Link>
        <Link to={`/faculty/subjects/${subject.id}/analytics`}><Button variant="secondary">Analytics</Button></Link>
      </div>
    </Card>
  );
}
