import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Input, Textarea } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { useAsync } from "../../hooks/useAsync";
import type { Subject } from "../../types/api";

export function FacultySubjectsPage({ analyticsEntry = false }: { analyticsEntry?: boolean }) {
  const subjects = useAsync(subjectsApi.list, []);
  const [form, setForm] = useState({ name: "", code: "", description: "" });
  const [error, setError] = useState("");

  // Edit Course state
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "", is_archived: false });
  const [editError, setEditError] = useState("");
  const [editLoading, setEditLoading] = useState(false);

  // Delete / Archive confirmation modal state
  const [actionSubject, setActionSubject] = useState<Subject | null>(null);
  const [actionType, setActionType] = useState<"delete" | "archive" | "unarchive" | null>(null);
  const [actionError, setActionError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

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

  function startEdit(subj: Subject) {
    setEditingSubject(subj);
    setEditForm({
      name: subj.name,
      description: subj.description || "",
      is_archived: !!subj.is_archived,
    });
    setEditError("");
  }

  async function handleUpdate(event: FormEvent) {
    event.preventDefault();
    if (!editingSubject) return;
    setEditLoading(true);
    setEditError("");
    try {
      await subjectsApi.update(editingSubject.id, {
        name: editForm.name,
        description: editForm.description,
        is_archived: editForm.is_archived,
      });
      setEditingSubject(null);
      subjects.refetch();
    } catch (err) {
      setEditError(getApiErrorMessage(err));
    } finally {
      setEditLoading(false);
    }
  }

  async function handleActionConfirm() {
    if (!actionSubject || !actionType) return;
    setActionLoading(true);
    setActionError("");
    try {
      if (actionType === "delete") {
        await subjectsApi.remove(actionSubject.id);
      } else if (actionType === "archive") {
        await subjectsApi.archive(actionSubject.id, true);
      } else if (actionType === "unarchive") {
        await subjectsApi.archive(actionSubject.id, false);
      }
      setActionSubject(null);
      setActionType(null);
      subjects.refetch();
    } catch (err) {
      setActionError(getApiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  }

  if (subjects.loading) return <LoadingState label="Loading subjects" />;
  if (subjects.error) return <ErrorState message={subjects.error} onRetry={subjects.refetch} />;

  return (
    <>
      <PageHeader
        title={analyticsEntry ? "Select analytics subject" : "Courses & Subjects"}
        eyebrow="Faculty Portal"
        description="Create and manage academic courses, update syllabus details, archive completed terms, and safeguard enrollment history."
      />
      {!analyticsEntry ? (
        <form onSubmit={create} className="mb-8 grid gap-4 rounded-lg border border-line bg-white p-5 shadow-soft md:grid-cols-4">
          <Field label="Course Name">
            <Input required placeholder="e.g. Data Structures & Algorithms" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Course Code">
            <Input required placeholder="e.g. CS201" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </Field>
          <div className="md:col-span-2">
            <Field label="Description">
              <Textarea placeholder="Overview and prerequisites" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
          </div>
          {error ? <p className="text-sm text-red-700 md:col-span-4">{error}</p> : null}
          <Button className="md:col-span-4">Create course</Button>
        </form>
      ) : null}

      {subjects.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {subjects.data.map((subject) => (
            <Card key={subject.id}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold text-muted">{subject.code}</p>
                  <h2 className="mt-1 text-xl font-semibold text-ink">{subject.name}</h2>
                </div>
                {subject.is_archived ? (
                  <Badge tone="neutral">Archived</Badge>
                ) : (
                  <Badge tone="success">Active</Badge>
                )}
              </div>
              <p className="mt-2 text-sm text-muted">{subject.description ?? "No description provided."}</p>

              <div className="mt-5 flex flex-wrap gap-2 border-t border-line/60 pt-4">
                <Link to={`/faculty/subjects/${subject.id}/assignments`}>
                  <Button variant="secondary">Assignments</Button>
                </Link>
                <Link to={`/faculty/subjects/${subject.id}/materials`}>
                  <Button variant="secondary">Materials</Button>
                </Link>
                <Link to={`/faculty/subjects/${subject.id}/analytics`}>
                  <Button variant="secondary">Analytics</Button>
                </Link>
                {!analyticsEntry && (
                  <>
                    <Button variant="ghost" onClick={() => startEdit(subject)}>
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setActionSubject(subject);
                        setActionType(subject.is_archived ? "unarchive" : "archive");
                        setActionError("");
                      }}
                    >
                      {subject.is_archived ? "Unarchive" : "Archive"}
                    </Button>
                    <Button
                      variant="ghost"
                      className="text-red-700 hover:bg-red-50"
                      onClick={() => {
                        setActionSubject(subject);
                        setActionType("delete");
                        setActionError("");
                      }}
                    >
                      Delete
                    </Button>
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="No courses yet." body="Create your first academic course above to begin assigning homework and course materials." />
      )}

      {/* Edit Course Modal */}
      <Modal
        isOpen={!!editingSubject}
        onClose={() => setEditingSubject(null)}
        title={`Edit ${editingSubject?.code}`}
        description="Update course title, overview, and active status."
      >
        <form onSubmit={handleUpdate} className="space-y-4">
          <Field label="Course Name">
            <Input
              required
              value={editForm.name}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
            />
          </Field>
          <Field label="Description">
            <Textarea
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
            />
          </Field>
          <div className="flex items-center gap-2 pt-1">
            <input
              id="edit_is_archived"
              type="checkbox"
              checked={editForm.is_archived}
              onChange={(e) => setEditForm({ ...editForm, is_archived: e.target.checked })}
              className="h-4 w-4 rounded border-line"
            />
            <label htmlFor="edit_is_archived" className="text-sm font-medium text-ink">
              Archive this course (read-only for students)
            </label>
          </div>
          {editError ? <p className="text-sm text-red-700">{editError}</p> : null}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setEditingSubject(null)}>
              Cancel
            </Button>
            <Button disabled={editLoading}>
              {editLoading ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Action / Delete Confirmation Modal */}
      <Modal
        isOpen={!!actionSubject && !!actionType}
        onClose={() => {
          setActionSubject(null);
          setActionType(null);
        }}
        title={
          actionType === "delete"
            ? `Delete course ${actionSubject?.code}?`
            : actionType === "archive"
            ? `Archive course ${actionSubject?.code}?`
            : `Unarchive course ${actionSubject?.code}?`
        }
        description={
          actionType === "delete"
            ? "Permanent deletion is only allowed if no students or assignments exist. If records exist, archiving is required to preserve academic integrity."
            : actionType === "archive"
            ? "Archiving hides the course from active student enrollment lists while keeping all student submissions, grades, and analytics intact."
            : "Reactivating will restore the course to active status for students."
        }
      >
        <div className="space-y-4">
          {actionError ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <p className="font-semibold">Action Prevented</p>
              <p className="mt-1">{actionError}</p>
            </div>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setActionSubject(null);
                setActionType(null);
              }}
            >
              Cancel
            </Button>
            <Button
              variant={actionType === "delete" ? "danger" : "primary"}
              disabled={actionLoading}
              onClick={handleActionConfirm}
            >
              {actionLoading
                ? "Processing..."
                : actionType === "delete"
                ? "Confirm Delete"
                : actionType === "archive"
                ? "Confirm Archive"
                : "Confirm Unarchive"}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
