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
    "data_analytics": {
        "Statistics": ["statistics", "statistical analysis"],
        "A/B Testing": ["a/b testing", "ab testing", "experimentation"],
        "Data Visualization": ["data visualization", "dataviz"],
        "Tableau": ["tableau"],
        "Power BI": ["power bi", "powerbi"],
        "Data Analysis": ["data analysis", "data analytics"],
        "Excel": ["excel", "spreadsheets"],
        "Big Data": ["spark", "hadoop", "big data"],
    },
    "mlops": {
        "MLOps": ["mlops", "ml ops"],
        "Model Deployment": ["model deployment", "model serving"],
        "MLflow": ["mlflow"],
        "Airflow": ["airflow"],
        "Feature Engineering": ["feature engineering"],
        "Model Monitoring": ["model monitoring", "model drift"],
        "ONNX": ["onnx"],
    },
    "qa": {
        "Manual Testing": ["manual testing"],
        "Test Automation": ["test automation", "automated testing"],
        "Selenium": ["selenium"],
        "Cypress": ["cypress"],
        "JUnit": ["junit"],
        "PyTest": ["pytest", "py.test"],
        "Postman": ["postman"],
        "Regression Testing": ["regression testing"],
        "Test Case Design": ["test case", "test cases", "test plan"],
        "Bug Tracking": ["bug tracking", "defect tracking"],
    },
    "product": {
        "Product Management": ["product management", "product manager"],
        "Roadmapping": ["roadmap", "roadmapping"],
        "User Research": ["user research", "usability testing"],
        "Wireframing": ["wireframing", "wireframe", "figma"],
        "Stakeholder Management": ["stakeholder management", "stakeholder"],
        "Go-to-Market": ["go-to-market", "gtm", "go to market"],
        "Product Analytics": ["product analytics", "amplitude", "mixpanel"],
        "JIRA": ["jira"],
    },
    "soft": {
        "Leadership": ["leadership", "led a team", "team lead"],
        "Communication": ["communication"],
        "Teamwork": ["teamwork", "collaboration"],
        "Problem Solving": ["problem solving", "problem-solving"],
        "Project Management": ["project management", "scrum", "agile"],
    },
}

# Category -> weight signalling how strongly a match points at each role.
# A rarer, more role-specific category (product, qa, mlops, data_analytics,
# hr_domain) outweighs a broad one (language, cs_fundamentals) that half of
# all resumes will contain regardless of which role they're aiming for —
# the same precedent the old HR-weighting rule set.
ROLE_SIGNALS: dict[str, dict[str, float]] = {
    "SDE": {
        "language": 1.5,
        "frontend": 1.5,
        "backend": 2.0,
        "database": 1.5,
        "devops": 1.0,
        "cs_fundamentals": 1.5,
    },
    "DS": {"ml": 2.0, "data_analytics": 3.0, "language": 0.5, "cs_fundamentals": 0.5},
    "MLE": {"ml": 2.0, "mlops": 3.0, "devops": 1.5, "language": 0.5, "backend": 0.5},
    "QA": {"qa": 3.0, "cs_fundamentals": 1.0, "language": 0.5},
    "PM": {"product": 3.0, "soft": 1.5, "data_analytics": 0.5},
    "HR": {"hr_domain": 3.0, "soft": 1.0},
}

# Seniority keywords, checked before the years-of-experience heuristic.
LEVEL_KEYWORDS: dict[str, list[str]] = {
    "intern": ["intern", "internship", "trainee"],
    "senior": ["senior", "sr.", "lead", "principal", "staff engineer", "architect", "manager"],
}
