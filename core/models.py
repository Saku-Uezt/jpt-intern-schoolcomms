#モデルクラス（学年、クラス、生徒の定義）

from django.db import models
from django.contrib.auth.models import User

class Grade(models.Model):
    name = models.CharField(max_length=20)  # 1年,2年...
    year = models.IntegerField()            # 西暦や学年コードなど任意
    def __str__(self): return f"{self.name}"

class ClassRoom(models.Model):
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT)
    name = models.CharField(max_length=20)  # 1組,2組...
    homeroom_teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name="homeroom_classes")
    def __str__(self): return f"{self.grade}-{self.name}"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    class_room = models.ForeignKey(ClassRoom, on_delete=models.PROTECT)
    student_no = models.CharField(max_length=20)
    def __str__(self): return f"{self.student_no}:{self.user.get_full_name() or self.user.username}"

class Entry(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "提出済み"
        READ = "READ", "既読"

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    target_date = models.DateField()
    content = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUBMITTED)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="read_entries")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "target_date")  # 同日二重提出を防止

    def lock_as_read(self, teacher_user):
        if self.status == self.Status.READ:
            return
        from django.utils import timezone
        self.status = self.Status.READ
        self.read_by = teacher_user
        self.read_at = timezone.now()
        self.save()