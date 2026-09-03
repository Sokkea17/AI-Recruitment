import pytest
from app.services.document_parser import document_parser

def test_parse_text_jd():
    sample_jd = """
Job Title: Senior Legal Executive
Department: Legal & Compliance
Location: Phnom Penh, Cambodia
Employment Type: Full-time
Salary: $1,500 - $2,500 per month

Job Summary
We are seeking an experienced Senior Legal Executive to oversee corporate compliance, contract drafting, and regulatory affairs.

Key Responsibilities
- Draft, review, and negotiate commercial contracts and agreements.
- Advise management on legal risks and statutory compliance.
- Liaise with regulatory authorities and external counsel.

Requirements
- Bachelor of Laws (LL.B) or higher.
- Minimum 4 years of corporate legal experience.
- Strong analytical and negotiation skills.
- Fluent in English and Khmer.

How to Apply
Submit your updated CV via our recruitment portal or bot.
"""
    parsed = document_parser.parse_jd_sections(sample_jd)
    
    assert parsed["title"] == "Senior Legal Executive"
    assert parsed["department"] == "Legal & Compliance"
    assert parsed["location"] == "Phnom Penh, Cambodia"
    assert parsed["employment_type"] == "Full-time"
    assert "$1,500 - $2,500" in parsed["salary_range"]
    assert "experienced Senior Legal Executive" in parsed["short_description"]
    assert "commercial contracts" in parsed["responsibilities"]
    assert "Bachelor of Laws" in parsed["requirements"]
    assert "Submit your updated CV" in parsed["instructions"]

def test_extract_cv_details():
    sample_cv = """
John Doe
Email: john.doe@example.com
Phone: +855 12 345 678
Phnom Penh, Cambodia

PROFESSIONAL SUMMARY
Experienced Software Engineer with over 5 years developing cloud services and APIs.

SKILLS
Python, FastAPI, Docker, PostgreSQL, React, Git, Linux

EXPERIENCE
Senior Backend Developer | Tech Solutions (2021 - Present)
- Developed scalable REST APIs using Python and FastAPI.
- Containerized microservices with Docker and managed PostgreSQL databases.

EDUCATION
Bachelor of Science in Computer Science | RUPP (2016 - 2020)
"""
    info = document_parser.extract_cv_details(sample_cv)
    
    assert info["full_name"] == "John Doe"
    assert info["email"] == "john.doe@example.com"
    assert "12 345 678" in info["phone"]
    assert "Python" in info["skills"]
    assert "FastAPI" in info["skills"]
    assert "PostgreSQL" in info["skills"]
