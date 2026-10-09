import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { analyticsApi } from "../../api/analytics";
import { getApiErrorMessage } from "../../api/client";
import { subjectsApi } from "../../api/subjects";
import { PageHeader } from "../../components/common/PageHeader";
import { ScoreDisplay } from "../../components/common/ScoreDisplay";
import { TrendChart } from "../../components/charts/Charts";
import { Badge, statusTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardTitle } from "../../components/ui/Card";
import { Field, Input } from "../../components/ui/Input";
import { ErrorState, LoadingState, EmptyState } from "../../components/ui/State";
import { useAsync } from "../../hooks/useAsync";

export function StudentDashboardPage() {
  const summary = useAsync(analyticsApi.studentOverall, []);
  const gaps = useAsync(analyticsApi.studentGaps, []);
  const trends = useAsync(analyticsApi.studentTrends, []);
  const subjects = useAsync(subjectsApi.list, []);
  const [courseCode, setCourseCode] = useState("");
  const [joinLoading, setJoinLoading] = useState(false);
  const [joinError, setJoinError] = useState("");
  const [joinSuccess, setJoinSuccess] = useState("");

  async function joinCourse(event: FormEvent) {
    event.preventDefault();
    const normalizedCode = courseCode.trim();
    setJoinError("");
    setJoinSuccess("");
    if (!normalizedCode) {
      setJoinError("Enter a course code from your faculty member.");
      return;
    }

    setJoinLoading(true);
    try {
      await subjectsApi.joinByCode(normalizedCode);
      setCourseCode("");
      setJoinSuccess(`Joined ${normalizedCode.toUpperCase()}.`);
      subjects.refetch();
      summary.refetch();
    } catch (err) {
      setJoinError(getApiErrorMessage(err));
    } finally {
      setJoinLoading(false);
    }
  }

  if (summary.loading) return <LoadingState label="Loading student overview" />;
  if (summary.error) return <ErrorState message={summary.error} onRetry={summary.refetch} />;

  const data = summary.data;
  return (
    <>
      <PageHeader title="Student overview" eyebrow="Your work" description="A focused view of evaluated assessments, concept strengths, and learning gaps." />
      {data ? (
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="lg:col-span-2">
            <div className="grid gap-6 lg:grid-cols-[0.75fr_1.25fr]">
              <div>
                <CardTitle>Join Course</CardTitle>
                <p className="mt-2 text-sm leading-6 text-muted">Enter the course code shared by your faculty member.</p>
              </div>
              <form onSubmit={joinCourse} className="space-y-3">
                <Field label="Course code">
                  <Input
                    value={courseCode}
                    onChange={(event) => setCourseCode(event.target.value)}
                    placeholder="CS101"
                    autoCapitalize="characters"
                  />
                </Field>
                {joinError ? <p className="text-sm text-red-700">{joinError}</p> : null}
                {joinSuccess ? <p className="text-sm text-emerald-700">{joinSuccess}</p> : null}
                <Button disabled={joinLoading}>{joinLoading ? "Joining..." : "Join Course"}</Button>
              </form>
            </div>
          </Card>
          <Card>
            <ScoreDisplay value={data.overall_percentage} label="Overall percentage" />
            <div className="mt-6 grid gap-4 border-t border-line pt-5 sm:grid-cols-3">
              <Stat label="Evaluated" value={data.total_assessments_evaluated} />
              <Stat label="Subjects" value={data.enrolled_subjects_count} />
              <Stat label="Average score" value={data.average_score.toFixed(1)} />
            </div>
          </Card>
          <Card>
            <CardTitle>My Courses</CardTitle>
            <div className="mt-4 space-y-3">
              {subjects.loading ? <LoadingState /> : subjects.data?.length ? subjects.data.slice(0, 5).map((subject) => (
                <Link
                  key={subject.id}
                  to={`/student/subjects/${subject.id}`}
                  className="block rounded-md border border-line p-3 transition hover:bg-stone-50"
                >
                  <p className="text-sm font-semibold text-muted">{subject.code}</p>
                  <p className="mt-1 font-medium text-ink">{subject.name}</p>
                </Link>
              )) : <EmptyState title="No joined courses yet." body="Use a faculty course code to join your first course." />}
            </div>
          </Card>
          <Card>
            <CardTitle>Strongest concepts</CardTitle>
            <ConceptList items={data.strongest_concepts} />
          </Card>
          <Card className="lg:col-span-2">
            <CardTitle>Recent assessment activity</CardTitle>
            <div className="mt-4">
              {trends.loading ? <LoadingState /> : <TrendChart data={trends.data ?? []} />}
            </div>
          </Card>
          <Card>
            <CardTitle>Weakest concepts</CardTitle>
            <ConceptList items={data.weakest_concepts} />
          </Card>
          <Card>
            <CardTitle>Learning gaps</CardTitle>
            <div className="mt-4 space-y-3">
              {gaps.data?.length ? gaps.data.slice(0, 4).map((gap) => (
                <div key={`${gap.concept}-${gap.subject_id}`} className="flex items-start justify-between gap-3 border-b border-line pb-3 last:border-0">
                  <div>
                    <p className="font-medium">{gap.concept}</p>
                    <p className="text-sm text-muted">{gap.subject_name ?? "General"} · {Math.round(gap.mastery_score * 100)}%</p>
                  </div>
                  <Badge tone={statusTone(gap.severity)}>{gap.severity}</Badge>
                </div>
              )) : <EmptyState title="No learning gaps identified." />}
            </div>
          </Card>
        </div>
      ) : null}
      <Link className="mt-6 inline-block text-sm font-medium text-ink underline" to="/student/analytics">Open full analytics</Link>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return <div><p className="text-xs uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-2xl font-semibold">{value}</p></div>;
}

function ConceptList({ items }: { items: { concept: string; mastery_score: number; mastery_level: string }[] }) {
  if (!items.length) return <EmptyState title="No concepts yet." body="Concept mastery appears after evaluation." />;
  return (
    <div className="mt-4 space-y-3">
      {items.slice(0, 5).map((item) => (
        <div key={item.concept} className="flex items-center justify-between gap-4">
          <div><p className="font-medium">{item.concept}</p><p className="text-sm text-muted">{item.mastery_level}</p></div>
          <span className="text-sm font-semibold">{Math.round(item.mastery_score * 100)}%</span>
        </div>
      ))}
    </div>
  );
}
