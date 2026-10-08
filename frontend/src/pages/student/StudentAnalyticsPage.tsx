import { analyticsApi } from "../../api/analytics";
import { BarMetricChart, TrendChart } from "../../components/charts/Charts";
import { PageHeader } from "../../components/common/PageHeader";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Card, CardTitle } from "../../components/ui/Card";
import { ErrorState, LoadingState } from "../../components/ui/State";
import { Table } from "../../components/ui/Table";
import { useAsync } from "../../hooks/useAsync";

export function StudentAnalyticsPage() {
  const overall = useAsync(analyticsApi.studentOverall, []);
  const subjects = useAsync(analyticsApi.studentSubjects, []);
  const concepts = useAsync(analyticsApi.studentConcepts, []);
  const gaps = useAsync(analyticsApi.studentGaps, []);
  const trends = useAsync(analyticsApi.studentTrends, []);
  if (overall.loading) return <LoadingState label="Loading analytics" />;
  if (overall.error) return <ErrorState message={overall.error} onRetry={overall.refetch} />;
  return (
    <>
      <PageHeader title="Analytics" eyebrow="Performance" description="Subject performance, concept mastery, learning gaps, and chronological assessment trend." />
      <div className="grid gap-6">
        <Card><CardTitle>Performance trend</CardTitle><div className="mt-4"><TrendChart data={trends.data ?? []} /></div></Card>
        <Card><CardTitle>Subject performance</CardTitle><div className="mt-4"><BarMetricChart data={subjects.data ?? []} nameKey="subject_code" valueKey="percentage" /></div></Card>
        <Card>
          <CardTitle>Concept mastery</CardTitle>
          <div className="mt-4"><Table columns={["Concept", "Mastery", "Level", "Assessments"]} rows={(concepts.data ?? []).map((item) => [item.concept, `${Math.round(item.mastery_score * 100)}%`, <Badge tone={statusTone(item.mastery_level)}>{item.mastery_level}</Badge>, item.assessment_count])} /></div>
        </Card>
        <Card>
          <CardTitle>Learning gaps</CardTitle>
          <div className="mt-4"><Table columns={["Concept", "Subject", "Severity", "Evidence"]} rows={(gaps.data ?? []).map((gap) => [gap.concept, gap.subject_name ?? "General", <Badge tone={statusTone(gap.severity)}>{gap.severity}</Badge>, gap.evidence.slice(0, 2).join(" ")])} /></div>
        </Card>
      </div>
    </>
  );
}
