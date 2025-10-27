#モデルクラス（DB定義、学年、クラス、生徒）

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
from django.core.exceptions import ValidationError
import jpholiday
import unicodedata

# 学年登録クラス
class Grade(models.Model):
    name = models.CharField(max_length=20)  # 1年,2年...
    year = models.IntegerField(unique=True) # 西暦や学年コードなど任意（ただし一意）
    def __str__(self):
        return f"{self.name}"
    
# 学級クラス登録クラス
class ClassRoom(models.Model):
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT)
    name = models.CharField(max_length=20)  # 1年1組,1年2組...（自由記述）
    homeroom_teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name="homeroom_classes")

    def clean(self):
        # 正規化（空白などを削除する処理）をここで反映
        if self.name:
            self.name = unicodedata.normalize('NFKC', self.name).strip()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['grade', 'name'], name='ux_core_classroom_grade_name')  # grade と name の複合ユニーク（同一学年内でクラス名重複を禁止）
        ]
    
    def __str__(self):
        # 例: "3年 3組" のように読みやすく
        return f"{self.grade} {self.name}"


# 生徒登録クラス
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    class_room = models.ForeignKey(ClassRoom, on_delete=models.PROTECT)
    student_no = models.CharField(max_length=20)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['class_room', 'student_no'], ## class_room と student_no の複合ユニーク（同一クラス内の生徒番号の重複を禁止）
                name='ux_core_student_class_no'
            )
        ]
    def __str__(self):
        # 例: "3年 3組 1番 ○○（氏名）"
        return f"{self.class_room} {self.student_no}番 {self.user.last_name}{self.user.first_name}"

# 祝日判定メソッド（weekdayメソッドでは月曜を0、火曜を1…と定義）※課題2要素
def calc_prev_schoolday(base_date=None):
    d = base_date or timezone.localdate()
    d -= timedelta(days=1)
    # 土日(weekday >= 5) または 祝日(jpholiday) の場合はさらに1日前へ
    while d.weekday() >= 5 or jpholiday.is_holiday(d):
        d -= timedelta(days=1)
    return d

# 連絡帳登録クラス
class Entry(models.Model):
    # 既読/未読
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "未読（提出済み）"
        READ = "READ", "既読"
    
    # 体調
    class HealthScale(models.IntegerChoices):
        VERY_BAD = 1, "とてもわるい"
        BAD      = 2, "わるい"
        NORMAL   = 3, "ふつう"
        GOOD     = 4, "よい"
        GREAT    = 5, "とてもよい"

    # メンタル
    class MentalScale(models.IntegerChoices):
        VERY_LOW  = 1, "とても落ち込み気味"
        LOW       = 2, "やや不調"
        NORMAL    = 3, "ふつう"
        HIGH      = 4, "やや前向き"
        VERY_HIGH = 5, "とても前向き"

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    target_date = models.DateField()
    content = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUBMITTED)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="read_entries")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    condition = models.PositiveSmallIntegerField(
        choices=HealthScale.choices,
        default=HealthScale.NORMAL,
        verbose_name="体調"
    )
    mental = models.PositiveSmallIntegerField(
        choices=MentalScale.choices,
        default=MentalScale.NORMAL,
        verbose_name="メンタル"
    )

    class Meta:
        verbose_name_plural = "Entries" #Djangoが命名したスペルミスを修正
        ordering = ["-target_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "target_date"],
                name="core_entry_student_date_uniq",
            ),
            models.CheckConstraint(
                check=models.Q(condition__gte=1) & models.Q(condition__lte=5),
                name="core_entry_condition_range",
            ),
            models.CheckConstraint(
                check=models.Q(mental__gte=1) & models.Q(mental__lte=5),
                name="core_entry_mental_range",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "-target_date"], name="idx_entry_stu_date_desc"),
            models.Index(fields=["read_by"], name="idx_entry_read_by"),
        ]

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
        """管理者が既読を取り消す処理（課題2改善要素）"""
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

        # 既読済みデータは内容更新不可（サーバー側でDBの書き換えを制御、セキュアな実装を目的）
        if self.pk and self.is_read:
            raise ValidationError("既読済みの記録は編集できません。")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __str__(self):
        """
        表示例:
        3年3組 1番 demo_s_10101 - 2025-10-24
        """
        student = self.student
        return f"{student.class_room} {student.student_no}番 {student.user.username} - {self.target_date}"
