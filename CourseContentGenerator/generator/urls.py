
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views


urlpatterns = [

    # Teacher URLs
    path("", views.dashboard, name="dashboard"),

    path(
        "generate/",
        views.generate_content,
        name="generate_content"
    ),

    path(
        "content/<int:pk>/",
        views.content_detail,
        name="content_detail"
    ),

    path(
        "delete/<int:pk>/",
        views.delete_topic,
        name="delete_topic"
    ),

    # Login and Logout
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="generator/login.html"
        ),
        name="login"
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout"
    ),

    # Student LMS URLs
    path(
        "student/",
        views.student_dashboard,
        name="student_dashboard"
    ),

    path(
        "student/course/<int:topic_id>/",
        views.view_content,
        name="view_content"
    ),

    path(
        "student/quiz/<int:quiz_id>/submit/",
        views.submit_quiz,
        name="submit_quiz"
    ),

    path(
    "student/course/<int:topic_id>/pdf/",
    views.export_pdf,
    name="export_pdf"
),

]
