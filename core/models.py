#モデルクラス（DB定義、学年、クラス、生徒）

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    read_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="read_entries")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "target_date")  # 同日二重提出を防止

    def lock_as_read(self, teacher: User):
        # idempotent（2回押されても安全）
        if self.read_at:
            return
        self.read_by = teacher
        self.read_at = timezone.now()
        self.save(update_fields=["read_by", "read_at"])

    @property
    def is_read(self) -> bool:
        return bool(self.read_at)
