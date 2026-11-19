
import json
from unittest.mock import Mock, patch

import requests
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from .models import (
    CourseTopic,
    GeneratedContent,
    Quiz,
    Question,
    Answer,
    Summary
)
from .views import call_gemini


class CourseTopicModelTest(TestCase):

    def setUp(self):

        self.teacher = User.objects.create_user(
            username="teacher",
            password="test12345"
        )

    def test_create_topic(self):

        topic = CourseTopic.objects.create(
            title="Python Programming",
            teacher=self.teacher
        )

        self.assertEqual(
            topic.title,
            "Python Programming"
        )

        self.assertEqual(topic.teacher, self.teacher)

    def test_update_topic(self):

        topic = CourseTopic.objects.create(
            title="Python",
            teacher=self.teacher
        )

        topic.title = "Advanced Python"
        topic.save()

        self.assertEqual(
            topic.title,
            "Advanced Python"
        )

    def test_delete_topic(self):

        topic = CourseTopic.objects.create(
            title="Django",
            teacher=self.teacher
        )

        topic.delete()

        self.assertFalse(
            CourseTopic.objects.filter(pk=topic.pk).exists()
        )


class GeneratedContentModelTest(TestCase):

    def setUp(self):

        self.teacher = User.objects.create_user(
            username="teacher",
            password="test12345"
        )

        self.topic = CourseTopic.objects.create(
            title="Python",
            teacher=self.teacher
        )

        self.quiz = Quiz.objects.create(
            topic=self.topic,
            title="Python Quiz",
            description="Test your Python knowledge"
        )

    def test_create_content(self):

        content = GeneratedContent.objects.create(
            topic=self.topic,
            quiz=self.quiz,
            notes="Python notes",
            key_points="Variables\nLoops"
        )

        self.assertEqual(content.topic, self.topic)
        self.assertEqual(content.quiz, self.quiz)

    def test_update_content(self):

        content = GeneratedContent.objects.create(
            topic=self.topic,
            notes="Old notes",
            key_points="Old points"
        )

        content.notes = "Updated notes"
        content.save()

        self.assertEqual(content.notes, "Updated notes")

    def test_delete_content(self):

        content = GeneratedContent.objects.create(
            topic=self.topic,
            notes="Notes",
            key_points="Points"
        )

        content.delete()

        self.assertFalse(
            GeneratedContent.objects.filter(pk=content.pk).exists()
        )


class QuizModelTest(TestCase):

    def setUp(self):

        self.teacher = User.objects.create_user(
            username="teacher",
            password="test12345"
        )

        self.topic = CourseTopic.objects.create(
            title="Django",
            teacher=self.teacher
        )

    def test_create_quiz(self):

        quiz = Quiz.objects.create(
            topic=self.topic,
            title="Django Quiz",
            description="Test Django knowledge"
        )

        self.assertEqual(quiz.topic, self.topic)

    def test_update_quiz(self):

        quiz = Quiz.objects.create(
            topic=self.topic,
            title="Old Quiz",
            description="Description"
        )

        quiz.title = "Updated Quiz"
        quiz.save()

        self.assertEqual(quiz.title, "Updated Quiz")

    def test_delete_quiz(self):

        quiz = Quiz.objects.create(
            topic=self.topic,
            title="Quiz",
            description="Description"
        )

        quiz.delete()

        self.assertFalse(
            Quiz.objects.filter(pk=quiz.pk).exists()
        )


class QuestionModelTest(TestCase):

    def setUp(self):

        self.teacher = User.objects.create_user(
            username="teacher",
            password="test12345"
        )

        self.topic = CourseTopic.objects.create(
            title="Python",
            teacher=self.teacher
        )

        self.quiz = Quiz.objects.create(
            topic=self.topic,
            title="Python Quiz",
            description="Quiz"
        )

    def test_create_question(self):

        question = Question.objects.create(
            quiz=self.quiz,
            question_text="What is Python?"
        )

        self.assertEqual(question.quiz, self.quiz)

    def test_update_question(self):

        question = Question.objects.create(
            quiz=self.quiz,
            question_text="Old question"
        )

        question.question_text = "New question"
        question.save()

        self.assertEqual(
            question.question_text,
            "New question"
        )

    def test_delete_question(self):

        question = Question.objects.create(
            quiz=self.quiz,
            question_text="Test question"
        )

        question.delete()

        self.assertFalse(
            Question.objects.filter(pk=question.pk).exists()
        )


class AnswerModelTest(TestCase):

    def setUp(self):

        self.teacher = User.objects.create_user(
            username="teacher",
            password="test12345"
        )

        self.topic = CourseTopic.objects.create(
            title="Python",
            teacher=self.teacher
        )

        self.quiz = Quiz.objects.create(
            topic=self.topic,
            title="Python Quiz",
            description="Quiz"
        )

        self.question = Question.objects.create(
            quiz=self.quiz,
            question_text="What is Python?"
        )

    def test_create_answer(self):

        answer = Answer.objects.create(
            question=self.question,
            answer_text="Programming Language",
            is_correct=True
        )

        self.assertTrue(answer.is_correct)

    def test_update_answer(self):

        answer = Answer.objects.create(
            question=self.question,
            answer_text="Old Answer",
            is_correct=False
        )

        answer.answer_text = "Correct Answer"
        answer.is_correct = True
        answer.save()

        self.assertEqual(answer.answer_text, "Correct Answer")
        self.assertTrue(answer.is_correct)

    def test_delete_answer(self):

        answer = Answer.objects.create(
            question=self.question,
            answer_text="Option A",
            is_correct=False
        )

        answer.delete()

        self.assertFalse(
            Answer.objects.filter(pk=answer.pk).exists()
        )


class SummaryModelTest(TestCase):

    def test_create_summary(self):

        teacher = User.objects.create_user(
            username="summary_teacher",
            password="test12345"
        )

        topic = CourseTopic.objects.create(
            title="Machine Learning",
            teacher=teacher
        )

        summary = Summary.objects.create(
            topic=topic,
            summary_text="Introduction to Machine Learning"
        )

        self.assertEqual(summary.topic, topic)

        self.assertEqual(
            summary.summary_text,
            "Introduction to Machine Learning"
        )


class GeminiApiTest(TestCase):

    @patch.dict("os.environ", {
        "GEMINI_MODEL": "gemini-3.8-flash",
        "GEMINI_FALLBACK_MODEL": "gemini-3.1-flash-lite"
    })
    @patch("generator.views.requests.post")
    def test_overloaded_primary_uses_fallback_model(self, mock_post):
        primary_response = Mock()
        primary_response.status_code = 503
        primary_response.raise_for_status.side_effect = requests.HTTPError(
            response=primary_response
        )

        generated_data = {
            "notes": "Photosynthesis notes",
            "keyPoints": ["Plants use light."]
        }
        fallback_response = Mock()
        fallback_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps(generated_data)
                    }]
                }
            }]
        }
        mock_post.side_effect = [primary_response, fallback_response]

        result = call_gemini("prompt", "api-key")

        self.assertEqual(result, generated_data)
        self.assertEqual(mock_post.call_count, 2)
        self.assertIn(
            "models/gemini-3.1-flash-lite:",
            mock_post.call_args_list[1].args[0]
        )


class CourseContentViewTest(TestCase):

    def setUp(self):

        self.client = Client()

        self.teacher = User.objects.create_user(
            username="teacher",
            password="test12345"
        )

        self.client.force_login(self.teacher)

        self.topic = CourseTopic.objects.create(
            title="Python Programming",
            teacher=self.teacher
        )

        self.quiz = Quiz.objects.create(
            topic=self.topic,
            title="Python Quiz",
            description="Test your knowledge"
        )

        self.question = Question.objects.create(
            quiz=self.quiz,
            question_text="What is Python?"
        )

        Answer.objects.create(
            question=self.question,
            answer_text="Programming Language",
            is_correct=True
        )

    @patch("generator.views.call_gemini")
    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "test-api-key",
        "GEMINI_MODEL": "test-model"
    })
    def test_generate_content(self, mock_gemini):

        mock_gemini.return_value = {
            "notes": "Python is a programming language.",
            "keyPoints": [
                "Easy to learn",
                "Interpreted language"
            ],
            "summary": "Python is a popular language.",
            "quiz": {
                "title": "Python Quiz",
                "description": "Test Python knowledge",
                "questions": [
                    {
                        "questionText": "What is Python?",
                        "options": [
                            {
                                "text": "Programming Language",
                                "isCorrect": True
                            },
                            {
                                "text": "Database",
                                "isCorrect": False
                            },
                            {
                                "text": "Browser",
                                "isCorrect": False
                            },
                            {
                                "text": "Operating System",
                                "isCorrect": False
                            }
                        ]
                    }
                ]
            }
        }

        response = self.client.post(
            reverse("generate_content"),
            {"title": "Generated Python Course"}
        )

        self.assertEqual(response.status_code, 302)

        topic = CourseTopic.objects.get(
            title="Generated Python Course"
        )

        self.assertTrue(
            GeneratedContent.objects.filter(topic=topic).exists()
        )

        self.assertTrue(
            Summary.objects.filter(topic=topic).exists()
        )

        self.assertEqual(
            topic.quizzes.count(),
            1
        )

        self.assertEqual(
            Question.objects.filter(
                quiz__topic=topic
            ).count(),
            1
        )

        self.assertEqual(
            Answer.objects.filter(
                question__quiz__topic=topic
            ).count(),
            4
        )

    def test_export_pdf(self):

        content = GeneratedContent.objects.create(
            topic=self.topic,
            quiz=self.quiz,
            notes="Python is a programming language.",
            key_points="Easy to learn\nInterpreted language"
        )

        Summary.objects.create(
            topic=self.topic,
            summary_text="Python is a popular language."
        )

        response = self.client.get(
            reverse(
                "export_pdf",
                args=[self.topic.id]
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response["Content-Type"],
            "application/pdf"
        )

        self.assertIn(
            "attachment",
            response["Content-Disposition"]
        )

        pdf_content = b"".join(response.streaming_content)

        self.assertTrue(pdf_content.startswith(b"%PDF"))

    def test_student_dashboard(self):

        GeneratedContent.objects.create(
            topic=self.topic,
            quiz=self.quiz,
            notes="Python notes",
            key_points="Python points"
        )

        response = self.client.get(
            reverse("student_dashboard")
        )

        self.assertEqual(response.status_code, 200)

    def test_view_content(self):

        GeneratedContent.objects.create(
            topic=self.topic,
            quiz=self.quiz,
            notes="Python notes",
            key_points="Python points"
        )

        response = self.client.get(
            reverse(
                "view_content",
                args=[self.topic.id]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_quiz_submission(self):

        response = self.client.post(
            reverse(
                "submit_quiz",
                args=[self.quiz.id]
            ),
            {
                f"question_{self.question.id}":
                    self.question.answers.get(
                        is_correct=True
                    ).id
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "100.0%")
