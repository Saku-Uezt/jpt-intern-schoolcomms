from django.contrib import admin
from .models import Grade, ClassRoom, Student, Entry

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("id","name","year")
    search_fields = ("name",) 

@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("id","grade","name","homeroom_teacher")
    autocomplete_fields = ("grade","homeroom_teacher",)
    search_fields = ("name",) 

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("id","student_no","user","class_room")
    search_fields = ("student_no","user__username","user__first_name","user__last_name")
    autocomplete_fields = ("user","class_room",)

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("id","student","target_date","status","read_by","read_at","created_at")
    list_filter = ("status","target_date","student__class_room")
    search_fields = ("student__user__username","student__student_no")