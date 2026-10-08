import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Input, Textarea } from "../../components/ui/Input";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { useAsync } from "../../hooks/useAsync";

export function FacultySubjectsPage({ analyticsEntry = false }: { analyticsEntry?: boolean }) {
  const subjects = useAsync(subjectsApi.list, []);
  const [form, setForm] = useState({ name: "", code: "", description: "" });
  const [error, setError] = useState("");

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await subjectsApi.create(form);
      setForm({ name: "", code: "", description: "" });
      subjects.refetch();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  }

  if (subjects.loading) return <LoadingState label="Loading subjects" />;
  if (subjects.error) return <ErrorState message={subjects.error} onRetry={subjects.refetch} />;
  return (
    <>
      <PageHeader title={analyticsEntry ? "Select analytics subject" : "Subjects"} eyebrow="Faculty" description="Create subjects and move into assignments, materials, submissions, and analytics." />
      {!analyticsEntry ? (
        <form onSubmit={create} className="mb-8 grid gap-4 rounded-lg border border-line bg-white p-5 shadow-soft md:grid-cols-4">
          <Field label="Name"><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Code"><Input required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
          <div className="md:col-span-2"><Field label="Description"><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field></div>
          {error ? <p className="text-sm text-red-700 md:col-span-4">{error}</p> : null}
          <Button className="md:col-span-4">Create subject</Button>
        </form>
      ) : null}
      {subjects.data?.length ? <div className="grid gap-4 md:grid-cols-2">{subjects.data.map((subject) => (
        <Card key={subject.id}>
          <p className="text-sm font-semibold text-muted">{subject.code}</p>
          <h2 className="mt-1 text-xl font-semibold">{subject.name}</h2>
          <p className="mt-2 text-sm text-muted">{subject.description ?? "No description."}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to={`/faculty/subjects/${subject.id}/assignments`}><Button variant="secondary">Assignments</Button></Link>
            <Link to={`/faculty/subjects/${subject.id}/materials`}><Button variant="secondary">Materials</Button></Link>
            <Link to={`/faculty/subjects/${subject.id}/analytics`}><Button variant="secondary">Analytics</Button></Link>
          </div>
        </Card>
      ))}</div> : <EmptyState title="No subjects yet." />}
    </>
  );
}
