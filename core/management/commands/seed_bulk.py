# 本番環境用データの投入
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from faker import Faker
from core.models import Grade, ClassRoom, Student

class Command(BaseCommand):
    help = "Seed bulk data: 3 学年 x 3 クラス x 生徒 30 名  = 270"

    def add_arguments(self, parser):
        parser.add_argument("--grades", type=int, default=3)
        parser.add_argument("--classes", type=int, default=3)
        parser.add_argument("--students", type=int, default=30)
        parser.add_argument("--prefix", type=str, default="demo")  # ユーザー名接頭
        parser.add_argument("--seed", type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **opts):
        fake = Faker("ja_JP")
        Faker.seed(opts["seed"])

        # groups
        for g in ["ADMIN", "TEACHER", "STUDENT"]:
            Group.objects.get_or_create(name=g)

        # 既存消さない運用にしたい場合は↑でget_or_createを多用
        # 必要に応じて一掃するならここで .all().delete() を明示

        # 学年
        grades = []
        for gy in range(1, opts["grades"] + 1):
            grade, _ = Grade.objects.get_or_create(name=f"{gy}年", year=gy)
            grades.append(grade)

        # 学年ごとにクラスと先生・生徒を作成
        for grade in grades:
            for c in range(1, opts["classes"] + 1):
                # 先生
                t_username = f"{opts['prefix']}_t_{grade.year}{c:02d}"
                teacher, _ = User.objects.get_or_create(username=t_username, defaults={
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "email": f"{t_username}@example.com",
                })
                teacher.set_password("pass1234")
                teacher.save()
                teacher.groups.add(Group.objects.get(name="TEACHER"))

                # クラス
                room, _ = ClassRoom.objects.get_or_create(
                    name=f"{grade.year}年{c}組",
                    grade=grade,
                    defaults={"homeroom_teacher": teacher},
                )

                # 生徒30人
                for no in range(1, opts["students"] + 1):
                    s_username = f"{opts['prefix']}_s_{grade.year}{c:02d}{no:02d}"
                    stu_user, _ = User.objects.get_or_create(username=s_username, defaults={
                        "first_name": fake.first_name(),
                        "last_name": fake.last_name(),
                        "email": f"{s_username}@example.com",
                    })
                    stu_user.set_password("pass1234")
                    stu_user.save()
                    stu_user.groups.add(Group.objects.get(name="STUDENT"))

                    Student.objects.get_or_create(
                        user=stu_user,
                        class_room=room,
                        defaults={"student_no": str(no)}
                    )

        self.stdout.write(self.style.SUCCESS("Seeded bulk data successfully."))
