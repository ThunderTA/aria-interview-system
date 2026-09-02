"""Keyword taxonomy used to pull skills out of resume text.

Deliberately rule-based rather than model-based: it needs no API key, runs
instantly, and is easy to explain and extend during a viva. Each entry maps a
canonical skill name to the aliases that may appear in a resume.

Aliases are matched case-insensitively on word boundaries, so "go" won't match
inside "django" and "r" won't match inside "react".
"""

# category -> canonical name -> aliases
SKILL_TAXONOMY: dict[str, dict[str, list[str]]] = {
    "language": {
        "Python": ["python", "py"],
        "Java": ["java"],
        "JavaScript": ["javascript", "js", "es6"],
        "TypeScript": ["typescript", "ts"],
        "C++": ["c++", "cpp"],
        "C": ["c"],
        "C#": ["c#", "csharp"],
        "Go": ["go", "golang"],
        "Rust": ["rust"],
        "Kotlin": ["kotlin"],
        "Swift": ["swift"],
        "PHP": ["php"],
        "Ruby": ["ruby"],
        "R": ["r"],
        "SQL": ["sql"],
    },
    "frontend": {
        "React": ["react", "react.js", "reactjs"],
        "Next.js": ["next.js", "nextjs"],
        "Angular": ["angular"],
        "Vue": ["vue", "vue.js", "vuejs"],
        "HTML": ["html", "html5"],
        "CSS": ["css", "css3"],
        "Tailwind CSS": ["tailwind", "tailwindcss"],
        "Redux": ["redux"],
    },
    "backend": {
        "Node.js": ["node", "node.js", "nodejs"],
        "Express": ["express", "express.js", "expressjs"],
        "FastAPI": ["fastapi"],
        "Django": ["django"],
        "Flask": ["flask"],
        "Spring Boot": ["spring", "spring boot", "springboot"],
        "REST API": ["rest", "rest api", "restful"],
        "GraphQL": ["graphql"],
        "WebSocket": ["websocket", "websockets"],
    },
    "database": {
        "MongoDB": ["mongodb", "mongo"],
        "PostgreSQL": ["postgresql", "postgres"],
        "MySQL": ["mysql"],
        "SQLite": ["sqlite"],
        "Redis": ["redis"],
        "Firebase": ["firebase"],
        "Elasticsearch": ["elasticsearch"],
    },
    "ml": {
        "Machine Learning": ["machine learning", "ml"],
        "Deep Learning": ["deep learning"],
        "PyTorch": ["pytorch"],
        "TensorFlow": ["tensorflow"],
        "Keras": ["keras"],
        "Scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
        "NLP": ["nlp", "natural language processing"],
        "Computer Vision": ["computer vision", "opencv", "cv2"],
        "Pandas": ["pandas"],
        "NumPy": ["numpy"],
        "LLM": ["llm", "large language model", "large language models"],
    },
    "devops": {
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "k8s"],
        "AWS": ["aws", "amazon web services"],
        "Azure": ["azure"],
        "GCP": ["gcp", "google cloud"],
        "CI/CD": ["ci/cd", "cicd", "continuous integration"],
        "Git": ["git"],
        "Linux": ["linux", "unix"],
    },
    "cs_fundamentals": {
        "Data Structures": ["data structures", "dsa"],
        "Algorithms": ["algorithms", "algorithm"],
        "Operating Systems": ["operating systems", "os"],
        "DBMS": ["dbms", "database management"],
        "Computer Networks": ["computer networks", "networking"],
        "System Design": ["system design"],
        "OOP": ["oop", "object oriented", "object-oriented"],
    },
    "hr_domain": {
        "Recruitment": ["recruitment", "recruiting", "talent acquisition"],
        "Onboarding": ["onboarding"],
        "Employee Engagement": ["employee engagement"],
        "Payroll": ["payroll"],
        "HRMS": ["hrms", "hris"],
        "Performance Management": ["performance management", "appraisal"],
        "Learning & Development": ["learning and development", "l&d", "training"],
    },
    "soft": {
        "Leadership": ["leadership", "led a team", "team lead"],
        "Communication": ["communication"],
        "Teamwork": ["teamwork", "collaboration"],
        "Problem Solving": ["problem solving", "problem-solving"],
        "Project Management": ["project management", "scrum", "agile"],
    },
}

# Categories that signal each interview role. Used to infer which role's
# questions a candidate should get by default.
SDE_CATEGORIES = {"language", "frontend", "backend", "database", "ml", "devops", "cs_fundamentals"}
HR_CATEGORIES = {"hr_domain"}

# Seniority keywords, checked before the years-of-experience heuristic.
LEVEL_KEYWORDS: dict[str, list[str]] = {
    "intern": ["intern", "internship", "trainee"],
    "senior": ["senior", "sr.", "lead", "principal", "staff engineer", "architect", "manager"],
}
