import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Input } from "../../components/ui/Input";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";
import { formatDate } from "../../utils/format";

export function FacultyMaterialsPage() {
  const subjectId = Number(useParams().subjectId);
  const subject = useAsync(() => subjectsApi.get(subjectId), [subjectId]);
  const materials = useAsync(() => subjectsApi.materials(subjectId), [subjectId]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");

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

  if (subject.loading) return <LoadingState label="Loading materials" />;
  if (subject.error) return <ErrorState message={subject.error} onRetry={subject.refetch} />;
  return (
    <>
      <PageHeader title={`${subject.data?.name} materials`} eyebrow="Course knowledge" description="Upload PDF or DOCX files. Document processing and retrieval remain backend-owned." />
      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <Card><CardTitle>Upload material</CardTitle><form onSubmit={upload} className="mt-4 space-y-4"><Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field><Field label="PDF or DOCX"><Input type="file" accept=".pdf,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>{error ? <p className="text-sm text-red-700">{error}</p> : null}<Button disabled={!file}>Upload</Button></form></Card>
        <Card><CardTitle>Materials</CardTitle><div className="mt-4">{materials.loading ? <LoadingState /> : materials.data?.length ? <Table columns={["Title", "Filename", "Status", "Uploaded"]} rows={materials.data.map((item) => [item.title, item.original_filename, <Badge tone={statusTone(item.processing_status)}>{item.processing_status}</Badge>, formatDate(item.created_at)])} /> : <EmptyState title="No materials uploaded." />}</div></Card>
      </div>
    </>
  );
}
