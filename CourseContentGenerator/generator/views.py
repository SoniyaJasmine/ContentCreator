from io import BytesIO
from xml.sax.saxutils import escape

from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    HRFlowable,
    ListFlowable,
    ListItem
)

import os
import json
import logging
import requests

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST

from .models import (
    CourseTopic,
    GeneratedContent,
    Quiz,
    Question,
    Answer,
    Summary
)

from .forms import CourseTopicForm


logger = logging.getLogger(__name__)


# -----------------------------------------
# GEMINI API FUNCTION
# -----------------------------------------

def call_gemini(prompt, api_key):

    model = os.getenv("GEMINI_MODEL")

    if not model:
        raise ValueError("GEMINI_MODEL is missing from .env")

    fallback_model = os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-3.1-flash-lite"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "notes": {
                        "type": "STRING"
                    },
                    "keyPoints": {
                        "type": "ARRAY",
                        "items": {
                            "type": "STRING"
                        }
                    },
                    "summary": {
                        "type": "STRING"
                    },
                    "quiz": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {
                                "type": "STRING"
                            },
                            "description": {
                                "type": "STRING"
                            },
                            "questions": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "questionText": {
                                            "type": "STRING"
                                        },
                                        "options": {
                                            "type": "ARRAY",
                                            "items": {
                                                "type": "OBJECT",
                                                "properties": {
                                                    "text": {
                                                        "type": "STRING"
                                                    },
                                                    "isCorrect": {
                                                        "type": "BOOLEAN"
                                                    }
                                                },
                                                "required": [
                                                    "text",
                                                    "isCorrect"
                                                ]
                                            }
                                        }
                                    },
                                    "required": [
                                        "questionText",
                                        "options"
                                    ]
                                }
                            }
                        },
                        "required": [
                            "title",
                            "description",
                            "questions"
                        ]
                    }
                },
                "required": [
                    "notes",
                    "keyPoints",
                    "summary",
                    "quiz"
                ]
            }
        }
    }

    def generate(model_name):
        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model_name}:generateContent"
        )

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        result = response.json()

        generated_text = (
            result["candidates"][0]["content"]["parts"][0]["text"]
        )

        return json.loads(generated_text)

    try:
        return generate(model)
    except requests.Timeout:
        if fallback_model == model:
            raise
    except requests.HTTPError as error:
        if (
            error.response is None
            or error.response.status_code != 503
            or fallback_model == model
        ):
            raise

    return generate(fallback_model)


# -----------------------------------------
# TEACHER DASHBOARD
# -----------------------------------------

@login_required
def dashboard(request):

    topics = CourseTopic.objects.filter(
        teacher=request.user
    ).order_by("-created_at")

    return render(
        request,
        "generator/dashboard.html",
        {"topics": topics}
    )


# -----------------------------------------
# GENERATE COURSE CONTENT
# -----------------------------------------

@login_required
def generate_content(request):

    if request.method == "POST":

        form = CourseTopicForm(request.POST)

        if form.is_valid():

            api_key = os.getenv("GEMINI_API_KEY")

            if not api_key:
                messages.error(
                    request,
                    "Gemini API key is missing."
                )

                return render(
                    request,
                    "generator/topic_form.html",
                    {"form": form}
                )

            title = form.cleaned_data["title"]

            prompt = f"""
            Act as an expert educational content generator.

            Create complete educational material for:

            Topic: {title}

            REQUIREMENTS:

            1. NOTES:
            Create detailed, easy-to-understand educational notes.
            Use headings, subheadings and examples.

            2. KEY POINTS:
            Generate 5 to 10 important key points.

            3. SUMMARY:
            Generate a short and clear summary of the topic.

            4. QUIZ:
            Create a multiple-choice quiz with 5 questions.
            Each question must have exactly 4 options.
            Only ONE option must be correct.
            Make questions suitable for students.

            RETURN VALID JSON with this exact structure:

            {{
                "notes": "Detailed educational notes",
                "keyPoints": [
                    "Point 1",
                    "Point 2"
                ],
                "summary": "Short topic summary",
                "quiz": {{
                    "title": "Topic Quiz",
                    "description": "Test your knowledge",
                    "questions": [
                        {{
                            "questionText": "Question here?",
                            "options": [
                                {{
                                    "text": "Option A",
                                    "isCorrect": false
                                }},
                                {{
                                    "text": "Option B",
                                    "isCorrect": true
                                }},
                                {{
                                    "text": "Option C",
                                    "isCorrect": false
                                }},
                                {{
                                    "text": "Option D",
                                    "isCorrect": false
                                }}
                            ]
                        }}
                    ]
                }}
            }}

            Make sure every question has exactly one correct answer.
            Return only the JSON response.
            """

            try:

                # Call Gemini API
                generated_data = call_gemini(prompt, api_key)

                # Extract generated data
                notes = generated_data["notes"]
                key_points = generated_data["keyPoints"]
                summary_text = generated_data["summary"]
                quiz_data = generated_data["quiz"]

                # Validate generated response
                if not isinstance(notes, str) or not notes.strip():
                    raise ValueError("Invalid notes generated.")

                if not isinstance(key_points, list) or not key_points:
                    raise ValueError("Invalid key points generated.")

                if not all(
                    isinstance(point, str) and point.strip()
                    for point in key_points
                ):
                    raise ValueError("Invalid key points format.")

                if not isinstance(summary_text, str) or not summary_text.strip():
                    raise ValueError("Invalid summary generated.")

                if not isinstance(quiz_data, dict):
                    raise ValueError("Invalid quiz generated.")

                questions_data = quiz_data["questions"]

                if not isinstance(questions_data, list) or not questions_data:
                    raise ValueError("Quiz has no questions.")

                if len(questions_data) > 30:
                    raise ValueError("Too many quiz questions generated.")

                # Validate every question and its options
                for question_data in questions_data:

                    if not isinstance(question_data, dict):
                        raise ValueError("Invalid question format.")

                    if not isinstance(
                        question_data.get("questionText"), str
                    ) or not question_data["questionText"].strip():
                        raise ValueError("Question text is missing.")

                    options = question_data.get("options")

                    if not isinstance(options, list) or len(options) != 4:
                        raise ValueError(
                            "Every question must have four options."
                        )

                    correct_count = sum(
                        1 for option in options
                        if isinstance(option, dict)
                        and option.get("isCorrect") is True
                    )

                    if correct_count != 1:
                        raise ValueError(
                            "Each question must have exactly one correct answer."
                        )

                    for option in options:

                        if (
                            not isinstance(option, dict)
                            or not isinstance(option.get("text"), str)
                            or not option["text"].strip()
                            or not isinstance(option.get("isCorrect"), bool)
                        ):
                            raise ValueError("Invalid answer option.")

                # Save everything together
                with transaction.atomic():

                    topic = form.save(commit=False)
                    topic.teacher = request.user
                    topic.save()

                    quiz = Quiz.objects.create(
                        topic=topic,
                        title=quiz_data["title"],
                        description=quiz_data["description"]
                    )

                    # Save questions and answers
                    for question_data in questions_data:

                        question = Question.objects.create(
                            quiz=quiz,
                            question_text=question_data["questionText"]
                        )

                        for option in question_data["options"]:

                            Answer.objects.create(
                                question=question,
                                answer_text=option["text"],
                                is_correct=option["isCorrect"]
                            )

                    # Save generated content
                    GeneratedContent.objects.create(
                        topic=topic,
                        quiz=quiz,
                        notes=notes,
                        key_points="\n".join(key_points)
                    )

                    # Save summary
                    Summary.objects.create(
                        topic=topic,
                        summary_text=summary_text
                    )

                messages.success(
                    request,
                    "Notes, summary and quiz generated successfully!"
                )

                return redirect("content_detail", pk=topic.generated_contents.first().pk)

            except requests.RequestException as e:

                logger.exception("Gemini API request failed")

                messages.error(
                    request,
                    "Unable to connect to Gemini AI. Please try again."
                )

            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:

                logger.exception("Invalid Gemini response")

                messages.error(
                    request,
                    f"AI returned invalid content: {str(e)}"
                )

            except Exception as e:

                logger.exception("Content generation or database saving failed")

                messages.error(
                    request,
                    "Something went wrong while generating or saving content."
                )

    else:

        form = CourseTopicForm()

    return render(
        request,
        "generator/topic_form.html",
        {"form": form}
    )


# -----------------------------------------
# TEACHER CONTENT DETAIL
# -----------------------------------------

@login_required
def content_detail(request, pk):

    content = get_object_or_404(
        GeneratedContent.objects.select_related("topic"),
        pk=pk,
        topic__teacher=request.user
    )

    key_points = [
        point for point in content.key_points.split("\n")
        if point.strip()
    ]

    return render(
        request,
        "generator/content_detail.html",
        {
            "content": content,
            "key_points": key_points
        }
    )


# -----------------------------------------
# DELETE TOPIC
# -----------------------------------------

@login_required
@require_POST
def delete_topic(request, pk):

    topic = get_object_or_404(
        CourseTopic,
        pk=pk,
        teacher=request.user
    )

    topic.delete()

    messages.success(request, "Topic deleted successfully.")

    return redirect("dashboard")


# -----------------------------------------
# STUDENT DASHBOARD
# -----------------------------------------

def student_dashboard(request):

    topics = CourseTopic.objects.filter(
        generated_contents__isnull=False
    ).distinct().order_by("-created_at")

    return render(
        request,
        "generator/student_dashboard.html",
        {"topics": topics}
    )


# -----------------------------------------
# STUDENT CONTENT VIEW
# -----------------------------------------

def view_content(request, topic_id):

    topic = get_object_or_404(CourseTopic, pk=topic_id)

    content = get_object_or_404(
        GeneratedContent.objects.filter(topic=topic).select_related("quiz"),
        pk=GeneratedContent.objects.filter(topic=topic)
        .order_by("-created_at")
        .values_list("pk", flat=True)
        .first()
    )

    summary = Summary.objects.filter(
        topic=topic
    ).order_by("-created_at").first()

    quiz = content.quiz

    questions = []

    if quiz:

        questions = quiz.questions.prefetch_related(
            "answers"
        ).all()

    key_points = [
        point for point in content.key_points.split("\n")
        if point.strip()
    ]

    return render(
        request,
        "generator/view_content.html",
        {
            "topic": topic,
            "content": content,
            "summary": summary,
            "quiz": quiz,
            "questions": questions,
            "key_points": key_points
        }
    )


# -----------------------------------------
# STUDENT QUIZ SUBMISSION
# -----------------------------------------

@require_POST
def submit_quiz(request, quiz_id):

    quiz = get_object_or_404(Quiz, pk=quiz_id)

    questions = quiz.questions.prefetch_related("answers").all()

    total_questions = questions.count()

    score = 0
    results = []

    for question in questions:

        selected_answer_id = request.POST.get(
            f"question_{question.id}"
        )

        selected_answer = None

        if selected_answer_id:
            selected_answer = question.answers.filter(
                pk=selected_answer_id
            ).first()

        correct_answer = question.answers.filter(
            is_correct=True
        ).first()

        is_correct = (
            selected_answer is not None
            and selected_answer.is_correct
        )

        if is_correct:
            score += 1

        results.append({
            "question": question.question_text,
            "selected_answer": (
                selected_answer.answer_text
                if selected_answer else "Not answered"
            ),
            "correct_answer": (
                correct_answer.answer_text
                if correct_answer else "Not available"
            ),
            "is_correct": is_correct
        })

    percentage = (
        round((score / total_questions) * 100, 2)
        if total_questions else 0
    )

    return render(
        request,
        "generator/quiz_result.html",
        {
            "quiz": quiz,
            "score": score,
            "total_questions": total_questions,
            "percentage": percentage,
            "results": results
        }
    )


@login_required
def export_pdf(request, topic_id):

    # Fetch course topic belonging to the logged-in teacher
    topic = get_object_or_404(
        CourseTopic,
        pk=topic_id,
        teacher=request.user
    )

    # Fetch latest generated content
    content = get_object_or_404(
        GeneratedContent.objects.select_related("quiz"),
        topic=topic
    )

    # Fetch summary
    summary = Summary.objects.filter(
        topic=topic
    ).order_by("-created_at").first()

    # Fetch quiz and related questions
    quiz = content.quiz

    questions = []

    if quiz:
        questions = quiz.questions.prefetch_related(
            "answers"
        ).all()

    # Create PDF buffer
    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=55,
        leftMargin=55,
        topMargin=55,
        bottomMargin=55
    )

    # PDF styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=26,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#352B75"),
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=17,
        leading=23,
        textColor=colors.HexColor("#352B75"),
        spaceBefore=15,
        spaceAfter=12
    )

    normal_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=16,
        spaceAfter=8
    )

    question_style = ParagraphStyle(
        "QuestionStyle",
        parent=normal_style,
        fontSize=11,
        leading=16,
        spaceBefore=10,
        spaceAfter=6
    )

    # PDF content
    story = []

    # TITLE PAGE
    story.append(Spacer(1, 1.5 * inch))

    story.append(
        Paragraph("AI COURSE CONTENT GENERATOR", title_style)
    )

    story.append(
        HRFlowable(
            width="80%",
            thickness=2,
            color=colors.HexColor("#6254C5"),
            spaceAfter=30
        )
    )

    story.append(
        Paragraph(escape(topic.title), title_style)
    )

    story.append(Spacer(1, 25))

    story.append(
        Paragraph(
            f"<b>Teacher:</b> {escape(topic.teacher.username)}",
            normal_style
        )
    )

    story.append(
        Paragraph(
            f"<b>Created:</b> {topic.created_at.strftime('%d %B %Y')}",
            normal_style
        )
    )

    story.append(Spacer(1, 1 * inch))

    story.append(
        Paragraph(
            "Generated Study Material",
            ParagraphStyle(
                "Subtitle",
                parent=normal_style,
                alignment=TA_CENTER,
                fontSize=14,
                textColor=colors.grey
            )
        )
    )

    story.append(PageBreak())

    # SUMMARY SECTION
    story.append(
        Paragraph("1. Topic Summary", heading_style)
    )

    if summary:
        story.append(
            Paragraph(
                escape(summary.summary_text).replace("\n", "<br/>"),
                normal_style
            )
        )
    else:
        story.append(
            Paragraph("Summary not available.", normal_style)
        )

    story.append(Spacer(1, 15))

    # NOTES SECTION
    story.append(
        Paragraph("2. Course Notes", heading_style)
    )

    for line in content.notes.splitlines():

        line = line.strip()

        if line:
            story.append(
                Paragraph(
                    escape(line),
                    normal_style
                )
            )

    story.append(Spacer(1, 15))

    # KEY POINTS SECTION
    story.append(
        Paragraph("3. Important Key Points", heading_style)
    )

    key_points = [
        point.strip()
        for point in content.key_points.splitlines()
        if point.strip()
    ]

    if key_points:

        bullet_items = [
            ListItem(
                Paragraph(escape(point), normal_style)
            )
            for point in key_points
        ]

        story.append(
            ListFlowable(
                bullet_items,
                bulletType="bullet",
                leftIndent=20
            )
        )

    story.append(PageBreak())

    # QUIZ SECTION
    story.append(
        Paragraph("4. Multiple Choice Quiz", heading_style)
    )

    if quiz:

        story.append(
            Paragraph(
                escape(quiz.title),
                styles["Heading3"]
            )
        )

        story.append(
            Paragraph(
                escape(quiz.description),
                normal_style
            )
        )

        for index, question in enumerate(questions, start=1):

            story.append(
                Paragraph(
                    f"<b>Q{index}. {escape(question.question_text)}</b>",
                    question_style
                )
            )

            answers = question.answers.all()

            for answer_index, answer in enumerate(answers):

                option_label = chr(65 + answer_index)

                story.append(
                    Paragraph(
                        f"{option_label}. {escape(answer.answer_text)}",
                        normal_style
                    )
                )

        # Correct answers on separate section
        story.append(PageBreak())

        story.append(
            Paragraph("5. Quiz Answer Key", heading_style)
        )

        for index, question in enumerate(questions, start=1):

            correct_answer = question.answers.filter(
                is_correct=True
            ).first()

            if correct_answer:

                story.append(
                    Paragraph(
                        f"Q{index}. {escape(correct_answer.answer_text)}",
                        normal_style
                    )
                )

    else:

        story.append(
            Paragraph("No quiz available.", normal_style)
        )

    # Build PDF
    pdf.build(story)

    buffer.seek(0)

    filename = f"course_{topic.id}_study_material.pdf"

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf"
    )
