import asyncio
import uuid

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.models import (
    CandidateProfile,
    EvidenceChunk,
    JobPosting,
    MatchReport,
    Membership,
    ResumeArtifact,
    Tenant,
    User,
)
from app.db.session import async_session_factory


async def seed_demo():
    async with async_session_factory() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == "dachjob-local"))
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                slug="dachjob-local",
                name="Dachjob Local",
            )
            session.add(tenant)
            await session.flush()

        result = await session.execute(select(User).where(User.email == "demo@dachjob.ai"))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id=uuid.uuid4(),
                email="demo@dachjob.ai",
                name="Demo User",
                password_hash=hash_password("demo1234"),
            )
            session.add(user)
            await session.flush()
        elif not user.password_hash:
            user.password_hash = hash_password("demo1234")

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
            select(CandidateProfile).where(CandidateProfile.tenant_id == tenant.id)
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
                    metadata_json={
                        "section": "experience",
                        "dates": "2021–Present",
                        "tags": ["llm", "kubernetes", "fastapi"],
                    },
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: TechCorp Berlin",
                    content="Built an automated ML pipeline orchestration system with Airflow and MLflow, handling 200+ daily training runs.",
                    metadata_json={
                        "section": "experience",
                        "dates": "2021–Present",
                        "tags": ["mlops", "airflow", "mlflow"],
                    },
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: TechCorp Berlin",
                    content="Implemented real-time model monitoring and observability using Prometheus, Grafana, and custom alerting rules.",
                    metadata_json={
                        "section": "experience",
                        "dates": "2021–Present",
                        "tags": ["monitoring", "prometheus", "grafana"],
                    },
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: DataFlow Munich",
                    content="Developed a feature store using Redis and PostgreSQL, serving 500+ features to production ML models.",
                    metadata_json={
                        "section": "experience",
                        "dates": "2018–2021",
                        "tags": ["feature-store", "redis", "postgresql"],
                    },
                ),
                EvidenceChunk(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    profile_id=profile.id,
                    source_type="cv",
                    source_label="Experience: DataFlow Munich",
                    content="Containerized ML workloads with Docker and Kubernetes, achieving 99.95% uptime for critical inference services.",
                    metadata_json={
                        "section": "experience",
                        "dates": "2018–2021",
                        "tags": ["docker", "kubernetes", "mlops"],
                    },
                ),
            ]
            session.add_all(chunks)

        legacy_result = await session.execute(
            select(JobPosting)
            .where(
                JobPosting.tenant_id == tenant.id,
                JobPosting.url.like("https://example.com/jobs/%"),
            )
            .order_by(JobPosting.created_at)
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

**Location:** Germany - Remote
**Req ID:** CSQ327R197
**Recruiter:** Dina Hussain

### Mission
The AI Forward Deployed Engineering (AI FDE) team is a highly specialized customer-facing AI team at Databricks. We deliver professional services engagements to help our customers build and productionize first-of-its-kind AI applications. We work cross-functionally to shape long-term strategic priorities and initiatives alongside engineering, product, and developer relations, as well as support internal subject matter expert (SME) teams. We view our team as an ensemble: we look for individuals with strong, unique specializations to improve the overall strength of the team. This team is the right fit for you if you love working with customers, teammates, and fueling your curiosity for the latest trends in GenAI, LLMOps, and ML more broadly.

We welcome remote applicants located near our offices. Preferred locations (in priority order): London (UK), Madrid (Spain), Paris (France), and Amsterdam (NL).

Reporting to: Senior Manager - AI FDE, EMEA

### The Impact You Will Have
- Develop cutting-edge GenAI solutions, incorporating the latest techniques from Databricks AI research to solve customer problems
- Own production rollouts of consumer and internally facing GenAI applications
- Serve as a trusted technical advisor to customers across a variety of domains
- Present at conferences such as Data + AI Summit, recognized as a thought leader internally and externally
- Collaborate cross-functionally with the product and engineering teams to influence priorities and shape the product roadmap

### What We Look For
- Experience building GenAI applications, including RAG, multi-agent systems, Text2SQL, fine-tuning, etc., with tools such as HuggingFace, LangChain, and DSPy
- Expertise in deploying production-grade GenAI applications, including evaluation and optimizations
- Extensive years of hands-on industry data science experience, leveraging common machine learning and data science tools, i.e. pandas, scikit-learn, PyTorch, etc.
- Experience building production-grade machine learning deployments on AWS, Azure, or GCP
- Graduate degree in a quantitative discipline (Computer Science, Engineering, Statistics, Operations Research, etc.) or equivalent practical experience
- Experience communicating and/or teaching technical concepts to non-technical and technical audiences alike
- Passion for collaboration, life-long learning, and driving business value through AI
- [Preferred] Experience using the Databricks Intelligence Platform and Apache Spark to process large-scale distributed datasets
- Willing to travel once every 4-8 weeks to see customers (as needed)

### About Databricks
Databricks is the data and AI company. More than 10,000 organizations worldwide — including Comcast, Condé Nast, Grammarly, and over 50% of the Fortune 500 — rely on the Databricks Data Intelligence Platform to unify and democratize data, analytics and AI. Databricks is headquartered in San Francisco, with offices around the globe and was founded by the original creators of Lakehouse, Apache Spark, Delta Lake and MLflow.

### Benefits
At Databricks, we strive to provide comprehensive benefits and perks that meet the needs of all of our employees. For specific details on the benefits offered in your region click here.

### Our Commitment to Diversity and Inclusion
At Databricks, we are committed to fostering a diverse and inclusive culture where everyone can excel. We take great care to ensure that our hiring practices are inclusive and meet equal employment opportunity standards. Individuals looking for employment at Databricks are considered without regard to age, color, disability, ethnicity, family or marital status, gender identity or expression, language, national origin, physical and mental ability, political affiliation, race, religion, sexual orientation, socio-economic status, veteran status, and other protected characteristics.

### Compliance
If access to export-controlled technology or source code is required for performance of job duties, it is within Employer's discretion whether to apply for a U.S. government license for such positions, and Employer may decline to proceed with an applicant on this basis alone.
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
                await session.execute(delete(ResumeArtifact).where(ResumeArtifact.job_id == job.id))
                await session.flush()
                await session.execute(delete(MatchReport).where(MatchReport.job_id == job.id))

        await session.commit()
        print("Demo data seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_demo())
