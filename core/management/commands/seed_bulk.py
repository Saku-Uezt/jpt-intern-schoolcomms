# 本番環境用データの投入（Fakerを使ってランダムな氏名データを持った教師・生徒ユーザーとクラスを生成する）
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from django.db import transaction
from core.models import Grade, ClassRoom, Student

class Command(BaseCommand):
    help = "Seed bulk data: grades x classes x students（例: 3 x 3 x 30 = 270生徒）"

    def add_arguments(self, parser):
        parser.add_argument("--grades", type=int, default=3)
        parser.add_argument("--classes", type=int, default=3)
        parser.add_argument("--students", type=int, default=30)
        parser.add_argument("--prefix", type=str, default="demo")  # ユーザー名接頭語
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--purge", action="store_true",
                            help="既存データを初期化してから投入する")

    @transaction.atomic
    def handle(self, *args, **opts):
        # Faker は投入時のみ読み込み（本番通常起動へ影響させない）
        try:
            from faker import Faker
        except Exception as e:
            raise CommandError("Faker が見つかりません。requirements に追加してください。") from e

        fake = Faker("ja_JP")
        Faker.seed(opts["seed"])

        # 既存消去（必要なら）
        if opts["purge"]:
            # 順序はモデル依存で調整
            Student.objects.all().delete()
            ClassRoom.objects.all().delete()
            Grade.objects.all().delete()
            # ユーザは prefix で絞って消すと安全
            User.objects.filter(username__startswith=f"{opts['prefix']}_").delete()

        # groups（先に作ってキャッシュ）
        for g in ["ADMIN", "TEACHER", "STUDENT"]:
            Group.objects.get_or_create(name=g)
        g_teacher = Group.objects.get(name="TEACHER")
        g_student = Group.objects.get(name="STUDENT")

        # 学年
        grades = []
        for gy in range(1, opts["grades"] + 1):
            grade, _ = Grade.objects.get_or_create(name=f"{gy}年", defaults={"year": gy})
            grades.append(grade)

        # 学年ごとにクラスと教師・生徒
        for grade in grades:
            # 教師の生成
            for c in range(1, opts["classes"] + 1):
                t_username = f"{opts['prefix']}_t_{grade.year}{c:02d}"
                teacher, created = User.objects.get_or_create(
                    username=t_username,
                    defaults={
                        "first_name": fake.first_name(),
                        "last_name": fake.last_name(),
                        "email": f"{t_username}@example.com",
                    },
                )
                if created:
                    teacher.set_password("pass1234")
                    teacher.save()
                    teacher.groups.add(g_teacher)
                # クラスの生成
                room, _ = ClassRoom.objects.get_or_create(
                    name=f"{c}組",
                    grade=grade,
                    defaults={"homeroom_teacher": teacher},
                )
                # 生徒ユーザーの生成
                for no in range(1, opts["students"] + 1):
                    s_username = f"{opts['prefix']}_s_{grade.year}{c:02d}{no:02d}"
                    stu_user, s_created = User.objects.get_or_create(
                        username=s_username,
                        defaults={
                            "first_name": fake.first_name(),
                            "last_name": fake.last_name(),
                            "email": f"{s_username}@example.com",
                        },
                    )
                    if s_created:
                        stu_user.set_password("pass1234")
                        stu_user.save()
                        stu_user.groups.add(g_student)

                    Student.objects.get_or_create(
                        user=stu_user,
                        class_room=room,
                        defaults={"student_no": str(no)},
                    )

        self.stdout.write(self.style.SUCCESS("Seeded bulk data successfully."))
