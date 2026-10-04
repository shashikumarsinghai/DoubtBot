# ================================
# Smart Study Planner
# ================================

def create_study_plan(subject, days, hours_per_day):

    days = int(days)
    hours_per_day = float(hours_per_day)

    total_hours = days * hours_per_day

    subject_lower = subject.lower().strip()

    topic_templates = {
        "python": [
            "Python Basics",
            "Variables & Data Types",
            "Conditions & if-else",
            "Loops",
            "Functions",
            "Lists, Tuples & Dictionaries",
            "Practice + Revision"
        ],

        "javascript": [
            "JavaScript Basics",
            "Variables & Data Types",
            "Conditions",
            "Loops",
            "Functions",
            "Arrays & Objects",
            "Practice + Revision"
        ],

        "java": [
            "Java Basics",
            "Variables & Data Types",
            "Conditions",
            "Loops",
            "Methods",
            "Arrays & OOP Basics",
            "Practice + Revision"
        ],

        "c": [
            "C Basics",
            "Variables & Data Types",
            "Conditions",
            "Loops",
            "Functions",
            "Arrays & Pointers Basics",
            "Practice + Revision"
        ],

        "c++": [
            "C++ Basics",
            "Variables & Data Types",
            "Conditions & Loops",
            "Functions",
            "Arrays & Strings",
            "OOP Basics",
            "Practice + Revision"
        ],

        "html": [
            "HTML Basics",
            "Headings, Paragraphs & Links",
            "Images & Lists",
            "Tables",
            "Forms",
            "Semantic HTML",
            "Practice + Revision"
        ],

        "css": [
            "CSS Basics",
            "Selectors & Properties",
            "Box Model",
            "Flexbox",
            "Grid",
            "Responsive Design",
            "Practice + Revision"
        ],

        "django": [
            "Django Basics",
            "Project & App Structure",
            "URLs & Views",
            "Templates",
            "Models & Database",
            "Forms & Authentication",
            "Practice + Revision"
        ],

        "sql": [
            "SQL Basics",
            "SELECT & WHERE",
            "ORDER BY & GROUP BY",
            "Aggregate Functions",
            "JOINs",
            "Subqueries",
            "Practice + Revision"
        ],

        "dsa": [
            "DSA Basics & Complexity",
            "Arrays",
            "Strings",
            "Linked Lists",
            "Stacks & Queues",
            "Trees & Searching",
            "Practice + Revision"
        ]
    }

    # Find matching subject
    topics = None

    for key, template in topic_templates.items():
        if key in subject_lower:
            topics = template
            break

    # Generic plan for unknown subjects
    if topics is None:
        topics = [
            "Introduction & Basics",
            "Core Concepts",
            "Important Concepts",
            "Examples & Applications",
            "Practice",
            "Revision",
            "Final Test"
        ]

    plan = []

    for day in range(1, days + 1):

        topic_index = (day - 1) % len(topics)
        topic = topics[topic_index]

        # Special handling for longer plans
        if day > len(topics):
            cycle = (day - 1) // len(topics)

            if cycle % 2 == 1:
                topic = f"{topic} — Extra Practice"
            else:
                topic = f"{topic} — Revision"

        plan.append({
            "day": day,
            "subject": subject,
            "topic": topic,
            "hours": hours_per_day
        })

    return {
        "subject": subject,
        "days": days,
        "hours_per_day": hours_per_day,
        "total_hours": total_hours,
        "plan": plan
    }