from uuid import UUID

from app.modules.llm_gateway.schemas import (
    FitExplanation,
    GeneratedResume,
    ParsedJobPosting,
    ScreeningAnswerSet,
)


class FakeLLMGateway:
    async def run_json(
        self,
        tenant_id: UUID,
        task: str,
        prompt_version: str,
        messages: list[dict],
        output_schema,
        **kwargs,
    ):
        if task == "jd_extract":
            return ParsedJobPosting(
                title="Software Engineer",
                company="Example GmbH",
                location="Berlin",
                work_model="hybrid",
                language_requirements=["German (C1)", "English (B2)"],
                must_have_skills=["Python", "AWS"],
                nice_to_have_skills=["Kubernetes"],
                salary_range="75.000 - 95.000 €",
                seniority="Senior",
                dach_signals={"visa_sponsorship": "yes"},
            )
        elif task == "fit_explanation":
            return FitExplanation(
                overall_score=82.5,
                recommendation="apply",
                breakdown={
                    "skills_match": 85.0,
                    "experience": 80.0,
                    "language_fit": 90.0,
                    "location": 75.0,
                },
                top_reasons=[
                    "Strong Python experience",
                    "Relevant industry background",
                    "Fluent German",
                ],
                gaps=["No Kubernetes experience"],
                explanation="The candidate is a strong match with solid Python experience and fluent German.",
            )
        elif task == "resume_generate":
            return GeneratedResume(
                html_content="<html><body><h1>John Doe</h1><p>Senior Engineer</p></body></html>",
                provenance=[
                    {
                        "bullet": "Senior Engineer at Acme (2019-2024)",
                        "source_chunk_ids": ["chunk-1"],
                    }
                ],
            )
        elif task == "screening_answer":
            return ScreeningAnswerSet(
                answers=[
                    {
                        "question": "Why do you want this job?",
                        "answer": "I have relevant experience.",
                    }
                ],
            )
        else:
            raise ValueError(f"Unknown task: {task}")
