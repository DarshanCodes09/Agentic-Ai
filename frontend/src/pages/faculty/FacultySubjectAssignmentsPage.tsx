import { ChangeEvent, FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { assignmentsApi } from "../../api/assignments";
import { getApiErrorMessage } from "../../api/client";
import { downloadOrPreviewFile } from "../../api/files";
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
import type { Assignment, AssignmentFile, ExtractedRubricResponse } from "../../types/api";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

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

  // Assignment files state
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [fileValidationError, setFileValidationError] = useState("");
  const [extractingFileIdx, setExtractingFileIdx] = useState<number | null>(null);
  const [conflictWarning, setConflictWarning] = useState<string | null>(null);
  const [extractionInfo, setExtractionInfo] = useState<string | null>(null);
  const [extractedDraft, setExtractedDraft] = useState<ExtractedRubricResponse | null>(null);
  const [hasManualRubricTouched, setHasManualRubricTouched] = useState(false);

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
  const [selectedAssignmentForFiles, setSelectedAssignmentForFiles] = useState<Assignment | null>(null);
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

  const ALLOWED_EXTS = [".pdf", ".docx", ".doc", ".txt", ".md"];
  const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

  function handleFileSelect(e: ChangeEvent<HTMLInputElement>) {
    setFileValidationError("");
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (!ALLOWED_EXTS.includes(ext)) {
        setFileValidationError(`File "${f.name}" has an unsupported format. Supported formats: PDF, DOCX, TXT, MD.`);
        continue;
      }
      if (f.size > MAX_FILE_SIZE) {
        setFileValidationError(`File "${f.name}" exceeds the 20 MB size limit.`);
        continue;
      }
      newFiles.push(f);
    }
    if (newFiles.length > 0) {
      setAttachedFiles((prev) => [...prev, ...newFiles]);
    }
    e.target.value = "";
  }

  function removeAttachedFile(index: number) {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
    if (extractingFileIdx === index) {
      setExtractingFileIdx(null);
    }
  }

  function previewLocalFile(file: File) {
    const url = URL.createObjectURL(file);
    window.open(url, "_blank");
  }

  async function extractRubricFromFile(file: File, idx: number) {
    setExtractingFileIdx(idx);
    setConflictWarning(null);
    setExtractionInfo(null);
    setExtractedDraft(null);

    try {
      const result = await assignmentsApi.extractRubricFromFile(file, form.max_marks);
      setExtractedDraft(result);

      if (result.has_rubric && result.items && result.items.length > 0) {
        // Case B: Faculty already customized manual rubric
        if (hasManualRubricTouched) {
          const extractedSum = result.total_marks ?? result.items.reduce((s, i) => s + i.max_marks, 0);
          if (Math.abs(extractedSum - totalCriteriaMarks) > 0.01) {
            setConflictWarning(
              `The extracted document marking distribution (Total: ${extractedSum} marks, ${result.items.length} criteria) conflicts with your manual rubric (Total: ${totalCriteriaMarks} marks). Your manual rubric remains authoritative unless you choose to replace it.`
            );
          } else {
            setConflictWarning(
              `Document rubric extracted (${result.items.length} criteria totaling ${extractedSum} marks). You have existing manual criteria. Choose whether to replace your manual rubric or keep it.`
            );
          }
        } else {
          // Case A: Faculty has not entered a manual rubric -> populate draft
          setHasRubric(true);
          if (result.rubric_name) setRubricName(result.rubric_name);
          setCriteria(
            result.items.map((i) => ({
              criterion: i.criterion,
              description: i.description || "",
              max_marks: i.max_marks,
            }))
          );
          if (result.assignment_summary && !form.description) {
            setForm((prev) => ({ ...prev, description: result.assignment_summary || prev.description }));
          }
          setExtractionInfo(
            `Extracted rubric draft populated (${result.items.length} criteria totaling ${result.total_marks} marks) from "${file.name}". Please review, edit, and approve criteria below before saving.`
          );
        }
      } else {
        // Case C: No explicit rubric in document
        setExtractionInfo(
          `No explicit grading rubric was found in "${file.name}". The document will still be attached to provide assignment instructions and requirements for AI evaluation. Please continue using the manual rubric builder.`
        );
      }
    } catch (err) {
      setFileValidationError(getApiErrorMessage(err));
    } finally {
      setExtractingFileIdx(null);
    }
  }

  function applyExtractedDraft() {
    if (!extractedDraft || !extractedDraft.items) return;
    setHasRubric(true);
    if (extractedDraft.rubric_name) setRubricName(extractedDraft.rubric_name);
    setCriteria(
      extractedDraft.items.map((i) => ({
        criterion: i.criterion,
        description: i.description || "",
        max_marks: i.max_marks,
      }))
    );
    setConflictWarning(null);
    setExtractionInfo(
      `Replaced manual rubric with extracted criteria (${extractedDraft.items.length} criteria totaling ${extractedDraft.total_marks} marks). Please review before saving.`
    );
    setHasManualRubricTouched(true);
  }

  function addCriterion() {
    setHasManualRubricTouched(true);
    setCriteria([
      ...criteria,
      { criterion: "", description: "", max_marks: 10 },
    ]);
  }

  function removeCriterion(index: number) {
    setHasManualRubricTouched(true);
    setCriteria(criteria.filter((_, i) => i !== index));
  }

  function updateCriterion(index: number, key: keyof CriterionFormItem, value: string | number) {
    setHasManualRubricTouched(true);
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
      const newAsg = await assignmentsApi.create(subjectId, {
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

      // Upload attached files if any
      if (attachedFiles.length > 0) {
        for (const file of attachedFiles) {
          try {
            await assignmentsApi.uploadFile(newAsg.id, file);
          } catch (uploadErr) {
            console.error("Failed to upload assignment file:", uploadErr);
          }
        }
      }

      setForm({ title: "", description: "", instructions: "", due_date: "", max_marks: 100 });
      setAttachedFiles([]);
      setFileValidationError("");
      setConflictWarning(null);
      setExtractionInfo(null);
      setExtractedDraft(null);
      setHasManualRubricTouched(false);
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

            {/* Assignment Files (Optional) */}
            <div className="mt-6 rounded-lg border border-line bg-stone-50/70 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-ink">Assignment Files (Optional)</h3>
                  <p className="text-xs text-muted">
                    Upload one or more assignment instruction files: PDF, DOCX, TXT, or Markdown (Max 20 MB).
                  </p>
                </div>
                <label className="cursor-pointer rounded border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink shadow-sm transition hover:bg-stone-50">
                  <span>+ Choose Files</span>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx,.doc,.txt,.md"
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                </label>
              </div>

              {fileValidationError ? (
                <p className="mt-2 text-xs font-medium text-red-600">{fileValidationError}</p>
              ) : null}

              {attachedFiles.length > 0 ? (
                <div className="mt-3 space-y-2">
                  {attachedFiles.map((f, idx) => (
                    <div
                      key={idx}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-white p-2.5 text-xs shadow-sm"
                    >
                      <div className="flex items-center gap-2 overflow-hidden">
                        <span className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-ink">
                          {f.name.split(".").pop() || "FILE"}
                        </span>
                        <span className="truncate font-medium text-ink" title={f.name}>
                          {f.name}
                        </span>
                        <span className="text-muted">({formatBytes(f.size)})</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => previewLocalFile(f)}
                          className="cursor-pointer rounded border border-line px-2 py-1 text-xs text-ink hover:bg-stone-50"
                        >
                          Preview
                        </button>
                        <button
                          type="button"
                          disabled={extractingFileIdx === idx}
                          onClick={() => extractRubricFromFile(f, idx)}
                          className="cursor-pointer rounded border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                          title="Extract grading criteria and mark distribution from this document"
                        >
                          {extractingFileIdx === idx ? "Extracting..." : "⚡ Extract Rubric from File"}
                        </button>
                        <button
                          type="button"
                          onClick={() => removeAttachedFile(idx)}
                          className="rounded p-1 text-xs text-muted hover:bg-red-50 hover:text-red-700"
                          title="Remove file"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs italic text-muted">
                  No files selected. Faculty can attach instruction files, specifications, or rubric documents.
                </p>
              )}

              {/* Conflict Warning Banner (Case B) */}
              {conflictWarning ? (
                <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-semibold">⚠️ Marking Distribution Conflict</p>
                      <p className="mt-0.5">{conflictWarning}</p>
                    </div>
                    <div className="flex shrink-0 gap-1.5 pt-1 sm:pt-0">
                      <button
                        type="button"
                        onClick={applyExtractedDraft}
                        className="rounded bg-amber-700 px-2.5 py-1 font-medium text-white hover:bg-amber-800"
                      >
                        Replace with Extracted Rubric
                      </button>
                      <button
                        type="button"
                        onClick={() => setConflictWarning(null)}
                        className="rounded border border-amber-400 bg-white px-2.5 py-1 font-medium text-amber-900 hover:bg-amber-100"
                      >
                        Keep Manual Rubric
                      </button>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Extraction Info Banner (Case A / C) */}
              {extractionInfo ? (
                <div className="mt-3 flex items-center justify-between rounded-md border border-sky-200 bg-sky-50 p-2.5 text-xs text-sky-900">
                  <p>{extractionInfo}</p>
                  <button
                    type="button"
                    onClick={() => setExtractionInfo(null)}
                    className="ml-2 text-xs font-semibold text-sky-700 hover:text-sky-900"
                  >
                    ✕
                  </button>
                </div>
              ) : null}
            </div>

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
                  columns={["Title", "Files", "Marks", "Status", "Rubric", "Submissions", "Actions"]}
                  rows={assignments.data.map((item) => [
                    <div>
                      <p className="font-medium text-ink">{item.title}</p>
                      <p className="text-xs text-muted">Due: {formatDate(item.due_date)}</p>
                    </div>,
                    item.files?.length ? (
                      <button
                        type="button"
                        onClick={() => setSelectedAssignmentForFiles(item)}
                        className="cursor-pointer transition hover:opacity-80"
                        title="Click to view attached files"
                      >
                        <Badge tone="neutral">📎 {item.files.length} file{item.files.length > 1 ? "s" : ""}</Badge>
                      </button>
                    ) : (
                      <span className="text-xs text-muted">—</span>
                    ),
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

      {/* Attached Files Modal */}
      <Modal
        isOpen={!!selectedAssignmentForFiles}
        onClose={() => setSelectedAssignmentForFiles(null)}
        title={`${selectedAssignmentForFiles?.title ?? "Assignment"} — Attached Files`}
        description="Instruction, specification, and rubric documents attached by faculty."
      >
        <div className="space-y-3">
          {selectedAssignmentForFiles?.files?.length ? (
            selectedAssignmentForFiles.files.map((af) => (
              <div
                key={af.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-stone-50/50 p-3 text-xs"
              >
                <div className="flex items-center gap-2 overflow-hidden">
                  <span className="rounded bg-stone-200 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-ink">
                    {af.file_type}
                  </span>
                  <span className="truncate font-medium text-ink" title={af.original_filename}>
                    {af.original_filename}
                  </span>
                  <span className="text-muted">({formatBytes(af.file_size)})</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      downloadOrPreviewFile(
                        `/assignments/${selectedAssignmentForFiles.id}/files/${af.id}/file`,
                        af.original_filename,
                        true
                      )
                    }
                    className="cursor-pointer rounded border border-line bg-white px-2.5 py-1 text-xs font-medium text-ink hover:bg-stone-100"
                  >
                    Preview
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      downloadOrPreviewFile(
                        `/assignments/${selectedAssignmentForFiles.id}/files/${af.id}/download`,
                        af.original_filename,
                        false
                      )
                    }
                    className="cursor-pointer rounded bg-ink px-2.5 py-1 text-xs font-medium text-white hover:bg-ink/90"
                  >
                    Download
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs italic text-muted">No files attached to this assignment.</p>
          )}
        </div>
      </Modal>
    </>
  );
}
