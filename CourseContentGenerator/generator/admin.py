
from django.contrib import admin

from .models import (
    CourseTopic,
    GeneratedContent,
    Quiz,
    Question,
    Answer,
    Summary
)


admin.site.register(CourseTopic)
admin.site.register(GeneratedContent)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(Summary)
