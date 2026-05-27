"""Sample resume JSON used across the test suite.

Two shapes are exposed:

  - ``SAMPLE_RESUME`` — a fully populated resume covering every section the
    PDF / DOCX / ODT generators render. Use this as the input for any test
    that exercises generation, rescoring, or export.
  - ``MINIMAL_RESUME`` — the smallest valid shape (personal_info + summary).
    Use this to check generators degrade gracefully when sections are absent.

Tests should ALWAYS deep-copy these before mutating.
"""
from __future__ import annotations


SAMPLE_RESUME: dict = {
    "metadata": {
        "version": "1",
        "overall_score": 88,
        "ats_score": 90,
        "quality_score": 87,
        "impact_score": 86,
        "completeness_score": 89,
        "jd_match_score": 92,
        "jd_tailored": True,
        "jd_role": "Senior Backend Engineer",
        "manually_edited": False,
        "manual_edit_count": 0,
        "iteration_count": 2,
        "review_notes": "Strong impact bullets, ATS-friendly formatting.",
        "improvement_suggestions": [
            "Quantify the open-source impact in one more bullet.",
            "Add a brief leadership bullet for the staff role.",
        ],
        "keywords_included": ["Python", "FastAPI", "PostgreSQL", "AWS"],
        "keywords_to_consider": ["Kubernetes", "Terraform"],
        "generated_at": "2026-05-24T12:00:00+00:00",
        "llm_provider": "fake",
        "llm_model": "fake-test",
    },
    "personal_info": {
        "full_name": "Ada Lovelace",
        "professional_title": "Senior Software Engineer",
        "email": "ada@example.com",
        "phone": "+1-555-0100",
        "location": "London, UK",
        "linkedin": "https://linkedin.com/in/ada",
        "github": "https://github.com/ada",
        "website": "https://ada.dev",
    },
    "professional_summary": (
        "Senior backend engineer with 8 years of experience scaling Python "
        "platforms in fintech and developer tooling. Owns systems end-to-end."
    ),
    "core_competencies": [
        "Distributed systems", "API design", "Async Python", "Observability",
        "Mentorship", "Incident response",
    ],
    "experience": [
        {
            "company": "Acme Fintech",
            "title": "Staff Engineer",
            "location": "London, UK",
            "start_date": "2022-01",
            "end_date": "Present",
            "responsibilities": [
                "Led design of a multi-region payments service handling 50k rps.",
                "Mentored 6 engineers; owned the on-call rotation for 12 services.",
            ],
            "achievements": [
                "Cut p99 latency by 62% by rewriting hot path in async Python.",
                "Saved $480k/yr by migrating batch jobs from EC2 to ECS Fargate.",
            ],
            "technologies": ["Python", "FastAPI", "PostgreSQL", "AWS", "Terraform"],
        },
        {
            "company": "Initech",
            "title": "Senior Backend Engineer",
            "location": "Remote",
            "start_date": "2019-04",
            "end_date": "2021-12",
            "responsibilities": [
                "Built the company's first event-driven ingestion pipeline.",
            ],
            "achievements": [
                "Onboarded 14 enterprise customers via the new pipeline in 6 months.",
            ],
            "technologies": ["Python", "Kafka", "DynamoDB"],
        },
    ],
    "education": [
        {
            "institution": "University of Cambridge",
            "degree": "B.A. Computer Science",
            "graduation_year": 2017,
            "gpa": "First Class",
        }
    ],
    "technical_skills": {
        "programming_languages": ["Python", "Go", "TypeScript"],
        "frameworks_and_libraries": ["FastAPI", "Django", "LangChain"],
        "databases": ["PostgreSQL", "Redis", "DynamoDB"],
        "cloud_and_infrastructure": ["AWS", "Terraform", "Kubernetes", "Docker"],
        "tools_and_practices": ["Git", "GitHub Actions", "OpenTelemetry"],
    },
    "projects": [
        {
            "name": "StackResume",
            "role": "Creator",
            "url": "https://github.com/example/stackresume",
            "year": 2026,
            "technologies": ["Python", "FastAPI", "LangGraph"],
            "description": "Multi-agent AI resume builder.",
        }
    ],
    "certifications": [
        {"name": "AWS Solutions Architect — Associate", "issuer": "AWS", "year": 2024},
    ],
    "open_source_contributions": [
        {"project": "FastAPI", "contribution": "Patched the OpenAPI generator.", "year": 2023},
    ],
    "publications": [],
    "patents": [],
    "awards_and_honors": [
        {"name": "Engineer of the Quarter", "issuer": "Acme Fintech", "year": 2024},
    ],
    "volunteer_experience": [],
    "languages": [
        {"language": "English", "proficiency": "Native"},
        {"language": "French", "proficiency": "Professional"},
    ],
    "interests": ["Open source", "Mountaineering"],
}


MINIMAL_RESUME: dict = {
    "metadata": {"version": "1", "overall_score": 70},
    "personal_info": {
        "full_name": "Grace Hopper",
        "professional_title": "Software Engineer",
        "email": "grace@example.com",
    },
    "professional_summary": "Backend engineer.",
    "experience": [],
    "education": [],
    "technical_skills": {},
}
