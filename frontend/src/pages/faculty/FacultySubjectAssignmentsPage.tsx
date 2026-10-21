import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { assignmentsApi } from "../../api/assignments";
import { getApiErrorMessage } from "../../api/client";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Input, Textarea } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";
import type { Assignment } from "../../types/api";

interface CriterionFormItem {
  criterion: string;
  description: string;
  max_marks: number;
}

export function FacultySubjectAssignmentsPage() {
  const subjectId = Number(useParams().subjectId);
  const subject = useAsync(() => subjectsApi.get(subjectId), [subjectId]);
  const assignments = useAsync(() => subjectsApi.assignments(subjectId), [subjectId]);

  const [form, setForm] = useState({
    title: "",
    description: "",
    instructions: "",
    due_date: "",
    max_marks: 100,
  });

  const [hasRubric, setHasRubric] = useState(true);
  const [rubricName, setRubricName] = useState("");
  const [rubricDescription, setRubricDescription] = useState("");
  const [criteria, setCriteria] = useState<CriterionFormItem[]>([
    {
      criterion: "Technical Correctness & Accuracy",
      description: "Correct logic, problem solving, and adherence to requirements",
      max_marks: 60,
    },
    {
      criterion: "Code Quality & Documentation",
      description: "Modular, readable structure, appropriate comments, and clean style",
      max_marks: 40,
    },
  ]);

  const [selectedAssignmentForRubric, setSelectedAssignmentForRubric] = useState<Assignment | null>(null);
  const [error, setError] = useState("");

  // Edit assignment state
  const [editingAssignment, setEditingAssignment] = useState<Assignment | null>(null);
  const [editForm, setEditForm] = useState({
    title: "",
    description: "",
    instructions: "",
    due_date: "",
    max_marks: 100,
    is_archived: false,
  });
  const [editError, setEditError] = useState("");
  const [editLoading, setEditLoading] = useState(false);

  // Delete / Archive assignment state
  const [actionAssignment, setActionAssignment] = useState<Assignment | null>(null);
  const [actionType, setActionType] = useState<"delete" | "archive" | "unarchive" | null>(null);
  const [actionError, setActionError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  function startEditAssignment(asg: Assignment) {
    setEditingAssignment(asg);
    setEditForm({
      title: asg.title,
      description: asg.description || "",
      instructions: asg.instructions || "",
      due_date: asg.due_date ? new Date(asg.due_date).toISOString().slice(0, 16) : "",
      max_marks: asg.max_marks,
      is_archived: !!asg.is_archived,
    });
    setEditError("");
  }

  async function handleUpdateAssignment(event: FormEvent) {
    event.preventDefault();
    if (!editingAssignment) return;
    setEditError("");

    if (!editForm.title.trim()) {
      setEditError("Assignment title cannot be empty.");
      return;
    }
    if (editForm.max_marks <= 0) {
      setEditError("Maximum marks must be greater than 0.");
      return;
    }

    // Rubric total check
    if (editingAssignment.rubric?.items?.length) {
      const rubricTotal = editingAssignment.rubric.items.reduce(
        (sum, item) => sum + (Number(item.max_marks) || 0),
        0
      );
      if (editForm.max_marks < rubricTotal) {
        setEditError(
          `Maximum marks (${editForm.max_marks}) cannot be less than current rubric criteria total (${rubricTotal}).`
        );
        return;
      }
    }

    setEditLoading(true);
    try {
      await assignmentsApi.update(editingAssignment.id, {
        title: editForm.title.trim(),
        description: editForm.description || undefined,
        instructions: editForm.instructions || undefined,
        due_date: editForm.due_date ? new Date(editForm.due_date).toISOString() : undefined,
        max_marks: Number(editForm.max_marks),
        is_archived: editForm.is_archived,
      });
      setEditingAssignment(null);
      assignments.refetch();
    } catch (err) {
      setEditError(getApiErrorMessage(err));
    } finally {
      setEditLoading(false);
    }
  }

  async function handleActionConfirm() {
    if (!actionAssignment || !actionType) return;
    setActionLoading(true);
    setActionError("");
    try {
      if (actionType === "delete") {
        await assignmentsApi.remove(actionAssignment.id);
      } else if (actionType === "archive") {
        await assignmentsApi.archive(actionAssignment.id, true);
      } else if (actionType === "unarchive") {
        await assignmentsApi.archive(actionAssignment.id, false);
      }
      setActionAssignment(null);
      setActionType(null);
      assignments.refetch();
    } catch (err) {
      setActionError(getApiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  }

  const totalCriteriaMarks = criteria.reduce(
    (sum, item) => sum + (Number(item.max_marks) || 0),
    0
  );

  function addCriterion() {
    setCriteria([
      ...criteria,
      { criterion: "", description: "", max_marks: 10 },
    ]);
  }

  function removeCriterion(index: number) {
    setCriteria(criteria.filter((_, i) => i !== index));
  }

  function updateCriterion(index: number, key: keyof CriterionFormItem, value: string | number) {
    setCriteria(
      criteria.map((item, i) => (i === index ? { ...item, [key]: value } : item))
    );
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    setError("");

    if (hasRubric) {
      if (criteria.length === 0) {
        setError("Please define at least one rubric criterion or disable the rubric.");
        return;
      }
      for (let i = 0; i < criteria.length; i++) {
        if (!criteria[i].criterion.trim()) {
          setError(`Criterion #${i + 1} title cannot be empty.`);
          return;
        }
        if (Number(criteria[i].max_marks) <= 0) {
          setError(`Criterion #${i + 1} max marks must be greater than 0.`);
          return;
        }
      }

      // Check for duplicate names
      const seen = new Set<string>();
      for (const item of criteria) {
        const norm = item.criterion.trim().toLowerCase();
        if (seen.has(norm)) {
          setError(`Duplicate rubric criterion: "${item.criterion.trim()}".`);
          return;
        }
        seen.add(norm);
      }

      if (totalCriteriaMarks > form.max_marks) {
        setError(
          `Total rubric marks (${totalCriteriaMarks}) cannot exceed the assignment maximum marks (${form.max_marks}).`
        );
        return;
      }
    }

    try {
      await assignmentsApi.create(subjectId, {
        ...form,
        due_date: new Date(form.due_date).toISOString(),
        rubric: hasRubric
          ? {
              name: rubricName.trim() || `${form.title.trim()} Rubric`,
              description: rubricDescription.trim() || undefined,
              items: criteria.map((c) => ({
                criterion: c.criterion.trim(),
                description: c.description.trim() || undefined,
                max_marks: Number(c.max_marks),
              })),
            }
          : undefined,
      });

      setForm({ title: "", description: "", instructions: "", due_date: "", max_marks: 100 });
      setRubricName("");
      setRubricDescription("");
      setCriteria([
        {
          criterion: "Technical Correctness & Accuracy",
          description: "Correct logic, problem solving, and adherence to requirements",
          max_marks: 60,
        },
        {
          criterion: "Code Quality & Documentation",
          description: "Modular, readable structure, appropriate comments, and clean style",
          max_marks: 40,
        },
      ]);
      assignments.refetch();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  }

  if (subject.loading) return <LoadingState label="Loading assignments" />;
  if (subject.error) return <ErrorState message={subject.error} onRetry={subject.refetch} />;

  return (
    <>
      <PageHeader
        title={`${subject.data?.name} assignments`}
        eyebrow={subject.data?.code}
        description="Create assignments with structured rubrics, configure grading criteria, and review AI-evaluated submissions."
      />
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardTitle>Create assignment</CardTitle>
          <form onSubmit={create} className="mt-4 space-y-4">
            <Field label="Title">
              <Input
                required
                placeholder="e.g., Assignment 1: Data Structures"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </Field>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Due date">
                <Input
                  required
                  type="datetime-local"
                  value={form.due_date}
                  onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                />
              </Field>
              <Field label="Maximum marks">
                <Input
                  required
                  type="number"
                  min={1}
                  value={form.max_marks}
                  onChange={(e) => setForm({ ...form, max_marks: Number(e.target.value) })}
                />
              </Field>
            </div>

            <Field label="Description">
              <Textarea
                placeholder="Overview of the assignment requirements"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </Field>

            <Field label="Instructions">
              <Textarea
                placeholder="Submission format, constraints, and guidelines"
                value={form.instructions}
                onChange={(e) => setForm({ ...form, instructions: e.target.value })}
              />
            </Field>

            {/* Rubric Section */}
            <div className="mt-6 rounded-lg border border-line bg-stone-50/70 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-ink">Evaluation Rubric</h3>
                  <p className="text-xs text-muted">
                    Define criteria used by Groq AI and faculty to evaluate submissions.
                  </p>
                </div>
                <label className="flex cursor-pointer items-center gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-line text-ink focus:ring-ink"
                    checked={hasRubric}
                    onChange={(e) => setHasRubric(e.target.checked)}
                  />
                  <span>Attach Rubric</span>
                </label>
              </div>

              {hasRubric ? (
                <div className="mt-4 space-y-4">
                  <Field label="Rubric Name" hint="Defaults to assignment title if empty">
                    <Input
                      placeholder={form.title ? `${form.title} Rubric` : "e.g., AVL Tree Grading Rubric"}
                      value={rubricName}
                      onChange={(e) => setRubricName(e.target.value)}
                    />
                  </Field>

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                      Criteria List
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-ink">
                        Tally: {totalCriteriaMarks} / {form.max_marks}
                      </span>
                      {totalCriteriaMarks === form.max_marks ? (
                        <Badge tone="success">Balanced</Badge>
                      ) : totalCriteriaMarks < form.max_marks ? (
                        <Badge tone="warning">
                          Unallocated: {form.max_marks - totalCriteriaMarks}
                        </Badge>
                      ) : (
                        <Badge tone="danger">
                          Exceeds: +{totalCriteriaMarks - form.max_marks}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="space-y-3">
                    {criteria.map((item, index) => (
                      <div
                        key={index}
                        className="rounded-md border border-line bg-white p-3 shadow-sm transition hover:border-ink/30"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-[1fr_100px]">
                            <Input
                              required
                              placeholder={`Criterion #${index + 1} Name`}
                              value={item.criterion}
                              onChange={(e) =>
                                updateCriterion(index, "criterion", e.target.value)
                              }
                            />
                            <Input
                              required
                              type="number"
                              min={1}
                              step="0.5"
                              placeholder="Marks"
                              value={item.max_marks}
                              onChange={(e) =>
                                updateCriterion(index, "max_marks", Number(e.target.value))
                              }
                            />
                          </div>
                          {criteria.length > 1 ? (
                            <button
                              type="button"
                              onClick={() => removeCriterion(index)}
                              className="rounded p-1.5 text-xs text-muted transition hover:bg-red-50 hover:text-red-700"
                              title="Remove criterion"
                            >
                              ✕
                            </button>
                          ) : null}
                        </div>
                        <div className="mt-2">
                          <Input
                            placeholder="Explanation of expected benchmark or concepts"
                            value={item.description}
                            onChange={(e) =>
                              updateCriterion(index, "description", e.target.value)
                            }
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="pt-1">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={addCriterion}
                      className="text-xs"
                    >
                      + Add Criterion
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>

            {error ? <p className="text-sm font-medium text-red-700">{error}</p> : null}
            <Button>Create Assignment</Button>
          </form>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardTitle>Assignments</CardTitle>
            <div className="mt-4">
              {assignments.loading ? (
                <LoadingState />
              ) : assignments.data?.length ? (
                <Table
                  columns={["Title", "Marks", "Status", "Rubric", "Submissions", "Actions"]}
                  rows={assignments.data.map((item) => [
                    <div>
                      <p className="font-medium text-ink">{item.title}</p>
                      <p className="text-xs text-muted">Due: {formatDate(item.due_date)}</p>
                    </div>,
                    item.max_marks,
                    item.is_archived ? (
                      <Badge tone="neutral">Archived</Badge>
                    ) : (
                      <Badge tone="success">Active</Badge>
                    ),
                    item.rubric ? (
                      <button
                        type="button"
                        onClick={() => setSelectedAssignmentForRubric(item)}
                        className="cursor-pointer transition hover:opacity-80"
                        title="Click to view criteria"
                      >
                        <Badge tone="success">
                          {item.rubric.items?.length ?? 0} criteria
                        </Badge>
                      </button>
                    ) : (
                      <Badge tone="neutral">None</Badge>
                    ),
                    <Link
                      className="font-medium underline hover:text-ink"
                      to={`/faculty/assignments/${item.id}/submissions`}
                    >
                      Open
                    </Link>,
                    <div className="flex items-center gap-1.5">
                      <Link
                        className="rounded px-2 py-1 text-xs font-medium text-ink hover:bg-stone-100"
                        to={`/faculty/subjects/${subjectId}/analytics`}
                      >
                        Analytics
                      </Link>
                      <button
                        type="button"
                        onClick={() => startEditAssignment(item)}
                        className="rounded px-2 py-1 text-xs font-medium text-ink hover:bg-stone-100"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setActionAssignment(item);
                          setActionType(item.is_archived ? "unarchive" : "archive");
                          setActionError("");
                        }}
                        className="rounded px-2 py-1 text-xs font-medium text-ink hover:bg-stone-100"
                      >
                        {item.is_archived ? "Unarchive" : "Archive"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setActionAssignment(item);
                          setActionType("delete");
                          setActionError("");
                        }}
                        className="rounded px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </div>,
                  ])}
                />
              ) : (
                <EmptyState title="No assignments yet." />
              )}
            </div>
          </Card>

          {/* Rubric Preview Card when an assignment is selected */}
          {selectedAssignmentForRubric && selectedAssignmentForRubric.rubric ? (
            <Card>
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div>
                  <CardTitle>{selectedAssignmentForRubric.rubric.name}</CardTitle>
                  <p className="text-xs text-muted">
                    {selectedAssignmentForRubric.title} • Total Marks:{" "}
                    {selectedAssignmentForRubric.max_marks}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedAssignmentForRubric(null)}
                  className="rounded p-1 text-xs text-muted hover:bg-stone-100"
                >
                  ✕
                </button>
              </div>
              <div className="mt-3 space-y-2">
                {selectedAssignmentForRubric.rubric.items.map((criterionItem) => (
                  <div
                    key={criterionItem.id}
                    className="flex items-start justify-between rounded-md border border-line bg-stone-50/50 p-2.5 text-xs"
                  >
                    <div>
                      <p className="font-semibold text-ink">{criterionItem.criterion}</p>
                      {criterionItem.description ? (
                        <p className="mt-0.5 text-muted">{criterionItem.description}</p>
                      ) : null}
                    </div>
                    <Badge tone="neutral">{criterionItem.max_marks} marks</Badge>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}
        </div>
      </div>

      {/* Edit Assignment Modal */}
      <Modal
        isOpen={!!editingAssignment}
        onClose={() => setEditingAssignment(null)}
        title="Edit assignment"
        description="Update assignment details, due date, maximum marks, or archive status."
      >
        <form onSubmit={handleUpdateAssignment} className="space-y-4">
          <Field label="Title">
            <Input
              required
              value={editForm.title}
              onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
            />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Due date">
              <Input
                required
                type="datetime-local"
                value={editForm.due_date}
                onChange={(e) => setEditForm({ ...editForm, due_date: e.target.value })}
              />
            </Field>
            <Field
              label="Maximum marks"
              hint={
                editingAssignment?.rubric?.items?.length
                  ? `Min: ${editingAssignment.rubric.items.reduce((s, i) => s + Number(i.max_marks), 0)} (rubric total)`
                  : undefined
              }
            >
              <Input
                required
                type="number"
                min={1}
                value={editForm.max_marks}
                onChange={(e) => setEditForm({ ...editForm, max_marks: Number(e.target.value) })}
              />
            </Field>
          </div>
          <Field label="Description">
            <Textarea
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
            />
          </Field>
          <Field label="Instructions">
            <Textarea
              value={editForm.instructions}
              onChange={(e) => setEditForm({ ...editForm, instructions: e.target.value })}
            />
          </Field>
          <div className="flex items-center gap-2 pt-1">
            <input
              id="edit_asg_archived"
              type="checkbox"
              checked={editForm.is_archived}
              onChange={(e) => setEditForm({ ...editForm, is_archived: e.target.checked })}
              className="h-4 w-4 rounded border-line"
            />
            <label htmlFor="edit_asg_archived" className="text-sm font-medium text-ink">
              Archive this assignment (read-only for submissions)
            </label>
          </div>
          {editError ? <p className="text-sm text-red-700">{editError}</p> : null}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setEditingAssignment(null)}>
              Cancel
            </Button>
            <Button disabled={editLoading}>
              {editLoading ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Action / Delete Assignment Modal */}
      <Modal
        isOpen={!!actionAssignment && !!actionType}
        onClose={() => {
          setActionAssignment(null);
          setActionType(null);
        }}
        title={
          actionType === "delete"
            ? `Delete assignment "${actionAssignment?.title}"?`
            : actionType === "archive"
            ? `Archive assignment "${actionAssignment?.title}"?`
            : `Unarchive assignment "${actionAssignment?.title}"?`
        }
        description={
          actionType === "delete"
            ? "Permanent deletion is rejected if student submissions exist to protect grades, feedback, and academic records. If work was submitted, archive the assignment instead."
            : actionType === "archive"
            ? "Archived assignments will no longer accept new student submissions while preserving all past submissions and evaluation records."
            : "Reactivating restores student visibility for active submissions."
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
                setActionAssignment(null);
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
