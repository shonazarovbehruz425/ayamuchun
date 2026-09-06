"""Quiz Service — Quiz generation, export to Word/PDF, and Telegram Quiz formatting."""

import asyncio
import logging
import os
from typing import Optional

from docx import Document
from docx.shared import Pt, Inches
from fpdf import FPDF

from bot.services.ai_service import AIService

logger = logging.getLogger(__name__)


class QuizService:
    """Service for generating quizzes and exporting them to various formats."""

    def __init__(self, ai_service: AIService) -> None:
        self.ai_service = ai_service

    async def generate_quiz_from_text(
        self,
        text: str,
        num_questions: int = 10,
        quiz_type: str = "multiple",
        language: str = "uz",
    ) -> dict:
        """Generate a quiz from the provided text using AI."""
        questions = await self.ai_service.generate_quiz(
            text, num_questions, quiz_type, language
        )
        return {"title": "Test", "questions": questions}

    # ── Export to Word ─────────────────────────────────────────────────

    async def export_to_word(self, questions: list[dict], output_path: str) -> str:
        """Export quiz questions to a Word document."""
        def _create_word():
            doc = Document()

            # Title
            title = doc.add_heading("Test savollari", level=1)

            doc.add_paragraph(f"Savollar soni: {len(questions)}")
            doc.add_paragraph("")

            for i, q in enumerate(questions, 1):
                # Question
                q_para = doc.add_paragraph()
                q_run = q_para.add_run(f"{i}. {q.get('question', '')}")
                q_run.bold = True
                q_run.font.size = Pt(12)

                # Options
                options = q.get("options", [])
                for j, opt in enumerate(options):
                    letter = chr(65 + j)
                    doc.add_paragraph(f"   {letter}) {opt}")

                doc.add_paragraph("")

            # Answer key section
            doc.add_page_break()
            doc.add_heading("Javoblar kaliti", level=1)

            for i, q in enumerate(questions, 1):
                answer = q.get("correct_answer", "")
                explanation = q.get("explanation", "")
                p = doc.add_paragraph(f"{i}. {answer}")
                if explanation:
                    exp_para = doc.add_paragraph(f"   Izoh: {explanation}")
                    exp_para.runs[0].italic = True if exp_para.runs else None

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            doc.save(output_path)
            return output_path

        return await asyncio.to_thread(_create_word)

    # ── Export to PDF ──────────────────────────────────────────────────

    async def export_to_pdf(self, questions: list[dict], output_path: str) -> str:
        """Export quiz questions to a PDF document."""
        def _create_pdf():
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            # Try to use a Unicode font if available, fallback to Arial
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Test savollari", ln=True, align="C")
            pdf.ln(5)

            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 8, f"Savollar soni: {len(questions)}", ln=True)
            pdf.ln(5)

            for i, q in enumerate(questions, 1):
                # Check if we need a new page
                if pdf.get_y() > 250:
                    pdf.add_page()

                # Question
                pdf.set_font("Helvetica", "B", 11)
                question_text = f"{i}. {q.get('question', '')}"
                # Encode safely for PDF
                safe_text = question_text.encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(0, 7, safe_text)

                # Options
                pdf.set_font("Helvetica", "", 10)
                for j, opt in enumerate(q.get("options", [])):
                    letter = chr(65 + j)
                    safe_opt = f"   {letter}) {opt}".encode("latin-1", "replace").decode("latin-1")
                    pdf.multi_cell(0, 6, safe_opt)

                pdf.ln(3)

            # Answer key
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "Javoblar kaliti", ln=True, align="C")
            pdf.ln(5)

            pdf.set_font("Helvetica", "", 10)
            for i, q in enumerate(questions, 1):
                answer = q.get("correct_answer", "")
                safe_answer = f"{i}. {answer}".encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(0, 6, safe_answer)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            pdf.output(output_path)
            return output_path

        return await asyncio.to_thread(_create_pdf)

    # ── Format for Telegram Quiz ───────────────────────────────────────

    def format_for_telegram(self, questions: list[dict]) -> list[dict]:
        """Format quiz questions for Telegram sendPoll (quiz mode)."""
        polls = []
        for q in questions:
            options = q.get("options", [])
            if len(options) < 2:
                continue  # Telegram requires at least 2 options

            # Limit to 10 options (Telegram max)
            options = options[:10]

            # Find correct option index
            correct_answer = q.get("correct_answer", "")
            correct_idx = 0
            for i, opt in enumerate(options):
                if opt.strip().lower() == correct_answer.strip().lower():
                    correct_idx = i
                    break

            polls.append({
                "question": q.get("question", "Savol")[:300],
                "options": [opt[:100] for opt in options],
                "correct_option_id": correct_idx,
                "explanation": q.get("explanation", "")[:200],
            })

        return polls
