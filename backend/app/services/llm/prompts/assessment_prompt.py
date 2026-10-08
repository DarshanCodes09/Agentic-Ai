"""
Prompt builder for the AssessmentAgent.
"""

from typing import Any

SYSTEM_ASSESSMENT_PROMPT = """You are a rigorous, impartial, and expert University Academic Assessor and Evaluator.
Your objective is to evaluate a student's submission with high academic integrity against the provided assignment questions, rubric criteria, expected concepts, and retrieved course materials.

Evaluation Directives:
1. Grounding & Anti-Hallucination: Evaluate solely based on the text submitted by the student and the provided course context. Do NOT award marks for assumptions or hallucinated student arguments.
2. Rubric Alignment: Assess every rubric criterion thoroughly. The awarded score for each criterion MUST NOT exceed its max_marks and MUST NOT be negative.
3. Scoring Consistency: The total ai_score MUST exactly equal the sum of all criterion scores, and MUST NOT exceed the assignment's total max marks.
4. Concept Mastery: For each expected academic concept, assign an accurate mastery level (MASTERED, PROFICIENT, PARTIAL, NEEDS_IMPROVEMENT, NOT_DEMONSTRATED) and cite specific evidence from the submission.
5. Critical Analysis: Distinguish clearly between superficial keyword mentions and genuine deep comprehension.
6. JSON Strictness: Return valid JSON matching the requested schema.
"""


def build_assessment_prompts(
    assignment_title: str,
    assignment_description: str | None,
    total_max_marks: float,
    questions: list[dict[str, Any]],
    rubric_items: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
    submission_text: str,
) -> tuple[str, str]:
    """
    Constructs (system_prompt, user_prompt) for the AssessmentAgent.
    """
    user_parts: list[str] = [
        f"### Assignment Title: {assignment_title}",
    ]
    if assignment_description:
        user_parts.append(f"Assignment Description: {assignment_description}")
    user_parts.append(f"Total Assignment Max Marks: {total_max_marks}")

    user_parts.append("\n### Assignment Questions & Expected Concepts:")
    for q in questions:
        q_num = q.get("question_number", 1)
        q_text = q.get("question_text", "")
        q_marks = q.get("marks", 0.0)
        concepts = q.get("expected_concepts") or []
        concepts_str = ", ".join(concepts) if isinstance(concepts, list) else str(concepts)
        user_parts.append(
            f"Question {q_num} ({q_marks} Marks):\n"
            f"  Prompt: {q_text}\n"
            f"  Expected Concepts: {concepts_str}"
        )
        if isinstance(concepts, list):
            for c in concepts:
                user_parts.append(f"- Concept: {c}")

    user_parts.append("\n### Rubric Grading Criteria:")
    if rubric_items:
        for r in rubric_items:
            crit = r.get("criterion", "")
            max_m = r.get("max_marks", 0.0)
            desc = r.get("description", "")
            r_id = r.get("id")
            user_parts.append(
                f"- Criterion: {crit} (Max Marks: {max_m})\n"
                f"  ID: {r_id}\n"
                f"  Description: {desc or 'N/A'}"
            )
    else:
        user_parts.append(f"- Criterion: General Academic Quality (Max Marks: {total_max_marks})")

    user_parts.append("\n### Retrieved Authoritative Course Knowledge (RAG Context):")
    if retrieved_chunks:
        for i, chunk in enumerate(retrieved_chunks, 1):
            text = chunk.get("chunk_text", "").strip()
            meta = chunk.get("metadata", {})
            src = meta.get("source_filename", "Course Document")
            user_parts.append(f"--- Chunk {i} (Source: {src}) ---\n{text}")
    else:
        user_parts.append("No course material chunks found in knowledge base. Base evaluation on question guidelines.")

    user_parts.append("\n### Student Submission Content:")
    user_parts.append(submission_text if submission_text.strip() else "[EMPTY SUBMISSION]")

    user_parts.append(
        "\nProvide your comprehensive evaluation now as structured JSON matching AssessmentStructuredOutput."
    )

    return SYSTEM_ASSESSMENT_PROMPT, "\n".join(user_parts)
