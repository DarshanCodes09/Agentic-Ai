"""
AssessmentAgent: Evaluates student submission against rubric criteria, questions, and RAG context.
"""

import logging
from app.schemas.assessment import AssessmentStructuredOutput
from app.services.assessment.preparation_service import AssessmentContext
from app.services.llm.client import LLMService, get_llm_service
from app.services.llm.prompts.assessment_prompt import build_assessment_prompts

logger = logging.getLogger(__name__)


class AssessmentAgent:
    """Agent responsible for rigorous rubric-based grading and concept mastery evaluation."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    async def evaluate(self, context: AssessmentContext) -> AssessmentStructuredOutput:
        """
        Execute LLM evaluation for the provided assessment context.
        Validates, clamps, and aligns scores within legal rubric bounds.
        Applies multi-pass adaptive evidence reduction to ensure the complete
        serialized request fits within model context and TPM limits.
        """
        from app.core.config import get_settings
        from app.services.llm.token_budget import get_model_safe_token_limit

        settings = get_settings()
        model_name = getattr(self.llm_service, "model_name", "llama-3.3-70b-versatile")
        max_tokens = get_model_safe_token_limit(model_name)
        max_chars = settings.max_assessment_prompt_chars

        system_prompt, user_prompt = self._prepare_bounded_prompts(
            context=context,
            model_name=model_name,
            max_tokens=max_tokens,
            max_chars=max_chars,
        )

        result: AssessmentStructuredOutput = await self.llm_service.generate_structured(
            prompt=user_prompt,
            response_model=AssessmentStructuredOutput,
            system_prompt=system_prompt,
        )

        # Post-validation and score bounding safeguards
        validated_result = self._validate_and_bound_scores(result, context)
        return validated_result

    def _compact_submission_evidence(self, sub_text: str, max_chars: int) -> str:
        """
        Intelligently compacts submission evidence to fit within max_chars while
        preserving critical headers, archive inventories, execution audits,
        and criterion mappings, with explicit omission notices.
        """
        if len(sub_text) <= max_chars:
            return sub_text

        # If this is a multi-file ZIP archive evidence package
        if "=== MULTI-FILE PROJECT ARCHIVE EVIDENCE:" in sub_text:
            header_marker = "--- COMPLETE ARCHIVE INVENTORY TREE ---"
            if header_marker in sub_text:
                header_part, rest = sub_text.split(header_marker, 1)
                omission_notice = (
                    f"\n\n... [Notice: Secondary code implementation and output details condensed to fit "
                    f"model token quota ({max_chars} chars). Archive inventory and diagnostics preserved.] ..."
                )
                overhead = len(header_part) + len(header_marker) + len(omission_notice) + 50
                rem_rest = max(200, max_chars - overhead)
                return f"{header_part}{header_marker}{rest[:rem_rest]}{omission_notice}"

        # If this is a Jupyter Notebook
        if "=== JUPYTER NOTEBOOK INSPECTION AUDIT ===" in sub_text:
            audit_marker = "--- NOTEBOOK CELLS & OUTPUTS ---"
            if audit_marker in sub_text:
                audit_header, cells_rest = sub_text.split(audit_marker, 1)
                omission_notice = (
                    f"\n\n... [Notice: Notebook cells condensed to fit model token quota ({max_chars} chars). "
                    "Execution audit, cell status, and error logs preserved.] ..."
                )
                overhead = len(audit_header) + len(audit_marker) + len(omission_notice) + 50
                rem_cells = max(200, max_chars - overhead)
                return f"{audit_header}{audit_marker}{cells_rest[:rem_cells]}{omission_notice}"

        # Standard / single file submission
        omission_notice = (
            f"\n\n... [Notice: Submission content condensed to {max_chars} characters to satisfy "
            "safe AI model token limits. Full original submission preserved in system storage.] ..."
        )
        avail = max(100, max_chars - len(omission_notice))
        return f"{sub_text[:avail]}{omission_notice}"

    def _prepare_bounded_prompts(
        self,
        context: AssessmentContext,
        model_name: str,
        max_tokens: int,
        max_chars: int,
    ) -> tuple[str, str]:
        """
        Builds the assessment prompts using multi-pass adaptive reduction to ensure
        the complete serialized request (system directive + schema + user prompt)
        strictly fits within max_tokens and max_chars with a safety margin, while
        preserving non-negotiable rubric items and assignment questions.
        """
        import json
        from app.core.exceptions import PayloadTooLargeError
        from app.services.llm.token_budget import estimate_tokens
        from app.services.document_processing.zip_processor import get_zip_processor

        schema_json = json.dumps(AssessmentStructuredOutput.model_json_schema())
        sub_id = getattr(context.submission, "id", "unknown")

        # 1. Safety target budget with reasonable safety buffer (Requirement 3)
        safe_token_margin = min(200, max(80, int(max_tokens * 0.05)))
        safe_target_tokens = max_tokens - safe_token_margin
        safe_target_chars = int(max_chars * 0.95)

        # 2. Preflight baseline check for non-negotiable rubric & questions (Requirement 7)
        baseline_sys, baseline_user = build_assessment_prompts(
            assignment_title=context.assignment_title,
            assignment_description=None,
            total_max_marks=context.total_max_marks,
            questions=context.questions,
            rubric_items=context.rubric_items,
            retrieved_chunks=[],
            submission_text="[SUBMISSION PLACEHOLDER]",
            assignment_instructions=None,
            assignment_documents_text=None,
        )
        baseline_directive = f"{baseline_sys}\n\nYou MUST return ONLY valid JSON matching this schema:\n{schema_json}"
        baseline_tokens = estimate_tokens(baseline_directive) + estimate_tokens(baseline_user)
        baseline_chars = len(baseline_directive) + len(baseline_user)

        if baseline_tokens > max_tokens or baseline_chars > max_chars:
            rubric_tokens = estimate_tokens("\n".join(f"{r.get('criterion', '')} {r.get('description', '')}" for r in context.rubric_items))
            questions_tokens = estimate_tokens("\n".join(f"{q.get('question_text', '')} {q.get('expected_concepts', '')}" for q in context.questions))
            logger.error(
                "Failure Stage: Baseline Non-Negotiables Exceed Token Budget. "
                "baseline_tokens=%d > max_tokens=%d (rubric_tokens=%d, questions_tokens=%d)",
                baseline_tokens, max_tokens, rubric_tokens, questions_tokens,
            )
            raise PayloadTooLargeError(
                detail=(
                    f"The approved rubric criteria ({len(context.rubric_items)} criteria, ~{rubric_tokens} tokens) "
                    f"and assignment questions ({len(context.questions)} questions, ~{questions_tokens} tokens) "
                    f"alone require ~{baseline_tokens} tokens, which exceeds the AI model safe limit ({max_tokens} tokens). "
                    "Please condense the rubric criteria or question descriptions to proceed with AI assessment."
                )
            )

        # Working state for reduction passes
        curr_submission_text = context.submission_text
        curr_rag_chunks = list(context.retrieved_chunks)
        curr_instructions = context.assignment_instructions or context.assignment_description
        curr_docs = getattr(context, "assignment_documents_text", "")

        def serialize_and_measure(
            sub_text: str,
            rag_chunks: list[dict[str, Any]],
            instructions: str | None,
            docs: str | None,
        ) -> tuple[str, str, str, int, int]:
            sys_p, user_p = build_assessment_prompts(
                assignment_title=context.assignment_title,
                assignment_description=context.assignment_description if not instructions else None,
                total_max_marks=context.total_max_marks,
                questions=context.questions,
                rubric_items=context.rubric_items,
                retrieved_chunks=rag_chunks,
                submission_text=sub_text,
                assignment_instructions=instructions,
                assignment_documents_text=docs,
            )
            s_directive = f"{sys_p}\n\nYou MUST return ONLY valid JSON matching this schema:\n{schema_json}"
            t_chars = len(s_directive) + len(user_p)
            t_tokens = estimate_tokens(s_directive) + estimate_tokens(user_p)
            return sys_p, user_p, s_directive, t_chars, t_tokens

        last_sys_prompt = ""
        last_user_prompt = ""
        total_req_chars = 0
        total_req_tokens = 0

        # Multi-pass reduction loop (up to 5 passes: Pass 0 to Pass 4)
        for pass_num in range(5):
            if pass_num == 0:
                # Pass 0: Try full assembled context
                pass
            elif pass_num == 1:
                # Pass 1: Prune optional course RAG chunks (Requirement 5)
                if curr_rag_chunks:
                    logger.info(
                        "Adaptive prompt reduction (Pass 1): Dropping %d optional RAG course chunks.",
                        len(curr_rag_chunks),
                    )
                    curr_rag_chunks = []
            elif pass_num == 2:
                # Pass 2: Condense attached specification documents and calculate dynamic evidence budget
                logger.info("Adaptive prompt reduction (Pass 2): Condensing secondary docs and computing available evidence budget.")
                if curr_docs and len(curr_docs) > 800:
                    curr_docs = (
                        curr_docs[:800]
                        + "\n... [Notice: Attached specification condensed to primary requirements for token budget.] ..."
                    )
                if curr_instructions and len(curr_instructions) > 600:
                    curr_instructions = (
                        curr_instructions[:600]
                        + "\n... [Notice: Instructions condensed to core requirements.] ..."
                    )

                # Compute exact tokens used without submission evidence
                _, user_no_sub, s_dir_no_sub, chars_no_sub, tokens_no_sub = serialize_and_measure(
                    sub_text="",
                    rag_chunks=curr_rag_chunks,
                    instructions=curr_instructions,
                    docs=curr_docs,
                )
                avail_tokens = max(200, safe_target_tokens - tokens_no_sub)
                avail_chars = max(600, min(safe_target_chars - chars_no_sub, int(avail_tokens * 3.0)))

                if getattr(context, "zip_inventory", None):
                    zip_proc = get_zip_processor()
                    curr_submission_text = zip_proc.build_evidence_package(
                        manifest=context.zip_inventory,
                        archive_name=getattr(context, "original_archive_name", "project.zip") or "project.zip",
                        evidence_budget=avail_chars,
                        rubric_items=context.rubric_items,
                        assignment_instructions=curr_instructions,
                        assignment_title=context.assignment_title,
                    )
                else:
                    curr_submission_text = self._compact_submission_evidence(curr_submission_text, avail_chars)
            elif pass_num == 3:
                # Pass 3: Aggressive reduction for tight token quotas (e.g. 4,282 -> <4,000 tokens)
                logger.info("Adaptive prompt reduction (Pass 3): Aggressive condensation of docs and student evidence.")
                if curr_docs and len(curr_docs) > 350:
                    curr_docs = (
                        curr_docs[:350]
                        + "\n... [Notice: Attached specification condensed to primary requirements for token budget.] ..."
                    )
                if curr_instructions and len(curr_instructions) > 350:
                    curr_instructions = (
                        curr_instructions[:350]
                        + "\n... [Notice: Instructions condensed to core requirements.] ..."
                    )

                _, user_no_sub, s_dir_no_sub, chars_no_sub, tokens_no_sub = serialize_and_measure(
                    sub_text="",
                    rag_chunks=curr_rag_chunks,
                    instructions=curr_instructions,
                    docs=curr_docs,
                )
                avail_tokens = max(150, safe_target_tokens - tokens_no_sub)
                avail_chars = max(450, min(safe_target_chars - chars_no_sub, int(avail_tokens * 2.8)))

                if getattr(context, "zip_inventory", None):
                    zip_proc = get_zip_processor()
                    curr_submission_text = zip_proc.build_evidence_package(
                        manifest=context.zip_inventory,
                        archive_name=getattr(context, "original_archive_name", "project.zip") or "project.zip",
                        evidence_budget=avail_chars,
                        rubric_items=context.rubric_items,
                        assignment_instructions=curr_instructions,
                        assignment_title=context.assignment_title,
                    )
                else:
                    curr_submission_text = self._compact_submission_evidence(curr_submission_text, avail_chars)
            elif pass_num == 4:
                # Pass 4: Minimal essential evidence fallback with strict token bounding
                logger.info("Adaptive prompt reduction (Pass 4): Retaining minimal essential evidence and core rubric.")
                if curr_docs:
                    curr_docs = "[Attached assignment specification files verified; condensed to primary criteria for token limits.]"
                if curr_instructions and len(curr_instructions) > 180:
                    curr_instructions = curr_instructions[:180] + "\n... [Core instructions retained]"

                _, user_no_sub, s_dir_no_sub, chars_no_sub, tokens_no_sub = serialize_and_measure(
                    sub_text="",
                    rag_chunks=[],
                    instructions=curr_instructions,
                    docs=curr_docs,
                )
                avail_tokens = max(100, safe_target_tokens - tokens_no_sub)
                avail_chars = max(300, min(safe_target_chars - chars_no_sub, int(avail_tokens * 2.5)))

                if getattr(context, "zip_inventory", None):
                    zip_proc = get_zip_processor()
                    curr_submission_text = zip_proc.build_evidence_package(
                        manifest=context.zip_inventory,
                        archive_name=getattr(context, "original_archive_name", "project.zip") or "project.zip",
                        evidence_budget=avail_chars,
                        rubric_items=context.rubric_items,
                        assignment_instructions=curr_instructions,
                        assignment_title=context.assignment_title,
                    )
                else:
                    curr_submission_text = self._compact_submission_evidence(curr_submission_text, avail_chars)

            sys_prompt, user_prompt, system_directive, total_req_chars, total_req_tokens = serialize_and_measure(
                curr_submission_text, curr_rag_chunks, curr_instructions, curr_docs
            )
            last_sys_prompt = sys_prompt
            last_user_prompt = user_prompt

            # Check if converged below target (using safe target in early passes, and hard limit in later passes)
            limit_to_check = safe_target_tokens if pass_num < 4 else max_tokens
            chars_limit_to_check = safe_target_chars if pass_num < 4 else max_chars

            if total_req_tokens <= limit_to_check and total_req_chars <= chars_limit_to_check:
                submission_len = len(curr_submission_text)
                instructions_len = len(curr_instructions or "")
                questions_len = sum(len(q.get("question_text", "")) for q in context.questions)
                rubric_len = sum(len(r.get("criterion", "")) + len(r.get("description", "") or "") for r in context.rubric_items)
                rag_len = sum(len(c.get("chunk_text", "")) for c in curr_rag_chunks)

                logger.info(
                    "Assessment prompt successfully prepared (Pass %d) for submission %s [model=%s]: "
                    "total_serialized_chars=%d, estimated_tokens=%d (budget=%d tokens, safe_target=%d tokens) "
                    "[system=%d, user=%d | submission_evidence=%d, rag=%d, rubric=%d, questions=%d, instructions=%d]",
                    pass_num,
                    sub_id,
                    model_name,
                    total_req_chars,
                    total_req_tokens,
                    max_tokens,
                    safe_target_tokens,
                    len(system_directive),
                    len(user_prompt),
                    submission_len,
                    rag_len,
                    rubric_len,
                    questions_len,
                    instructions_len,
                )
                return sys_prompt, user_prompt

        # Final verification: If still oversized after Pass 4 (Requirement 8)
        if total_req_tokens <= max_tokens and total_req_chars <= max_chars:
            return last_sys_prompt, last_user_prompt

        logger.warning(
            "Failure Stage: Local Prompt Budget Exceeded for submission %s: total_chars=%d, est_tokens=%d exceeds limit (%d tokens, %d chars).",
            sub_id, total_req_chars, total_req_tokens, max_tokens, max_chars,
        )
        raise PayloadTooLargeError(
            detail=(
                f"Assessment request size ({total_req_chars} chars, ~{total_req_tokens} tokens) exceeds "
                f"the AI model safe token limit ({max_tokens} tokens) even after multi-pass adaptive reduction. "
                f"[Breakdown: System & Schema={len(system_directive)} chars, "
                f"Rubric & Questions={len(last_user_prompt) - len(curr_submission_text)} chars, "
                f"Submission Evidence={len(curr_submission_text)} chars]. "
                "Please reduce submission file size or code complexity."
            )
        )

    def _validate_and_bound_scores(
        self, result: AssessmentStructuredOutput, context: AssessmentContext
    ) -> AssessmentStructuredOutput:
        """Ensure scores do not exceed maximum bounds and match rubric item IDs."""
        rubric_map = {item["criterion"].lower(): item for item in context.rubric_items}
        evaluated_criteria_names = set()

        bounded_criteria = []
        for crit in result.criteria_scores:
            crit_name_lower = crit.criterion.lower()
            matched_item = rubric_map.get(crit_name_lower)
            item_id = matched_item["id"] if matched_item else crit.rubric_item_id
            crit_max = matched_item["max_marks"] if matched_item else crit.max_marks

            # Clamp criterion score between 0.0 and crit_max
            clamped_score = max(0.0, min(float(crit.score), float(crit_max)))
            crit.rubric_item_id = item_id
            crit.score = round(clamped_score, 2)
            crit.max_marks = float(crit_max)
            bounded_criteria.append(crit)
            evaluated_criteria_names.add(crit_name_lower)

        # Ensure all rubric criteria from context are represented
        for item in context.rubric_items:
            if item["criterion"].lower() not in evaluated_criteria_names:
                from app.schemas.assessment import CriterionEvaluation
                bounded_criteria.append(
                    CriterionEvaluation(
                        rubric_item_id=item["id"],
                        criterion=item["criterion"],
                        score=0.0,
                        max_marks=float(item["max_marks"]),
                        reasoning="Criterion was not directly evaluated in model response.",
                    )
                )

        # Total score validation
        if bounded_criteria:
            summed_score = sum(c.score for c in bounded_criteria)
            final_ai_score = max(0.0, min(summed_score, context.total_max_marks))
        else:
            final_ai_score = max(0.0, min(result.ai_score, context.total_max_marks))

        result.ai_score = round(final_ai_score, 2)
        result.criteria_scores = bounded_criteria
        return result



_assessment_agent_instance: AssessmentAgent | None = None


def get_assessment_agent() -> AssessmentAgent:
    global _assessment_agent_instance
    if _assessment_agent_instance is None:
        _assessment_agent_instance = AssessmentAgent()
    return _assessment_agent_instance
