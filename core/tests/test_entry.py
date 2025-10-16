from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import  Grade, ClassRoom, Student, Entry, calc_prev_schoolday
from django.contrib.auth.models import Group, User


class EntryCleanTests(TestCase):
    # テストユーザーを定義（テストクラスではテスト用のDBをDjango内部で作って実行後に削除するのでDBの一意エラーなどは起きない）
    @classmethod
    def setUpTestData(cls):
        # グループ
        for g in ["ADMIN", "TEACHER", "STUDENT"]:
            Group.objects.get_or_create(name=g)

        # ユーザー
        cls.teacher = User.objects.create_user(username="teacher1", password="x")
        cls.teacher.groups.add(Group.objects.get(name="TEACHER"))

        cls.s1 = User.objects.create_user(username="stu01", password="x")
        cls.s1.groups.add(Group.objects.get(name="STUDENT"))

        # 学年・クラス・生徒
        g1 = Grade.objects.create(name="1年", year=2025)
        c1 = ClassRoom.objects.create(name="1組", grade=g1, homeroom_teacher=cls.teacher)
        cls.student = Student.objects.create(user=cls.s1, class_room=c1, student_no="1")

    # 既読状態の際に編集をしようとするとバリデーションエラーをサーバー側で返却するテスト
    def test_read_entry_cannot_be_edited(self):
        # 前登校日を呼び出し
        tdate = calc_prev_schoolday()
        e = Entry.objects.create(student=self.student, target_date=tdate, content="ok")
        e.lock_as_read(teacher=self.teacher)  
        e.content = "edit"
        # バリデーションエラー、エラーメッセージ出力確認（assertRaisesMessageメソッドを使用してチェック）
        with self.assertRaisesMessage(ValidationError, "既読済みの記録は編集できません"):
            # Djangoのfull_clean()はフィールド型検証→clean_fields()→clean()の順で実行される。
            # モデル内の業務ルール（既読編集不可など）もこの処理内で検証される。
            e.full_clean()

    # 未読状態の際に編集可能状態を返却するテスト
    def test_unread_entry_can_be_edited(self):
        tdate = calc_prev_schoolday() 
        e = Entry.objects.create(student=self.student, target_date=tdate, content="ok") 
        e.content = "edit ok"
        e.full_clean()