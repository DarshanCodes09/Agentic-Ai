import { useParams } from "react-router-dom";
import { analyticsApi } from "../../api/analytics";
import { BarMetricChart } from "../../components/charts/Charts";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Card, CardTitle } from "../../components/ui/Card";
import { ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";

export function FacultyAnalyticsPage() {
  const subjectId = Number(useParams().subjectId);
  const summary = useAsync(() => analyticsApi.facultySubject(subjectId), [subjectId]);
  const concepts = useAsync(() => analyticsApi.facultyConcepts(subjectId), [subjectId]);
  const gaps = useAsync(() => analyticsApi.facultyGaps(subjectId), [subjectId]);
  if (summary.loading) return <LoadingState label="Loading class analytics" />;
  if (summary.error) return <ErrorState message={summary.error} onRetry={summary.refetch} />;
  const data = summary.data;
  const distribution = Object.entries(data?.performance_distribution ?? {}).map(([range, count]) => ({ range, count }));
  return (
    <>
      <PageHeader title={`${data?.subject_name} analytics`} eyebrow={data?.subject_code} description="Class performance, completion, concept mastery, and learning gap priorities." />
      {data ? <div className="grid gap-6">
        <div className="grid gap-4 md:grid-cols-4">
          <Metric label="Enrollment" value={data.enrolled_student_count} />
          <Metric label="Submissions" value={data.total_submissions_count} />
          <Metric label="Evaluated" value={data.evaluated_submissions_count} />
          <Metric label="Completion" value={`${Math.round(data.completion_rate)}%`} />
        </div>
        <Card><CardTitle>Score distribution</CardTitle><div className="mt-4"><BarMetricChart data={distribution} nameKey="range" valueKey="count" max={Math.max(5, ...distribution.map((item) => item.count))} /></div></Card>
        <Card><CardTitle>Class concept mastery</CardTitle><div className="mt-4"><Table columns={["Concept", "Mastery", "Level", "Students"]} rows={(concepts.data ?? []).map((item) => [item.concept, `${Math.round(item.average_mastery * 100)}%`, <Badge tone={statusTone(item.mastery_level)}>{item.mastery_level}</Badge>, item.assessed_student_count])} /></div></Card>
        <Card><CardTitle>Learning gaps</CardTitle><div className="mt-4"><Table columns={["Concept", "Average mastery", "Affected students", "Severity", "Evidence"]} rows={(gaps.data ?? []).map((gap) => [gap.concept, `${Math.round(gap.average_mastery * 100)}%`, gap.affected_student_count, <Badge tone={statusTone(gap.severity)}>{gap.severity}</Badge>, gap.sample_evidence.slice(0, 2).join(" ")])} /></div></Card>
      </div> : null}
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <Card><p className="text-xs uppercase tracking-wide text-muted">{label}</p><p className="mt-2 text-3xl font-semibold">{value}</p></Card>;
}
