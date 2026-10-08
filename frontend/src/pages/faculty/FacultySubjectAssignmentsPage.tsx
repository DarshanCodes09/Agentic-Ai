import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { assignmentsApi } from "../../api/assignments";
import { getApiErrorMessage } from "../../api/client";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Input, Textarea } from "../../components/ui/Input";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";

export function FacultySubjectAssignmentsPage() {
  const subjectId = Number(useParams().subjectId);
  const subject = useAsync(() => subjectsApi.get(subjectId), [subjectId]);
  const assignments = useAsync(() => subjectsApi.assignments(subjectId), [subjectId]);
  const [form, setForm] = useState({ title: "", description: "", instructions: "", due_date: "", max_marks: 100 });
  const [error, setError] = useState("");

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await assignmentsApi.create(subjectId, { ...form, due_date: new Date(form.due_date).toISOString() });
      setForm({ title: "", description: "", instructions: "", due_date: "", max_marks: 100 });
      assignments.refetch();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  }

  if (subject.loading) return <LoadingState label="Loading assignments" />;
  if (subject.error) return <ErrorState message={subject.error} onRetry={subject.refetch} />;
  return (
    <>
      <PageHeader title={`${subject.data?.name} assignments`} eyebrow={subject.data?.code} description="Create assignments, then add questions, rubrics, and review submissions." />
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardTitle>Create assignment</CardTitle>
          <form onSubmit={create} className="mt-4 space-y-4">
            <Field label="Title"><Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
            <Field label="Due date"><Input required type="datetime-local" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field>
            <Field label="Maximum marks"><Input required type="number" min={1} value={form.max_marks} onChange={(e) => setForm({ ...form, max_marks: Number(e.target.value) })} /></Field>
            <Field label="Description"><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            <Field label="Instructions"><Textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} /></Field>
            {error ? <p className="text-sm text-red-700">{error}</p> : null}
            <Button>Create</Button>
          </form>
        </Card>
        <Card>
          <CardTitle>Assignments</CardTitle>
          <div className="mt-4">
            {assignments.loading ? <LoadingState /> : assignments.data?.length ? (
              <Table columns={["Title", "Due", "Marks", "Submissions", "Analytics"]} rows={assignments.data.map((item) => [
                item.title,
                formatDate(item.due_date),
                item.max_marks,
                <Link className="font-medium underline" to={`/faculty/assignments/${item.id}/submissions`}>Open</Link>,
                <Link className="font-medium underline" to={`/faculty/subjects/${subjectId}/analytics`}>View</Link>
              ])} />
            ) : <EmptyState title="No assignments yet." />}
          </div>
        </Card>
      </div>
    </>
  );
}
