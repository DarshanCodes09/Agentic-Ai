import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { downloadOrPreviewFile } from "../../api/files";
import { materialsApi } from "../../api/materials";
import { subjectsApi } from "../../api/subjects";

import { PageHeader } from "../../components/common/PageHeader";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";
import type { CourseMaterial } from "../../types/api";

export function FacultyMaterialsPage() {
  const subjectId = Number(useParams().subjectId);
  const subject = useAsync(() => subjectsApi.get(subjectId), [subjectId]);
  const materials = useAsync(() => subjectsApi.materials(subjectId), [subjectId]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");

  // Edit material state
  const [editingMaterial, setEditingMaterial] = useState<CourseMaterial | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editError, setEditError] = useState("");
  const [editLoading, setEditLoading] = useState(false);

  // Delete material confirmation state
  const [deletingMaterial, setDeletingMaterial] = useState<CourseMaterial | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError("");
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("file", file);
      await subjectsApi.uploadMaterial(subjectId, form);
      setTitle("");
      setFile(null);
      materials.refetch();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  }

  function startEdit(item: CourseMaterial) {
    setEditingMaterial(item);
    setEditTitle(item.title);
    setEditError("");
  }

  async function handleUpdate(event: FormEvent) {
    event.preventDefault();
    if (!editingMaterial) return;
    if (!editTitle.trim()) {
      setEditError("Material title cannot be empty.");
      return;
    }
    setEditLoading(true);
    setEditError("");
    try {
      await materialsApi.update(editingMaterial.id, { title: editTitle.trim() });
      setEditingMaterial(null);
      materials.refetch();
    } catch (err) {
      setEditError(getApiErrorMessage(err));
    } finally {
      setEditLoading(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deletingMaterial) return;
    setDeleteLoading(true);
    setDeleteError("");
    try {
      await materialsApi.remove(deletingMaterial.id);
      setDeletingMaterial(null);
      materials.refetch();
    } catch (err) {
      setDeleteError(getApiErrorMessage(err));
    } finally {
      setDeleteLoading(false);
    }
  }

  if (subject.loading) return <LoadingState label="Loading materials" />;
  if (subject.error) return <ErrorState message={subject.error} onRetry={subject.refetch} />;

  return (
    <>
      <PageHeader
        title={`${subject.data?.name} course materials`}
        eyebrow="Knowledge Base Management"
        description="Upload PDF or DOCX reference files. Manage material titles, remove outdated documents, and inspect vector indexing."
      />
      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardTitle>Upload material</CardTitle>
          <form onSubmit={upload} className="mt-4 space-y-4">
            <Field label="Title">
              <Input
                placeholder="e.g. Week 1: Algorithm Complexity Lecture Notes"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </Field>
            <Field label="PDF or DOCX">
              <Input
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </Field>
            {error ? <p className="text-sm text-red-700">{error}</p> : null}
            <Button disabled={!file}>Upload</Button>
          </form>
        </Card>

        <Card>
          <CardTitle>Materials</CardTitle>
          <div className="mt-4">
            {materials.loading ? (
              <LoadingState />
            ) : materials.data?.length ? (
              <Table
                columns={["Title", "Filename", "Status", "Uploaded", "Actions"]}
                rows={materials.data.map((item) => [
                  item.title,
                  item.original_filename,
                  <Badge tone={statusTone(item.processing_status)}>{item.processing_status}</Badge>,
                  formatDate(item.created_at),
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        downloadOrPreviewFile(
                          `/materials/${item.id}/file`,
                          item.original_filename,
                          true
                        )
                      }
                      className="cursor-pointer text-xs font-medium underline hover:text-ink"
                    >
                      Preview
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        downloadOrPreviewFile(
                          `/materials/${item.id}/file`,
                          item.original_filename,
                          false
                        )
                      }
                      className="cursor-pointer text-xs font-medium underline hover:text-ink"
                    >
                      Download
                    </button>
                    <button
                      type="button"
                      onClick={() => startEdit(item)}
                      className="rounded px-1.5 py-0.5 text-xs font-medium text-ink hover:bg-stone-100"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDeletingMaterial(item);
                        setDeleteError("");
                      }}
                      className="rounded px-1.5 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>,
                ])}
              />
            ) : (
              <EmptyState title="No materials uploaded." />
            )}
          </div>
        </Card>
      </div>

      {/* Edit Material Modal */}
      <Modal
        isOpen={!!editingMaterial}
        onClose={() => setEditingMaterial(null)}
        title="Edit course material"
        description="Update the display title for this lecture note or reference document."
      >
        <form onSubmit={handleUpdate} className="space-y-4">
          <Field label="Document Title">
            <Input
              required
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
            />
          </Field>
          {editError ? <p className="text-sm text-red-700">{editError}</p> : null}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setEditingMaterial(null)}>
              Cancel
            </Button>
            <Button disabled={editLoading}>
              {editLoading ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Material Confirmation Modal */}
      <Modal
        isOpen={!!deletingMaterial}
        onClose={() => setDeletingMaterial(null)}
        title={`Delete material "${deletingMaterial?.title}"?`}
        description="This will permanently delete the reference document from server storage and remove its vectorized semantic chunks from the ChromaDB knowledge base."
      >
        <div className="space-y-4">
          {deleteError ? <p className="text-sm text-red-700">{deleteError}</p> : null}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setDeletingMaterial(null)}>
              Cancel
            </Button>
            <Button variant="danger" disabled={deleteLoading} onClick={handleDeleteConfirm}>
              {deleteLoading ? "Deleting..." : "Confirm Delete"}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
