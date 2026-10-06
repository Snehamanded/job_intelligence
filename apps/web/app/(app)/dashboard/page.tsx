import { Pipeline } from "@/components/crm/pipeline";
import { HighMatchJobs } from "@/components/jobs/high-match-jobs";
import { PageHeader } from "@/components/page-header";
import { ResumeInsights } from "@/components/resume/resume-insights";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Your job search at a glance." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Pipeline</CardTitle>
            <CardDescription>Applications by stage.</CardDescription>
          </CardHeader>
          <CardContent>
            <Pipeline />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>High-match jobs</CardTitle>
            <CardDescription>Eligible jobs scoring 85 or higher.</CardDescription>
          </CardHeader>
          <CardContent>
            <HighMatchJobs />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Resume insights</CardTitle>
            <CardDescription>Skills, experience and gaps from your resume.</CardDescription>
          </CardHeader>
          <CardContent>
            <ResumeInsights />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
