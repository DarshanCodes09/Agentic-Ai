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
                  columns={["Title", "Marks", "Rubric", "Submissions", "Analytics"]}
                  rows={assignments.data.map((item) => [
                    <div>
                      <p className="font-medium text-ink">{item.title}</p>
                      <p className="text-xs text-muted">Due: {formatDate(item.due_date)}</p>
                    </div>,
                    item.max_marks,
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
                    <Link
                      className="font-medium underline hover:text-ink"
                      to={`/faculty/subjects/${subjectId}/analytics`}
                    >
                      View
                    </Link>,
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
    </>
  );
}
