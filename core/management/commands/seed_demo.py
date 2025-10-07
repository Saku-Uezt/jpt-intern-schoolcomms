# サンプルデータの投入
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from core.models import Grade, ClassRoom, Student

class Command(BaseCommand):
    help = "Demo data (groups, users, class, students)"

    def handle(self, *args, **kwargs):
        for g in ["ADMIN","TEACHER","STUDENT"]:
            Group.objects.get_or_create(name=g)

        admin = User.objects.filter(username="admin").first() or User.objects.create_superuser(
            username="admin", email="", password="adminpass")
        teacher = User.objects.filter(username="teacher1").first() or User.objects.create_user(
            username="teacher1", password="teacherpass", first_name="太郎", last_name="担任")
        s1u = User.objects.filter(username="stu01").first() or User.objects.create_user(
            username="stu01", password="stupass", first_name="花子", last_name="生徒")
        s2u = User.objects.filter(username="stu02").first() or User.objects.create_user(
            username="stu02", password="stupass", first_name="次郎", last_name="生徒")

        teacher.groups.add(Group.objects.get(name="TEACHER"))
        s1u.groups.add(Group.objects.get(name="STUDENT"))
        s2u.groups.add(Group.objects.get(name="STUDENT"))
        admin.groups.add(Group.objects.get(name="ADMIN"))

        g1 = Grade.objects.filter(name="1年").first() or Grade.objects.create(name="1年", year=2025)
        c1 = ClassRoom.objects.filter(name="1組", grade=g1).first() or ClassRoom.objects.create(
            grade=g1, name="1組", homeroom_teacher=teacher)

        Student.objects.get_or_create(user=s1u, defaults={"class_room": c1, "student_no":"1"})
        Student.objects.get_or_create(user=s2u, defaults={"class_room": c1, "student_no":"2"})

        self.stdout.write(self.style.SUCCESS("Demo seeded."))
        self.stdout.write("ログイン情報:")
        self.stdout.write("  管理者: admin / adminpass")
        self.stdout.write("  担任  : teacher1 / teacherpass")
        self.stdout.write("  生徒  : stu01 / stupass  / stu02 / stupass")
