import asyncio
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.db.models import (
    Tenant,
    User,
    Membership,
    CandidateProfile,
    EvidenceChunk,
    JobPosting,
    MatchReport,
    ResumeArtifact,
)


async def seed_demo():
    async with async_session_factory() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.slug == "dachjob-local")
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                slug="dachjob-local",
                name="Dachjob Local",
            )
            session.add(tenant)
            await session.flush()

        result = await session.execute(
            select(User).where(User.email == "demo@dachjob.ai")
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id=uuid.uuid4(),
                email="demo@dachjob.ai",
                name="Demo User",
            )
            session.add(user)
            await session.flush()

        result = await session.execute(
            select(Membership).where(
                Membership.tenant_id == tenant.id,
                Membership.user_id == user.id,
            )
        )
        if not result.scalar_one_or_none():
            session.add(
                Membership(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    user_id=user.id,
                    role="owner",
                )
            )

        result = await session.execute(
            select(CandidateProfile).where(
                CandidateProfile.tenant_id == tenant.id
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            profile = CandidateProfile(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                full_name="Demo User",
                headline="Senior AI Platform Engineer",
                location="Berlin, Germany",
                timezone="Europe/Berlin",
                raw_cv_md="""# Demo User

## Summary
Senior AI Platform Engineer with 8+ years of experience building ML infrastructure, LLM serving systems, and large-scale data platforms.

## Experience

### Senior AI Platform Engineer — TechCorp Berlin (2021–Present)
- Designed and deployed a multi-model LLM serving platform using FastAPI, Ray Serve, and Kubernetes, reducing inference latency by 40%.
- Built an automated ML pipeline orchestration system with Airflow and MLflow, handling 200+ daily training runs.
- Implemented real-time model monitoring and observability using Prometheus, Grafana, and custom alerting rules.

### MLOps Engineer — DataFlow Munich (2018–2021)
- Developed a feature store using Redis and PostgreSQL, serving 500+ features to production ML models.
- Containerized ML workloads with Docker and Kubernetes, achieving 99.95% uptime for critical inference services.
- Created a model versioning and A/B testing framework that reduced regression introduction by 60%.

## Skills
Python, FastAPI, Kubernetes, Docker, Ray, Airflow, MLflow, Prometheus, Grafana, PostgreSQL, Redis, Terraform, AWS, GCP, PyTorch, TensorFlow, LLM serving, MLOps, CI/CD.

## Languages
English (Fluent), German (B2), Mandarin (Native)
""",
            )
            session.add(profile)
            await session.flush()

            chunks = [
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: TechCorp Berlin",
                    content="Designed and deployed a multi-model LLM serving platform using FastAPI, Ray Serve, and Kubernetes, reducing inference latency by 40%.",
                    metadata_json={"section": "experience", "dates": "2021–Present", "tags": ["llm", "kubernetes", "fastapi"]},
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: TechCorp Berlin",
                    content="Built an automated ML pipeline orchestration system with Airflow and MLflow, handling 200+ daily training runs.",
                    metadata_json={"section": "experience", "dates": "2021–Present", "tags": ["mlops", "airflow", "mlflow"]},
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: TechCorp Berlin",
                    content="Implemented real-time model monitoring and observability using Prometheus, Grafana, and custom alerting rules.",
                    metadata_json={"section": "experience", "dates": "2021–Present", "tags": ["monitoring", "prometheus", "grafana"]},
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: DataFlow Munich",
                    content="Developed a feature store using Redis and PostgreSQL, serving 500+ features to production ML models.",
                    metadata_json={"section": "experience", "dates": "2018–2021", "tags": ["feature-store", "redis", "postgresql"]},
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: DataFlow Munich",
                    content="Containerized ML workloads with Docker and Kubernetes, achieving 99.95% uptime for critical inference services.",
                    metadata_json={"section": "experience", "dates": "2018–2021", "tags": ["docker", "kubernetes", "mlops"]},
                ),
            ]
            session.add_all(chunks)

        legacy_result = await session.execute(
            select(JobPosting).where(
                JobPosting.tenant_id == tenant.id,
                JobPosting.url.like("https://example.com/jobs/%"),
            ).order_by(JobPosting.created_at)
        )
        legacy_jobs = list(legacy_result.scalars().all())

        demo_jobs = [
            {
                "title": "AI Engineer - FDE (Forward Deployed Engineer)",
                "company": "Databricks",
                "url": "https://www.linkedin.com/jobs/view/4414035441/",
                "location": "Munich, Bavaria, Germany",
                "raw_jd": """## AI Engineer - FDE (Forward Deployed Engineer) — Databricks

LinkedIn source: https://www.linkedin.com/jobs/view/4414035441/

### Role summary
Customer-facing AI Forward Deployed Engineering role focused on helping enterprise customers build and productionize first-of-its-kind GenAI applications. The role is listed in Munich, with the posting also describing Germany-remote eligibility and EMEA collaboration.

### Responsibilities
- Build GenAI solutions for customer problems using current Databricks AI research and platform capabilities.
- Own production rollouts for internal and consumer-facing GenAI applications.
- Act as a trusted technical advisor for customers across domains.
- Collaborate with product and engineering teams to influence roadmap priorities.
- Share technical ideas through customer work, internal thought leadership, and conferences.

### Requirements
- Experience building GenAI applications such as RAG, multi-agent systems, Text2SQL, fine-tuning, or similar systems.
- Hands-on use of tools and frameworks such as Hugging Face, LangChain, DSPy, pandas, scikit-learn, and PyTorch.
- Experience deploying and evaluating production-grade GenAI or ML applications.
- Cloud ML deployment experience on AWS, Azure, or GCP.
- Strong communication skills with technical and non-technical audiences.
- Preferred: Databricks platform, Apache Spark, large-scale data processing, and willingness to travel periodically for customer work.
""",
            },
            {
                "title": "Senior Software / ML Engineer (Python) (f/m/d)",
                "company": "Digitec Galaxus AG",
                "url": "https://www.linkedin.com/jobs/view/4414349687/",
                "location": "Zurich, Switzerland",
                "raw_jd": """## Senior Software / ML Engineer (Python) (f/m/d) — Digitec Galaxus AG

LinkedIn source: https://www.linkedin.com/jobs/view/4414349687/

### Role summary
Backend Software/ML Engineering role for the Digitec and Galaxus e-commerce platform, focused on Order Management and Finance domains. The role combines Python ownership, document interpretation, and applied LLM/VLM systems.

### Responsibilities
- Work in a cross-functional engineering team on order management and finance systems.
- Lead the evolution of a distributed document interpretation system that classifies PDFs and extracts structured data with Vision Language Models.
- Own the evaluation pipeline and improve scoring correctness.
- Track emerging LLM and ML trends and apply them to practical business problems.
- Mentor C# engineers on Python best practices while contributing across the broader stack.

### Requirements
- Computer science degree or equivalent professional experience.
- 3-5+ years as a software engineer or ML engineer, with Python as the primary language.
- Additional experience with Java or C#.
- Experience integrating LLMs or VLMs into real business workflows, including evaluation and metrics.
- SQL and relational database experience; BigQuery is a plus.
- Data orchestration experience such as Dagster or Airflow.
- Messaging or streaming experience such as Azure Service Bus or Kafka.
- DevOps mindset and familiarity with GCP, Kubernetes, Docker, or Terraform.
- English working proficiency; German is a plus.
""",
            },
            {
                "title": "Senior DevOps & Cloud Platform Engineer, CH",
                "company": "vector8",
                "url": "https://www.linkedin.com/jobs/view/4417727434/",
                "location": "Zurich, Zurich, Switzerland",
                "raw_jd": """## Senior DevOps & Cloud Platform Engineer, CH — vector8

LinkedIn source: https://www.linkedin.com/jobs/view/4417727434/

### Role summary
Senior cloud platform engineering role for Swiss-market AI transformation projects. The role focuses on scalable infrastructure across Azure and AWS, Kubernetes, Docker, Terraform, and production operations.

### Responsibilities
- Design, implement, and operate scalable cloud infrastructure on Azure and AWS.
- Build and maintain CI/CD pipelines for automated deployment.
- Manage container orchestration and GitOps workflows with Kubernetes and Docker.
- Partner with development teams on integration and deployment.
- Monitor system performance, troubleshoot issues, and maintain high availability.
- Implement infrastructure as code and secure networking controls.
- Mentor junior team members and collaborate across teams.

### Requirements
- At least 5 years of commercial experience with Azure and/or AWS.
- Strong Kubernetes and Docker proficiency.
- Solid CI/CD automation knowledge, especially GitHub Actions.
- Microservices architecture experience.
- Infrastructure as code experience with Terraform, Ansible, or similar tools.
- Scripting skills in Python, Bash, or similar languages.
- Strong problem-solving, communication, and client-facing collaboration skills.
- Computer science degree or related background.
""",
            },
        ]

        for demo_job in demo_jobs:
            result = await session.execute(
                select(JobPosting).where(
                    JobPosting.tenant_id == tenant.id,
                    JobPosting.url == demo_job["url"],
                )
            )
            job = result.scalar_one_or_none()
            if job:
                job.title = demo_job["title"]
                job.company = demo_job["company"]
                job.location = demo_job["location"]
                job.raw_jd = demo_job["raw_jd"]
                job.status = "new"
            elif legacy_jobs:
                job = legacy_jobs.pop(0)
                job.title = demo_job["title"]
                job.company = demo_job["company"]
                job.url = demo_job["url"]
                job.location = demo_job["location"]
                job.raw_jd = demo_job["raw_jd"]
                job.parsed_json = None
                job.status = "new"
            else:
                session.add(
                    JobPosting(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        title=demo_job["title"],
                        company=demo_job["company"],
                        url=demo_job["url"],
                        location=demo_job["location"],
                        raw_jd=demo_job["raw_jd"],
                        status="new",
                    )
                )
                await session.flush()
                job = await session.scalar(
                    select(JobPosting).where(JobPosting.url == demo_job["url"])
                )

            if job:
                await session.execute(
                    delete(ResumeArtifact).where(ResumeArtifact.job_id == job.id)
                )
                await session.flush()
                await session.execute(
                    delete(MatchReport).where(MatchReport.job_id == job.id)
                )

        await session.commit()
        print("Demo data seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_demo())
