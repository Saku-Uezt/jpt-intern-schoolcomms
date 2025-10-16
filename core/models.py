#モデルクラス（DB定義、学年、クラス、生徒）

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
from django.core.exceptions import ValidationError
import jpholiday

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

# 祝日判定メソッド（weekdayメソッドでは月曜を0、火曜を1…と定義）
def calc_prev_schoolday(base_date=None):
    d = base_date or timezone.localdate()
    d -= timedelta(days=1)
    # 土日(weekday >= 5) または 祝日(jpholiday) の場合はさらに1日前へ
    while d.weekday() >= 5 or jpholiday.is_holiday(d):
        d -= timedelta(days=1)
    return d

class Entry(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "未読（提出済み）"
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
        ordering = ["-target_date"]

    # ---------- 機能①：既読ロック ----------
    def lock_as_read(self, teacher: User):
        """担任が既読にする処理（レースコンディション防止）"""
        with transaction.atomic():
            updated = (
                Entry.objects.filter(pk=self.pk, read_at__isnull=True)
                .update(
                    read_by=teacher,
                    read_at=timezone.now(),
                    status=Entry.Status.READ,
                )
            )
            if updated:
                self.read_by = teacher
                self.read_at = timezone.now()
                self.status = Entry.Status.READ

    # ---------- 機能②：未読に戻す（課題2用） ----------
    def unlock_as_unread(self):
        """担任が既読を取り消す処理（課題2改善要素）"""
        with transaction.atomic():
            Entry.objects.filter(pk=self.pk).update(
                read_by=None, read_at=None, status=Entry.Status.SUBMITTED
            )
            self.read_by = None
            self.read_at = None
            self.status = Entry.Status.SUBMITTED

    # ---------- 機能③：前登校日バリデーション ----------
    def clean(self):
        """
        前登校日のデータしか登録できないようサーバー側で検証。
        長期休暇はPoCでは考慮不要。（祝日はPoC外だが追加実装として反映）
        """
        prev_schoolday = calc_prev_schoolday() 
        if self.target_date != prev_schoolday:
            raise ValidationError({"target_date": f"提出日は前登校日（{prev_schoolday}）のみ登録可能です。"})

        # 既読済みデータは内容更新不可
        if self.pk and self.is_read:
            raise ValidationError("既読済みの記録は編集できません。")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __str__(self):
        status_label = "✔" if self.is_read else "…"
        return f"{self.student} {self.target_date} [{status_label}]"

