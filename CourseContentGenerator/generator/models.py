
from django.db import models
from django.conf import settings


class CourseTopic(models.Model):

    title = models.CharField(max_length=255)

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_topics"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Quiz(models.Model):

    topic = models.ForeignKey(
        CourseTopic,
        on_delete=models.CASCADE,
        related_name="quizzes"
    )

    title = models.CharField(max_length=255)

    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question_text = models.TextField()

    def __str__(self):
        return self.question_text


class Answer(models.Model):

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    answer_text = models.CharField(max_length=500)

    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.answer_text


class GeneratedContent(models.Model):

    topic = models.ForeignKey(
        CourseTopic,
        on_delete=models.CASCADE,
        related_name="generated_contents"
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="generated_contents",
        null=True,
        blank=True
    )

    notes = models.TextField()

    key_points = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Content for {self.topic.title}"


class Summary(models.Model):

    topic = models.ForeignKey(
        CourseTopic,
        on_delete=models.CASCADE,
        related_name="summaries"
    )

    summary_text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.topic.title}"
