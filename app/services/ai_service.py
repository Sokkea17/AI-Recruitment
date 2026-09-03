import logging
import json
from typing import Dict, Any, Optional
from app.config import settings
from app.services.document_parser import document_parser

logger = logging.getLogger(__name__)

class AIService:
    @staticmethod
    def generate_candidate_summary_heuristic(cv_text: str, extracted_details: Dict[str, Any]) -> str:
        name = extracted_details.get("full_name") or "The candidate"
        skills = extracted_details.get("skills", [])
        skills_str = ", ".join(skills[:6]) if skills else "relevant industry skills"
        
        # Estimate experience
        exp_lines = []
        for line in cv_text.splitlines():
            l_lower = line.lower()
            if any(k in l_lower for k in ["year", "experience", "developer", "officer", "manager", "engineer", "specialist"]):
                exp_lines.append(line.strip())
        
        exp_summary = "several years of professional experience"
        for line in exp_lines[:3]:
            if "year" in line.lower():
                exp_summary = line
                break

        summary = (
            f"[AI Summary - Advisory Only]\n"
            f"{name} demonstrates background in {skills_str}. "
            f"Profile highlights: {exp_summary}."
        )
        return summary

    @staticmethod
    def match_cv_with_vacancy_heuristic(cv_text: str, vacancy_requirements: Optional[str], vacancy_skills: Optional[str]) -> Dict[str, Any]:
        cv_text_lower = cv_text.lower()
        req_text = (vacancy_requirements or "") + " " + (vacancy_skills or "")
        
        # Look for matching keywords
        common_words = [
            "python", "fastapi", "django", "javascript", "react", "vue", "sql", "postgresql",
            "docker", "kubernetes", "aws", "git", "linux", "compliance", "recruitment", "payroll",
            "communication", "negotiation", "bachelor", "master", "english", "khmer", "management"
        ]
        
        matching_skills = []
        missing_skills = []
        
        for kw in common_words:
            in_req = kw in req_text.lower()
            in_cv = kw in cv_text_lower
            if in_req and in_cv:
                matching_skills.append(kw.capitalize())
            elif in_req and not in_cv:
                missing_skills.append(kw.capitalize())

        match_score = 75 if matching_skills else 50
        
        assessment = (
            f"[AI Preliminary Assessment - Advisory Only]\n"
            f"• Matching competencies: {', '.join(matching_skills) if matching_skills else 'General background match'}\n"
            f"• Potential gaps/to clarify in interview: {', '.join(missing_skills[:5]) if missing_skills else 'None prominent'}\n"
            f"• Note: Preliminary AI indicator only. Final decision remains with HR."
        )

        return {
            "matching_skills": matching_skills,
            "missing_skills": missing_skills,
            "match_score": match_score,
            "assessment": assessment
        }

    @staticmethod
    async def analyze_application(cv_text: str, vacancy_title: str, vacancy_requirements: Optional[str] = None, vacancy_skills: Optional[str] = None) -> Dict[str, str]:
        extracted_info = document_parser.extract_cv_details(cv_text)
        
        # Check if OpenAI or Gemini is configured
        provider = settings.AI_PROVIDER.lower() if settings.AI_PROVIDER else "none"
        
        if provider == "openai" and settings.OPENAI_API_KEY:
            try:
                import httpx
                prompt = (
                    f"Analyze this CV for the position: {vacancy_title}.\n"
                    f"Job Requirements: {vacancy_requirements}\n\n"
                    f"CV Content:\n{cv_text[:3500]}\n\n"
                    f"Provide a JSON response with two keys:\n"
                    f"1. 'summary': A 2-sentence HR summary of the candidate's background and key skills.\n"
                    f"2. 'matching_analysis': Matching skills, relevant experience, potential missing requirements, and a preliminary assessment. Clearly state this is advisory and never auto-reject."
                )
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                        json={
                            "model": "gpt-3.5-turbo",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.3
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        # Try parsing JSON from response
                        try:
                            parsed = json.loads(content)
                            return {
                                "ai_summary": parsed.get("summary", ""),
                                "ai_matching_analysis": parsed.get("matching_analysis", "")
                            }
                        except Exception:
                            return {
                                "ai_summary": content[:400],
                                "ai_matching_analysis": content
                            }
            except Exception as e:
                logger.warning(f"OpenAI analysis failed, falling back to heuristic: {e}")

        # Default / Heuristic Fallback
        summary = AIService.generate_candidate_summary_heuristic(cv_text, extracted_info)
        matching = AIService.match_cv_with_vacancy_heuristic(cv_text, vacancy_requirements, vacancy_skills)

        return {
            "ai_summary": summary,
            "ai_matching_analysis": matching["assessment"]
        }

ai_service = AIService()
