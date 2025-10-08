from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.db.models import Q
from .models import Student, Entry, ClassRoom
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST

def is_in(user, group_name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=group_name).exists()

def prev_school_day(d: date) -> date:
    return d - timedelta(days=3) if d.weekday() == 0 else d - timedelta(days=1)

def home(request):
    return render(request, "home.html")

# 標準のログイン画面（使用しないため念のためコメントアウト）
# def login_view(request):
#     if request.method == "POST":
#         u = authenticate(request, username=request.POST["username"], password=request.POST["password"])
#         if u:
#             login(request, u); return redirect("home")
#     return render(request, "login.html")


# 拡張版ログイン画面（認証時ロールに合わせてリダイレクト）
def custom_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # 一元ルートへ集約
            return redirect("route_after_login")
    else:
        form = AuthenticationForm()
    return render(request, "registration/login.html", {"form": form})

def logout_view(request):
    logout(request); return redirect("login")

# 権限によるリダイレクト処理
@login_required
def route_after_login(request):
    user = request.user
    # 管理者権限の場合（現状ダッシュボード未実装なのでDjangoのadminサイトへ）
    if user.is_superuser or is_in(user, "ADMIN"):
        return redirect("/admin/")  # 'admin_dashboard' を実装後差し替え
    # 権限が先生の場合
    if is_in(user, "TEACHER"):
        return redirect("teacher_dashboard")
    # 権限が生徒の場合
    elif is_in(user, "STUDENT"):
        # 生徒は “提出 or 履歴” のどちらでもOK。既存導線に合わせて片方に寄せる
        return redirect("student_entries")  
    # どこも通らない場合（未所属など）はフォールバック
    return redirect("home")

@login_required
def student_entry_new(request):
    if not is_in(request.user, "STUDENT"):
        return HttpResponseForbidden("学生のみ利用可")
    # 自分の Student レコード取得
    student = get_object_or_404(Student, user=request.user)
    target = prev_school_day(date.today())
    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        Entry.objects.get_or_create(
            student=student, target_date=target, defaults={"content": content}
        )
        return redirect("student_entries")
    # 既に提出済みか表示用に確認
    exists = Entry.objects.filter(student=student, target_date=target).exists()
    return render(request, "student_entry_new.html", {"tdate": target, "exists": exists})

@login_required
def student_entries(request):
    if not is_in(request.user, "STUDENT"):
        return HttpResponseForbidden("学生のみ利用可")
    student = get_object_or_404(Student, user=request.user)
    entries = Entry.objects.filter(student=student).order_by("-target_date")
    return render(request, "student_entries.html", {"entries": entries})

@login_required
def teacher_dashboard(request):
    if not is_in(request.user, "TEACHER"):
        return HttpResponseForbidden("担任のみ利用可")
    classes = ClassRoom.objects.filter(homeroom_teacher=request.user)
    tdate = prev_school_day(date.today())
    students = Student.objects.filter(class_room__in=classes).select_related("user","class_room")
    entries_today = Entry.objects.filter(student__in=students, target_date=tdate).select_related("student")
    by_student = {e.student_id: e for e in entries_today}
    not_submitted = [s for s in students if s.id not in by_student]
    q = request.GET.get("q")
    history = Entry.objects.filter(student__in=students).order_by("-target_date")
    if q:
        history = history.filter(Q(content__icontains=q) | Q(student__user__username__icontains=q))
    return render(request, "teacher_dashboard.html", {
        "tdate": tdate, "entries_today": entries_today, "not_submitted": not_submitted,
        "history": history[:200],
    })

@login_required
@require_POST
def mark_read(request, entry_id: int):
    if not is_in(request.user, "TEACHER"):
        return HttpResponseForbidden("担任のみ利用可")
    entry = get_object_or_404(Entry, pk=entry_id)
    if entry.student.class_room.homeroom_teacher != request.user:
        return HttpResponseForbidden("担当外の生徒です")
    entry.lock_as_read(request.user)
    return redirect("teacher_dashboard")