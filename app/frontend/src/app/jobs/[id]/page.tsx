import JobDetailClient from './job-detail-client';

export const revalidate = 0;

export async function generateStaticParams() {
  return [];
}

export default function JobDetailPage() {
  return <JobDetailClient />;
}
