import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.db.models import (
    Tenant,
    User,
    Membership,
    CandidateProfile,
    EvidenceChunk,
    JobPosting,
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

        result = await session.execute(
            select(JobPosting).where(
                JobPosting.tenant_id == tenant.id,
                JobPosting.title == "AI Platform Engineer",
            )
        )
        if not result.scalar_one_or_none():
            jobs = [
                JobPosting(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    title="AI Platform Engineer",
                    company="Berlin AI GmbH",
                    url="https://example.com/jobs/ai-platform-engineer",
                    location="Berlin, Germany",
                    raw_jd="""## AI Platform Engineer — Berlin AI GmbH

We are looking for an AI Platform Engineer to join our team in Berlin.

### Requirements
- 5+ years of experience in software engineering
- Strong experience with Kubernetes and Docker
- Experience building ML platforms and LLM serving infrastructure
- Proficiency in Python and FastAPI
- Experience with monitoring and observability tools (Prometheus, Grafana)
- Fluent English; German is a plus

### Nice to Have
- Experience with Ray Serve or similar ML serving frameworks
- Knowledge of MLOps best practices
- Experience with PostgreSQL and Redis

### What We Offer
- Competitive salary (€90k–€120k)
- Hybrid work model
- Berlin office with flexible hours
""",
                    status="new",
                ),
                JobPosting(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    title="MLOps Engineer",
                    company="Munich Data Labs",
                    url="https://example.com/jobs/mlops-engineer",
                    location="Munich, Germany",
                    raw_jd="""## MLOps Engineer — Munich Data Labs

Join our MLOps team in Munich to build and maintain our ML infrastructure.

### Requirements
- 3+ years of experience in MLOps or related role
- Expertise in Docker, Kubernetes, and CI/CD pipelines
- Experience with MLflow, Airflow, or similar orchestration tools
- Solid Python skills
- Experience with cloud platforms (AWS or GCP)
- German language proficiency (B2+)

### Nice to Have
- Experience with feature stores
- Knowledge of model monitoring and observability
- Experience with Terraform or similar IaC tools

### What We Offer
- Salary range €80k–€110k
- On-site preference with hybrid options
- Munich location with great public transport access
""",
                    status="new",
                ),
                JobPosting(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    title="Backend Cloud Engineer",
                    company="SwissTech Solutions",
                    url="https://example.com/jobs/backend-cloud-engineer",
                    location="Zurich, Switzerland",
                    raw_jd="""## Backend Cloud Engineer — SwissTech Solutions

We are building the next generation of cloud-native applications and need a Backend Cloud Engineer in Zurich.

### Requirements
- 4+ years of backend development experience
- Strong Python and FastAPI skills
- Experience with cloud services (AWS/GCP/Azure)
- Knowledge of PostgreSQL and Redis
- Experience with containerization and Kubernetes
- English required; German is a plus

### Nice to Have
- Experience with event-driven architectures
- Knowledge of infrastructure as code (Terraform)
- Experience with monitoring and logging stacks

### What We Offer
- Competitive Swiss salary (CHF 120k–CHF 150k)
- Modern Zurich office
- Remote-friendly policy
""",
                    status="new",
                ),
            ]
            session.add_all(jobs)

        await session.commit()
        print("Demo data seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_demo())
