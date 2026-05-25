import json
import logging
import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import EvidenceChunk, MatchReport
from app.modules.jobs.repository import get_job, sync_job_skills
from app.modules.profiles.repository import get_profile_by_user

SKILL_PATTERNS = [
    ("Python", [r"\bpython\b"]),
    ("TypeScript", [r"\btypescript\b"]),
    ("JavaScript", [r"\bjavascript\b"]),
    ("Node.js", [r"\bnode(?:\.js)?\b"]),
    ("React", [r"\breact\b"]),
    ("Vue.js", [r"\bvue(?:\.js)?\b"]),
    ("SASS", [r"\bsass\b", r"\bscss\b"]),
    ("FastAPI", [r"\bfastapi\b"]),
    (
        "Go",
        [
            r"\bgolang\b",
            r"\bgo programming\b",
            r"\bgo language\b",
            r"\bpython or go\b",
            r"\bgo for testing\b",
        ],
    ),
    ("Java", [r"\bjava\b"]),
    ("Spring Boot", [r"\bspring boot\b"]),
    ("PHP", [r"\bphp\b"]),
    ("C#", [r"(?<!\w)c#(?!\w)", r"\bc sharp\b"]),
    ("C++", [r"(?<!\w)c\+\+(?!\w)"]),
    ("SQL", [r"\bsql\b"]),
    ("PostgreSQL", [r"\bpostgres(?:ql)?\b"]),
    ("MySQL", [r"\bmysql\b"]),
    ("MongoDB", [r"\bmongodb\b"]),
    ("Redis", [r"\bredis\b"]),
    (
        "Production databases",
        [r"production (?:database|databases|dbs)", r"databases in production"],
    ),
    ("Database performance", [r"database performance", r"performance, scaling, and reliability"]),
    ("GraphQL", [r"\bgraphql\b"]),
    ("Docker", [r"\bdocker\b"]),
    (
        "Containerization",
        [r"\bcontaineri[sz]ed\b", r"\bcontaineri[sz]ation\b", r"container-based deployments?"],
    ),
    ("Kubernetes", [r"\bkubernetes\b", r"\bk8s\b"]),
    ("GCP", [r"\bgcp\b", r"google cloud"]),
    ("Cloud Run", [r"\bcloud run\b"]),
    ("AWS", [r"\baws\b", r"amazon web services"]),
    ("Azure", [r"\bazure\b"]),
    ("Cloud infrastructure", [r"cloud infrastructure", r"infrastructure backbone"]),
    ("Cloud compute", [r"major cloud platform[^.\n]*compute", r"cloud[^.\n]*compute"]),
    ("Compute-intensive workloads", [r"compute-intensive workloads?"]),
    ("Scientific simulation workloads", [r"scientific simulation workloads?"]),
    ("Climate tech", [r"climate tech"]),
    ("Sustainability", [r"\bsustainability\b", r"\bsustainable\b"]),
    ("Built environment", [r"built environment"]),
    ("Cloud storage", [r"\bstorage\b"]),
    ("Networking", [r"\bnetworking\b", r"network architecture"]),
    ("Network architecture", [r"network architecture"]),
    ("Wireless networking", [r"wireless networking", r"wireless performance"]),
    ("4G/LTE", [r"\b4g/lte\b", r"\blte\b"]),
    ("5G", [r"\b5g\b"]),
    ("Wi-Fi", [r"\bwi-?fi\b"]),
    ("Mobile Edge Computing", [r"mobile edge computing", r"\bmec\b"]),
    ("TCP/IP", [r"\btcp/ip\b"]),
    ("UDP", [r"\budp\b"]),
    ("WebRTC", [r"\bwebrtc\b"]),
    ("gRPC", [r"\bgrpc\b"]),
    ("MQTT", [r"\bmqtt\b"]),
    ("ROS2/DDS", [r"\bros2/dds\b", r"\bros2\b", r"\bdds\b"]),
    ("RF engineering", [r"\brf engineering\b", r"\brf\b"]),
    ("Antenna design", [r"antenna design"]),
    ("Link budget analysis", [r"link budget analysis"]),
    ("IAM", [r"\biam\b", r"identity and access management"]),
    ("Authentication", [r"\bauthentication\b"]),
    ("Encryption", [r"\bencryption\b"]),
    ("Secure message passing", [r"secure message-passing", r"secure message passing"]),
    ("TLS", [r"\btls\b", r"\bssl\b"]),
    ("Firewall rules", [r"firewall rules?", r"\bfirewalls?\b"]),
    ("RBAC", [r"\brbac\b", r"role-based access control"]),
    ("Job queues", [r"job queues?", r"\bqueues?\b"]),
    ("Distributed workloads", [r"distributed workloads?"]),
    ("Distributed systems", [r"distributed systems?"]),
    ("Large-scale distributed systems", [r"large-scale distributed systems?"]),
    ("Search engines", [r"search engines?"]),
    ("Elasticsearch", [r"\belasticsearch\b"]),
    ("OpenSearch", [r"\bopensearch\b"]),
    ("Apache Solr", [r"apache solr", r"\bsolr\b"]),
    ("Apache Lucene", [r"apache lucene", r"\blucene\b"]),
    ("Event-driven architecture", [r"event-driven"]),
    ("Event-based analytics", [r"event-based analytics"]),
    ("A/B testing", [r"\ba/b (?:testing|experiments?)\b"]),
    ("Hypothesis building", [r"hypothesis building"]),
    ("Metrics", [r"\bmetrics\b"]),
    ("CI/CD pipelines", [r"\bci/cd\b", r"continuous integration", r"continuous deployment"]),
    ("GitHub Actions", [r"github actions"]),
    ("GitLab CI", [r"gitlab ci"]),
    ("Jenkins", [r"\bjenkins\b"]),
    ("Release management", [r"release process", r"release management", r"production deployment"]),
    ("Deployment workflows", [r"deployment workflows?", r"deployment process"]),
    ("Rollbacks", [r"\brollbacks?\b"]),
    ("Staging environments", [r"\bstaging\b"]),
    ("QA", [r"\bqa\b", r"quality assurance"]),
    ("E2E tests", [r"\be2e tests?\b", r"end-to-end tests?"]),
    ("Integration tests", [r"integration tests?"]),
    ("Developer experience", [r"developer experience", r"\bdx\b"]),
    ("On-call", [r"on-call", r"on call"]),
    ("Incident response", [r"incident response", r"severity processes?"]),
    ("Reliability engineering", [r"\breliability\b", r"ensure uptime", r"stable releases?"]),
    ("Observability", [r"\bobservability\b", r"\bobservable systems?\b"]),
    ("Monitoring", [r"\bmonitoring\b"]),
    ("Vulnerability scanning", [r"vulnerability scanning"]),
    ("Penetration testing", [r"penetration testing", r"\bpentest(?:ing)?\b"]),
    ("Infrastructure hardening", [r"infrastructure hardening", r"security hardening"]),
    ("Infrastructure engineering", [r"infrastructure engineering"]),
    ("Platform engineering", [r"platform engineering"]),
    ("Backend engineering", [r"backend engineering", r"backend codebase"]),
    ("Full-stack engineering", [r"full stack", r"full-stack"]),
    ("Frontend frameworks", [r"frontend application frameworks?", r"component-based frontend"]),
    ("Data-oriented codebases", [r"data-oriented codebases?"]),
    ("Terraform", [r"\bterraform\b"]),
    ("Infrastructure as Code", [r"infrastructure-as-code", r"infrastructure as code", r"\biac\b"]),
    ("Ansible", [r"\bansible\b"]),
    ("Pulumi", [r"\bpulumi\b"]),
    ("Kafka", [r"\bkafka\b"]),
    ("RabbitMQ", [r"\brabbitmq\b"]),
    ("Airflow", [r"\bairflow\b"]),
    ("Dagster", [r"\bdagster\b"]),
    ("MLflow", [r"\bmlflow\b"]),
    ("Machine Learning", [r"\bmachine learning\b", r"\bml\b"]),
    ("Deep Learning", [r"\bdeep learning\b"]),
    ("GenAI", [r"\bgenai\b", r"generative ai"]),
    ("LLMs", [r"\bllms?\b", r"large language models?"]),
    ("RAG", [r"\brag\b", r"retrieval augmented generation"]),
    ("Multi-agent systems", [r"multi-agent systems?", r"multi agent systems?"]),
    ("Text2SQL", [r"\btext2sql\b", r"text-to-sql"]),
    ("Fine-tuning", [r"\bfine-tun(?:e|ing)\b", r"\bfinetun(?:e|ing)\b"]),
    ("LangChain", [r"\blangchain\b"]),
    ("DSPy", [r"\bdspy\b"]),
    ("Hugging Face", [r"hugging ?face"]),
    ("AI/ML models", [r"\bai/ml models?\b", r"\bai models?\b", r"\bml models?\b"]),
    ("Model evaluation", [r"\bmodel evaluation\b", r"\bevaluating models?\b"]),
    ("PyTorch", [r"\bpytorch\b"]),
    ("TensorFlow", [r"\btensorflow\b"]),
    ("scikit-learn", [r"scikit-learn", r"\bsklearn\b"]),
    ("NumPy", [r"\bnumpy\b"]),
    ("pandas", [r"\bpandas\b"]),
    ("Apache Spark", [r"apache spark", r"\bspark\b"]),
    ("Databricks", [r"\bdatabricks\b"]),
    ("Data engineering", [r"\bdata engineering\b"]),
    ("Analytics engineering", [r"\banalytics engineering\b"]),
    ("Linux", [r"\blinux(?:-based)?\b"]),
    ("Robotics", [r"\brobotics\b", r"\brobotic\b"]),
    ("Autonomous vehicles", [r"autonomous vehicles?"]),
    ("Drones", [r"\bdrones?\b"]),
    ("Teleoperation", [r"\bteleoperation\b"]),
    ("Remote supervision", [r"remote supervision"]),
    ("Middleware integration", [r"middleware integration"]),
    ("Cloud-to-edge architecture", [r"cloud-to-edge architectures?"]),
    ("E-commerce", [r"\be-?commerce\b"]),
    ("Stakeholder management", [r"manage stakeholders?", r"stakeholder management"]),
    ("Communication", [r"communication skills?", r"written and verbal communication"]),
    ("Collaboration", [r"collaboration skills?", r"cross-functional"]),
    ("Mentoring", [r"\bmentor(?:ing)?\b"]),
    ("Hiring", [r"\btechnical hiring\b", r"\binterviewing candidates\b", r"\bhiring plans?\b"]),
]

SKILL_KEYWORDS = [name for name, _patterns in SKILL_PATTERNS]

MUST_HAVE_SECTION_STARTS = (
    "must have",
    "must-have",
    "requirements",
    "your toolkit",
    "who we are looking for",
    "what we look for",
    "what you must have",
    "what you'll need",
    "what you will need",
    "what should you bring along",
    "what you bring along",
    "qualifications",
    "your profile",
    "anforderungen",
    "profil",
    "was du mitbringst",
)

NICE_TO_HAVE_SECTION_STARTS = (
    "nice to have",
    "nice-to-have",
    "preferred",
    "bonus",
    "bonus points",
    "get some bonus points",
    "extras that give you an edge",
    "plus",
    "wunschenswert",
    "wünschenswert",
)

REQUIREMENT_SECTION_STOPS = (
    "nice to have",
    "nice-to-have",
    "preferred",
    "bonus",
    "extras that give you an edge",
    "benefits",
    "what we offer",
    "what do we offer",
    "how we'll make",
    "how we’ll make",
    "how to apply",
    "start date",
    "type of employment",
    "working hours",
    "about ",
    "show more",
    "seniority level",
    "employment type",
    "job function",
    "industries",
)

SENIORITY_KEYWORDS = {
    "senior": "Senior",
    "lead": "Lead",
    "principal": "Principal",
    "staff": "Staff",
    "junior": "Junior",
    "graduate": "Graduate",
    "intern": "Intern",
    "head of": "Head",
    "manager": "Manager",
    "director": "Director",
    "vp": "VP",
    "chief": "Chief",
}

WORK_MODEL_KEYWORDS = {
    "remote": "remote",
    "fully remote": "remote",
    "100% remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "in office": "onsite",
}

DACH_CITIES = [
    "berlin",
    "munich",
    "hamburg",
    "cologne",
    "frankfurt",
    "stuttgart",
    "düsseldorf",
    "leipzig",
    "dresden",
    "bonn",
    "zurich",
    "geneva",
    "bern",
    "basel",
    "lausanne",
    "vienna",
    "salzburg",
    "graz",
    "linz",
]

DACH_COUNTRIES = ["germany", "switzerland", "austria", "deutschland"]

GERMAN_KEYWORDS = [
    "german",
    "deutsch",
    "deutschkenntnisse",
    "fließend deutsch",
    "verhandlungssicher",
    "muttersprache",
]

SWISS_LOCATION_KEYWORDS = [
    "switzerland",
    "swiss",
    "schweiz",
    "suisse",
    "svizzera",
    "zurich",
    "zürich",
    "zuerich",
    "geneva",
    "basel",
    "bern",
    "lausanne",
]

STRICT_WORK_AUTH_PATTERNS = [
    r"\b(?:only|must|require[sd]?|eligible|eligibility|applicants?|candidates?)\b.{0,140}\b(?:swiss|switzerland|schweiz|eu|e/u|efta|european union|swedish|sweden)\b.{0,140}\b(?:citizenship|citizens?|passport|work permit|right to work|work authori[sz]ation|eligible)\b",
    r"\b(?:swiss|switzerland|schweiz|eu|e/u|efta|european union|swedish|sweden)\b.{0,80}\b(?:citizenship|citizens?|passport holders?|work permit|right to work)\b.{0,80}\b(?:only|required|must|can't|cannot|unable|unfortunately)\b",
    r"\b(?:valid|existing)\b.{0,60}\b(?:swiss|switzerland|schweiz|eu|efta)\b.{0,60}\b(?:work permit|work authori[sz]ation|right to work)\b",
    r"\b(?:can't|cannot|unable to|unfortunately)\b.{0,120}\b(?:support|sponsor)\b.{0,120}\bnon[-\s]?eu\b",
]

VISA_SPONSORSHIP_WARNING_PATTERNS = [
    r"\b(?:no|not|unable to|cannot)\b.{0,80}\b(?:visa sponsorship|sponsor visas?|work permit sponsorship)\b",
    r"\b(?:must|need to)\b.{0,80}\b(?:already|currently)\b.{0,80}\b(?:authorized|eligible|right to work)\b",
]

# Common city/office names that frequently appear in "About Us" / "Global Offices"
# sections and should never be treated as skills.
SKILL_CITY_BLACKLIST: set[str] = {
    "amsterdam",
    "athens",
    "atlanta",
    "austin",
    "bangalore",
    "bangkok",
    "barcelona",
    "beijing",
    "berlin",
    "boston",
    "brussels",
    "budapest",
    "buenos aires",
    "chicago",
    "copenhagen",
    "dallas",
    "denver",
    "dubai",
    "dublin",
    "edinburgh",
    "frankfurt",
    "geneva",
    "hamburg",
    "helsinki",
    "hong kong",
    "istanbul",
    "jakarta",
    "lisbon",
    "london",
    "los angeles",
    "madrid",
    "manchester",
    "melbourne",
    "mexico city",
    "miami",
    "milan",
    "montreal",
    "moscow",
    "mumbai",
    "munich",
    "new orleans",
    "new york",
    "oslo",
    "paris",
    "prague",
    "riga",
    "rio de janeiro",
    "rome",
    "san francisco",
    "santiago",
    "sao paulo",
    "seattle",
    "seoul",
    "shanghai",
    "singapore",
    "stockholm",
    "sydney",
    "tallinn",
    "tel aviv",
    "tokyo",
    "toronto",
    "vancouver",
    "vienna",
    "vilnius",
    "warsaw",
    "zurich",
    "basel",
    "bern",
    "lausanne",
}


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        key = re.sub(r"\s+", " ", cleaned).strip(" .;:").casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _extract_pattern_skills(text: str | None) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for name, patterns in SKILL_PATTERNS:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            found.append(name)
    return found


SKILL_SPLIT_RE = re.compile(r"\s*(?:,|;|\bor\b|\band\b)\s*", flags=re.IGNORECASE)
SKILL_LIST_TRIGGER_RE = re.compile(
    r"(?:such as|including|include|includes|like|for example|e\.g\.|frameworks? like|tools? such as)\s+([^.\n]+)",
    flags=re.IGNORECASE,
)

SKILL_NAME_ALIASES = {
    "huggingface": "Hugging Face",
    "node": "Node.js",
    "nodejs": "Node.js",
    "vue": "Vue.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "k8s": "Kubernetes",
    "ci/cd": "CI/CD pipelines",
    "mec": "Mobile Edge Computing",
    "ros2": "ROS2/DDS",
    "dds": "ROS2/DDS",
    "grpc": "gRPC",
    "webrtc": "WebRTC",
    "mqtt": "MQTT",
    "tcp/ip": "TCP/IP",
    "wifi": "Wi-Fi",
    "wi-fi": "Wi-Fi",
    "node.js": "Node.js",
    "langchain": "LangChain",
    "dspy": "DSPy",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "numpy": "NumPy",
    "pandas": "pandas",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "rag": "RAG",
    "llm": "LLMs",
    "llms": "LLMs",
    "text2sql": "Text2SQL",
    "genai": "GenAI",
}

NON_SKILL_CANDIDATES = {
    "etc",
    "similar",
    "similar systems",
    "and more",
    "more",
    "all levels",
    "the form below",
    "benchmark",
    "engineering",
    "index ventures",
    "ivp",
    "it architects",
    "christmas bonus",
    "vacation pay",
    "profit sharing",
    "6 weeks annual leave",
}


def _normalize_skill_candidate(value: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", value).strip(" \t\n\r.,;:()[]{}")
    cleaned = re.sub(
        r"^(?:tools?|frameworks?|platforms?|languages?)\s+(?:such as|like)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip(" \t\n\r.,;:()[]{}")
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    if re.search(r"https?://|www\.", lowered):
        return None
    if lowered in NON_SKILL_CANDIDATES:
        return None
    words = re.findall(r"[A-Za-z0-9+#./-]+", cleaned)
    if len(words) > 4:
        return None
    if re.search(
        r"\b(?:please|visit|role|candidate|candidates|team|company|office|"
        r"opportunity|parents-to-be|to work|we work|we|you|your|our|this)\b",
        lowered,
    ):
        return None
    if len(cleaned) > 60 or len(cleaned) < 2:
        return None
    if re.search(
        r"\b(?:experience|familiarity|knowledge|ability|skills?|systems?)\s*$",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return None
    if lowered in SKILL_NAME_ALIASES:
        return SKILL_NAME_ALIASES[lowered]
    if cleaned[0].islower():
        return None
    if re.fullmatch(r"[A-Z][A-Za-z0-9+#./-]{1,20}", cleaned):
        return cleaned
    if re.fullmatch(r"[A-Z]{2,}(?:/[A-Z0-9]+)?", cleaned):
        return cleaned
    if re.search(r"[A-Z][a-z]+(?:\.[A-Za-z]+)?|[A-Z]{2,}|[0-9]|[+#/.-]", cleaned):
        return cleaned
    return None


def _split_skill_segment(segment: str) -> list[str]:
    segment = re.sub(r"\betc\.?.*$", "", segment, flags=re.IGNORECASE)
    segment = re.sub(r"\bsimilar\b.*$", "", segment, flags=re.IGNORECASE)
    parts = SKILL_SPLIT_RE.split(segment)
    candidates: list[str] = []
    for part in parts:
        candidate = _normalize_skill_candidate(part)
        if candidate:
            candidates.append(candidate)
    return candidates


def _extract_listed_skills(text: str | None) -> list[str]:
    if not text:
        return []
    candidates: list[str] = []
    for line in text.splitlines():
        for match in SKILL_LIST_TRIGGER_RE.finditer(line):
            candidates.extend(_split_skill_segment(match.group(1)))
    return _dedupe_preserve_order(candidates)


def _extract_skills_from_text(text: str | None) -> list[str]:
    return _dedupe_preserve_order(_extract_pattern_skills(text) + _extract_listed_skills(text))


def _extract_section(
    raw_jd: str, start_keywords: tuple[str, ...], stop_keywords: tuple[str, ...]
) -> str:
    lines = raw_jd.splitlines()
    section: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped:
            continue
        if in_section and any(stop in lower for stop in stop_keywords):
            break
        if any(start in lower for start in start_keywords):
            in_section = True
            continue
        if in_section:
            section.append(stripped)
    return "\n".join(section)


def _extract_language_requirements(raw_jd: str) -> list[str]:
    requirements: list[str] = []
    language_patterns = {
        "English": [
            r"english.{0,80}(?:required|proficiency|fluent|communication|written|verbal|skills)",
            r"(?:required|proficiency|fluent|communication|written|verbal|skills).{0,80}english",
        ],
        "German": [
            r"german.{0,80}(?:required|proficiency|fluent|communication|written|verbal|skills)",
            r"deutsch.{0,80}(?:erforderlich|kenntnisse|fließend|kommunikation)",
            r"(?:required|proficiency|fluent|communication|written|verbal|skills).{0,80}german",
        ],
    }
    for language, patterns in language_patterns.items():
        if any(re.search(pattern, raw_jd, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns):
            requirements.append(language)
    return requirements


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text or "")
    parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [re.sub(r"\s+", " ", part).strip() for part in parts if len(part.strip()) > 12]


def _is_swiss_job(job) -> bool:
    text = f"{job.location or ''}\n{job.raw_jd or ''}".lower()
    return any(keyword in text for keyword in SWISS_LOCATION_KEYWORDS)


def _extract_work_authorization(job) -> dict | None:
    if not _is_swiss_job(job):
        return None

    text = f"{job.title or ''}\n{job.company or ''}\n{job.location or ''}\n{job.raw_jd or ''}"
    sentences = _sentences(text)
    for sentence in sentences:
        if any(
            re.search(pattern, sentence, flags=re.IGNORECASE | re.DOTALL)
            for pattern in STRICT_WORK_AUTH_PATTERNS
        ):
            return {
                "status": "restricted",
                "label": "Swiss/EU/EFTA eligibility restriction",
                "detail": "The posting appears to restrict applicants by citizenship, permit, or existing Swiss/EU/EFTA work authorization.",
                "evidence": sentence,
            }

    for sentence in sentences:
        if any(
            re.search(pattern, sentence, flags=re.IGNORECASE | re.DOTALL)
            for pattern in VISA_SPONSORSHIP_WARNING_PATTERNS
        ):
            return {
                "status": "warning",
                "label": "Visa sponsorship warning",
                "detail": "The posting may require existing local work authorization.",
                "evidence": sentence,
            }

    return None


def _enrich_parsed_skills(parsed_json: dict, job) -> dict:
    raw_jd = job.raw_jd or ""
    title = job.title or ""
    full_text = f"{title}\n{raw_jd}"
    nice_text = _extract_section(
        raw_jd,
        NICE_TO_HAVE_SECTION_STARTS,
        ("benefits", "what we offer", "how to apply", "about ", "show more", "seniority level"),
    )
    must_text = _extract_section(
        raw_jd,
        MUST_HAVE_SECTION_STARTS,
        REQUIREMENT_SECTION_STOPS + ("what this role is not",),
    )
    not_text = _extract_section(
        raw_jd,
        ("what this role is not", "this role is not"),
        ("requirements", "benefits", "must have", "nice to have"),
    )

    nice_section_skills = _extract_skills_from_text(nice_text)
    must_section_skills = _extract_skills_from_text(must_text)
    not_only_skills = (
        set(_extract_skills_from_text(not_text))
        - set(must_section_skills)
        - set(nice_section_skills)
    )
    not_only_keys = {skill.casefold() for skill in not_only_skills}

    current_must = (
        parsed_json.get("must_have_skills")
        if isinstance(parsed_json.get("must_have_skills"), list)
        else []
    )
    current_must = [skill for skill in current_must if str(skill).casefold() not in not_only_keys]
    current_nice = (
        parsed_json.get("nice_to_have_skills")
        if isinstance(parsed_json.get("nice_to_have_skills"), list)
        else []
    )
    current_nice = [skill for skill in current_nice if str(skill).casefold() not in not_only_keys]
    inferred_skills = [
        skill for skill in _extract_skills_from_text(full_text) if skill not in not_only_skills
    ]

    must_seed = _dedupe_preserve_order(list(current_must) + must_section_skills)
    must_seed_keys = {skill.casefold() for skill in must_seed}
    nice_seed = _dedupe_preserve_order(
        [
            skill
            for skill in list(current_nice) + nice_section_skills
            if str(skill).casefold() not in must_seed_keys
        ]
    )
    nice_seed_keys = {skill.casefold() for skill in nice_seed}
    enriched_must = _dedupe_preserve_order(
        must_seed + [skill for skill in inferred_skills if skill.casefold() not in nice_seed_keys]
    )
    enriched_must_keys = {skill.casefold() for skill in enriched_must}
    enriched_nice = _dedupe_preserve_order(
        [skill for skill in nice_seed if skill.casefold() not in enriched_must_keys]
    )

    # Sanity: remove city/office names that leak through LLM or regex extraction
    enriched_must = [s for s in enriched_must if s.casefold() not in SKILL_CITY_BLACKLIST]
    enriched_nice = [s for s in enriched_nice if s.casefold() not in SKILL_CITY_BLACKLIST]

    parsed_json["must_have_skills"] = enriched_must
    parsed_json["nice_to_have_skills"] = enriched_nice
    parsed_json["skills"] = _dedupe_preserve_order(enriched_must + enriched_nice)
    work_authorization = _extract_work_authorization(job)
    if work_authorization:
        parsed_json["work_authorization"] = work_authorization
        dach_signals = parsed_json.get("dach_signals")
        if not isinstance(dach_signals, dict):
            dach_signals = {}
        dach_signals["work_authorization"] = work_authorization["label"]
        parsed_json["dach_signals"] = dach_signals
    return parsed_json


def _deterministic_parse(job):
    jd_lower = job.raw_jd.lower() if job.raw_jd else ""
    title_lower = job.title.lower() if job.title else ""

    must_have = _extract_skills_from_text(f"{job.title or ''}\n{job.raw_jd or ''}")
    nice_to_have = _extract_skills_from_text(
        _extract_section(
            job.raw_jd or "",
            NICE_TO_HAVE_SECTION_STARTS,
            ("benefits", "what we offer", "how to apply", "about ", "show more", "seniority level"),
        )
    )
    nice_keys = {skill.casefold() for skill in nice_to_have}
    must_have = [skill for skill in must_have if skill.casefold() not in nice_keys]

    work_model = "onsite"
    for keyword, model in WORK_MODEL_KEYWORDS.items():
        if keyword in jd_lower:
            work_model = model
            break

    seniority = None
    for keyword, level in SENIORITY_KEYWORDS.items():
        if keyword in title_lower or keyword in jd_lower:
            seniority = level
            break

    exp_match = re.search(r"(\d+)\+?\s*(?:years|yrs|years of experience)", jd_lower)
    experience_years = int(exp_match.group(1)) if exp_match else None

    salary_range = None
    salary_match = re.search(
        r"(?:€|eur|chf|usd)\s*([\d,.]+)\s*(?:k|000)?\s*(?:-|to|–)\s*(?:€|eur|chf|usd)?\s*([\d,.]+)\s*(?:k|000)?",
        jd_lower,
    )
    if salary_match:
        salary_range = f"{salary_match.group(1)}-{salary_match.group(2)}"

    location = job.location or ""
    dach_signals = {}
    for city in DACH_CITIES:
        if city in jd_lower or city in location.lower():
            dach_signals["location"] = city
            break
    location_lower = location.lower()
    for country in DACH_COUNTRIES:
        if country in location_lower:
            dach_signals["country"] = country
            break
    if "country" not in dach_signals:
        for country in DACH_COUNTRIES:
            if country in jd_lower:
                dach_signals["country"] = country
                break
    for kw in GERMAN_KEYWORDS:
        if kw in jd_lower:
            dach_signals["language"] = "german"
            break

    lang_reqs = _extract_language_requirements(job.raw_jd or "")

    return {
        "title": job.title,
        "company": job.company,
        "location": location,
        "work_model": work_model,
        "seniority": seniority,
        "experience_years": experience_years,
        "salary_range": salary_range,
        "must_have_skills": must_have,
        "nice_to_have_skills": nice_to_have,
        "skills": must_have + nice_to_have,
        "language_requirements": lang_reqs,
        "dach_signals": dach_signals,
        "raw_preview": job.raw_jd[:500] if job.raw_jd else "",
    }


async def format_raw_jd(
    tenant: TenantContext,
    raw_text: str,
    title: str,
    company: str,
) -> str | None:
    if not raw_text or len(raw_text.strip()) < 100:
        return None

    from app.modules.llm_gateway.gateway import LLMGateway

    logger = logging.getLogger(__name__)
    gateway = LLMGateway()
    try:
        content = await gateway.run_text(
            tenant_id=tenant.id,
            task="jd_format",
            prompt_version="1.0",
            model_tier="fast",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a job description formatter. Reformat the raw job posting text "
                        "into clean, well-structured Markdown. CRITICAL RULES:\n"
                        "- PRESERVE ALL original content. Do NOT summarize, paraphrase, shorten, or omit any information.\n"
                        "- Do NOT add any facts, opinions, skills, requirements, or commentary that are not explicitly in the original text.\n"
                        "- Only improve the FORMATTING: add appropriate ## and ### headings (e.g. ## About the Role, ## Responsibilities, "
                        "## Requirements, ## Benefits, ## About the Company), convert lists to bullet points (- ), and add paragraph breaks.\n"
                        "- Remove obvious boilerplate, cookie consent notices, login prompts, navigation text, and page chrome that are not part of the job description.\n"
                        "- Keep the original language and wording. Do not translate, rewrite sentences, or change tone.\n"
                        "- Output ONLY the formatted Markdown. No preamble, no postamble, no explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Job Title: {title}\n"
                        f"Company: {company}\n\n"
                        f"RAW TEXT TO FORMAT:\n{raw_text[:15000]}"
                    ),
                },
            ],
        )
        if content and len(content.strip()) > 80:
            return content.strip()
    except Exception:
        logger.exception("LLM JD formatting failed, keeping original raw_jd")

    return None


def _jd_extract_messages(job) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "You are a job parser. Extract structured information from the job posting below. Return valid JSON only.",
        },
        {
            "role": "user",
            "content": (
                f"Title: {job.title}\n"
                f"Company: {job.company}\n"
                f"Location: {job.location or 'N/A'}\n"
                f"Description:\n{job.raw_jd}\n\n"
                "Extract JSON with these fields:\n"
                "title, company, location, work_model (remote/hybrid/onsite), "
                "language_requirements (list), must_have_skills (list), "
                "nice_to_have_skills (list), "
                "salary_range (string or null), seniority (string or null), "
                "work_authorization (object or null with status, label, detail, evidence), "
                "dach_signals (object with location/country/language/work_authorization keys)\n\n"
                "Skill extraction rules:\n"
                "- Extract as many explicit atomic skills/capabilities as the posting contains, not only broad summary sentences.\n"
                "- Include programming languages, frameworks, databases, protocols, cloud services, infrastructure practices, security controls, testing/release practices, domain capabilities, collaboration requirements, and operational responsibilities.\n"
                "- Split combined requirements into separate items. Example: 'GCP infrastructure (Cloud Run, networking, IAM, TLS, firewall rules)' becomes "
                "['GCP', 'Cloud Run', 'Networking', 'IAM', 'TLS', 'Firewall rules'].\n"
                "- Treat capabilities like RBAC, job queues, CI/CD pipelines, GitHub Actions, E2E tests, QA, rollbacks, on-call, incident response, observability, monitoring, vulnerability scanning, penetration testing, and infrastructure hardening as skills when present.\n"
                "- Put skills from sections like 'Requirements', 'Your toolkit', 'What you must have', or equivalent in must_have_skills.\n"
                "- Put skills from sections like 'Nice to have', 'Preferred', 'Bonus', 'Extras that give you an edge', or equivalent in nice_to_have_skills.\n"
                "- Do not include skills that are mentioned only in a negated section such as 'What this role is NOT'.\n"
                "- Do NOT extract city names, office locations, or company headquarters as skills (e.g. Stockholm, London, New York). These are locations, not skills.\n"
                "- Put explicit 'must have' requirements in must_have_skills and optional/preferred items in nice_to_have_skills.\n"
                "- For Swiss jobs, flag explicit citizenship, work permit, EU/EFTA, right-to-work, or visa sponsorship restrictions in work_authorization with the exact evidence sentence."
            ),
        },
    ]


def _needs_reasoning_parse_retry(parsed_json: dict, job) -> bool:
    raw_jd = job.raw_jd or ""
    skill_count = len(parsed_json.get("must_have_skills") or []) + len(
        parsed_json.get("nice_to_have_skills") or []
    )
    has_requirement_signal = any(
        signal in raw_jd.lower()
        for signal in (
            "requirements",
            "your toolkit",
            "what you must have",
            "must have",
            "qualifications",
            "your mission",
        )
    )
    return len(raw_jd) > 1200 and has_requirement_signal and skill_count < 4


async def parse_job_posting(
    db: AsyncSession,
    tenant: TenantContext,
    job,
    force: bool = False,
) -> dict:
    if job.parsed_json and not force:
        await sync_job_skills(db, job, job.parsed_json, source="cached_parser")
        logging.getLogger(__name__).info(
            "parse_cache_hit | job_id=%s tenant_id=%s",
            job.id,
            tenant.id,
        )
        try:
            from app.db.models import LLMRun

            run = LLMRun(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                task="jd_extract",
                provider="cache",
                model="cache",
                prompt_version="1.1",
                latency_ms=0,
                status="cache_hit",
            )
            db.add(run)
            await db.flush()
        except Exception:
            pass
        return {"status": job.status or "parsed", "parsed_json": job.parsed_json}

    from app.modules.llm_gateway.gateway import LLMGateway

    logger = logging.getLogger(__name__)
    gateway = LLMGateway()
    messages = _jd_extract_messages(job)
    try:
        content = await gateway.run_text(
            tenant_id=tenant.id,
            task="jd_extract",
            prompt_version="1.1",
            model_tier="quality",
            messages=messages,
            response_format={"type": "json_object"},
        )
        if content:
            parsed_json = json.loads(content)
            parsed_json = _enrich_parsed_skills(parsed_json, job)
            if _needs_reasoning_parse_retry(parsed_json, job):
                try:
                    retry_content = await gateway.run_text(
                        tenant_id=tenant.id,
                        task="jd_extract",
                        prompt_version="1.1-reasoning-retry",
                        messages=messages,
                        reasoning=True,
                        response_format={"type": "json_object"},
                    )
                    if retry_content:
                        retry_json = _enrich_parsed_skills(json.loads(retry_content), job)
                        if len(retry_json.get("skills") or []) > len(
                            parsed_json.get("skills") or []
                        ):
                            parsed_json = retry_json
                except Exception:
                    logger.exception("Reasoning model JD parse retry failed, keeping fast parse")
            job.parsed_json = parsed_json
            job.status = "parsed"
            await sync_job_skills(db, job, parsed_json, source=gateway.last_provider)
            await db.flush()
            return {"status": "parsed", "parsed_json": parsed_json}
    except Exception:
        logger.exception("LLM job parsing failed, falling back to deterministic parser")

    parsed_json = _enrich_parsed_skills(_deterministic_parse(job), job)
    job.parsed_json = parsed_json
    job.status = "parsed"
    await sync_job_skills(db, job, parsed_json, source="deterministic_parser")
    await db.flush()
    return {"status": "parsed", "parsed_json": parsed_json}


def _skill_overlap(jd_skills: list[str], profile_text: str) -> float:
    if not jd_skills:
        return 0.5
    profile_lower = profile_text.lower()
    matched = sum(1 for s in jd_skills if s.lower() in profile_lower)
    return matched / len(jd_skills)


def _dach_score(
    job_location: str | None,
    profile_location: str | None,
    jd_text: str,
    profile_text: str,
) -> float:
    score = 0.0
    jd_lower = jd_text.lower()
    profile_lower = profile_text.lower()

    loc_text = (job_location or "").lower()
    profile_loc_text = (profile_location or "").lower()

    job_in_dach = any(c in loc_text or c in jd_lower for c in DACH_CITIES)
    job_in_dach = job_in_dach or any(c in jd_lower for c in DACH_COUNTRIES)
    profile_in_dach = any(
        c in profile_loc_text or c in profile_lower for c in DACH_CITIES + DACH_COUNTRIES
    )

    if job_in_dach and profile_in_dach:
        score += 0.6
    elif job_in_dach:
        score += 0.2
    elif profile_in_dach:
        score += 0.3

    has_german = any(kw in jd_lower for kw in GERMAN_KEYWORDS)
    profile_has_german = any(kw in profile_lower for kw in GERMAN_KEYWORDS)
    if has_german and profile_has_german:
        score += 0.4
    elif has_german:
        score += 0.0
    elif profile_has_german:
        score += 0.2
    else:
        score += 0.3

    return min(score, 1.0)


def _evidence_coverage(evidence_chunks: list, must_have_skills: list[str] | None) -> float:
    if not must_have_skills:
        return 0.5
    if not evidence_chunks:
        return 0.0
    combined = " ".join(c.content.lower() for c in evidence_chunks if c.content)
    matched = sum(1 for s in must_have_skills if s.lower() in combined)
    return matched / len(must_have_skills)


def _extract_text_for_scoring(job) -> str:
    parts = [job.title or "", job.raw_jd or ""]
    if job.parsed_json:
        for key in ("must_have_skills", "nice_to_have_skills"):
            items = job.parsed_json.get(key, [])
            if isinstance(items, list):
                parts.extend(str(i) for i in items)
    return " ".join(parts)


def _calculate_score(job, profile, evidence_chunks):
    parsed = job.parsed_json or {}
    must_have = parsed.get("must_have_skills") or []

    jd_text = _extract_text_for_scoring(job)
    profile_text = f"{profile.headline or ''} {profile.raw_cv_md or ''} {json.dumps(profile.profile_json or {})}"

    role_relevance = _skill_overlap(
        [job.title or ""] + must_have,
        profile_text,
    )

    skill_match = _skill_overlap(must_have, profile_text)

    evidence_strength = _evidence_coverage(evidence_chunks, must_have)

    dach_feasibility = _dach_score(
        job.location,
        profile.location,
        jd_text,
        profile_text,
    )

    compensation_fit = 0.5
    if parsed.get("salary_range"):
        compensation_fit = 0.6

    growth_story_value = 0.5
    if evidence_chunks:
        labels = [c.source_label.lower() for c in evidence_chunks if c.source_label]
        progression_kw = ["senior", "lead", "promot", "advanc", "head of", "manager"]
        if any(any(kw in label for kw in progression_kw) for label in labels):
            growth_story_value = 0.7

    weights = {
        "role_relevance": 0.20,
        "skill_match": 0.25,
        "evidence_strength": 0.20,
        "dach_feasibility": 0.15,
        "compensation_fit": 0.10,
        "growth_story_value": 0.10,
    }

    breakdown = {
        "role_relevance": round(role_relevance * 5, 2),
        "skill_match": round(skill_match * 5, 2),
        "evidence_strength": round(evidence_strength * 5, 2),
        "dach_feasibility": round(dach_feasibility * 5, 2),
        "compensation_fit": round(compensation_fit * 5, 2),
        "growth_story_value": round(growth_story_value * 5, 2),
    }

    overall = (
        role_relevance * weights["role_relevance"]
        + skill_match * weights["skill_match"]
        + evidence_strength * weights["evidence_strength"]
        + dach_feasibility * weights["dach_feasibility"]
        + compensation_fit * weights["compensation_fit"]
        + growth_story_value * weights["growth_story_value"]
    )

    overall_score = overall * 5.0
    overall_score = round(max(1.0, min(5.0, overall_score)), 2)

    if overall_score >= 4.2:
        recommendation = "apply"
    elif overall_score >= 3.6:
        recommendation = "maybe"
    else:
        recommendation = "skip"

    gaps = []
    if must_have:
        profile_lower = profile_text.lower()
        missing = [s for s in must_have if s.lower() not in profile_lower]
        if missing:
            gaps.append(f"Missing skills: {', '.join(missing[:5])}")

    parsed_german = any(kw in jd_text.lower() for kw in GERMAN_KEYWORDS)
    profile_german = any(kw in profile_text.lower() for kw in GERMAN_KEYWORDS)
    if parsed_german and not profile_german:
        gaps.append("German language requirement not met")

    return overall_score, recommendation, breakdown, {"gaps": gaps}


def _generate_explanation_template(
    overall_score: float,
    recommendation: str,
    breakdown: dict,
    gaps: dict | None,
) -> str:
    top = max(breakdown, key=breakdown.get)
    bottom = min(breakdown, key=breakdown.get)
    parts = [
        f"Overall match score: {overall_score}/5.0 — {recommendation}.",
        f"Strongest dimension: {top} ({breakdown[top]}/5).",
        f"Weakest dimension: {bottom} ({breakdown[bottom]}/5).",
    ]
    if gaps and gaps.get("gaps"):
        parts.append(f"Gaps identified: {'; '.join(gaps['gaps'])}.")
    return " ".join(parts)


async def compute_match(
    db: AsyncSession,
    tenant: TenantContext,
    job_id: uuid.UUID,
) -> MatchReport:
    job = await get_job(db, job_id, tenant.id)
    if not job:
        from app.core.errors import AppError

        raise AppError("job_not_found", "Job posting not found", status_code=404)

    if not job.parsed_json:
        await parse_job_posting(db, tenant, job)

    profile = await get_profile_by_user(db, tenant.user_id)
    if not profile:
        raise AppError("profile_not_found", "Candidate profile not found")

    result = await db.execute(
        select(EvidenceChunk)
        .where(EvidenceChunk.profile_id == profile.id)
        .where(EvidenceChunk.tenant_id == tenant.id)
    )
    evidence_chunks = list(result.scalars().all())

    overall_score, recommendation, breakdown, gaps = _calculate_score(job, profile, evidence_chunks)

    from app.modules.llm_gateway.gateway import LLMGateway

    logger = logging.getLogger(__name__)
    explanation = None
    gateway = LLMGateway()
    try:
        content = await gateway.run_text(
            tenant_id=tenant.id,
            task="fit_explanation",
            prompt_version="1.0",
            model_tier="fast",
            messages=[
                {
                    "role": "system",
                    "content": "You are a career coach. Given a match score and breakdown, write 2-3 sentences explaining the fit and key gaps. Be concise and factual.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Score: {overall_score}/5. Recommendation: {recommendation}.\n"
                        f"Breakdown: {json.dumps(breakdown)}\n"
                        f"Gaps: {json.dumps(gaps)}\n"
                        f"Job: {job.title} at {job.company}\n"
                        f"Profile: {profile.headline}"
                    ),
                },
            ],
        )
        if content:
            explanation = content.strip()
    except Exception:
        logger.exception("LLM match explanation failed, falling back to template")

    if not explanation:
        explanation = _generate_explanation_template(
            overall_score,
            recommendation,
            breakdown,
            gaps,
        )

    report = MatchReport(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        job_id=job.id,
        overall_score=Decimal(str(overall_score)),
        recommendation=recommendation,
        breakdown_json=breakdown,
        gaps_json=gaps if gaps.get("gaps") else None,
        explanation=explanation,
    )
    db.add(report)
    await db.flush()
    return report
