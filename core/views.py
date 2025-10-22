from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib import messages
from django.urls import reverse
from .models import Student, Entry, ClassRoom
from .models import calc_prev_schoolday
import logging

def is_in(user, group_name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=group_name).exists()

def prev_school_day(d: date) -> date:
    #前登校日を返す（週明け月曜は金曜に戻す）
    return d - timedelta(days=3) if d.weekday() == 0 else d - timedelta(days=1)


# 標準のログイン画面（使用しないため念のためコメントアウト）
# def login_view(request):
#     if request.method == "POST":
#         u = authenticate(request, username=request.POST["username"], password=request.POST["password"])
#         if u:
#             login(request, u); return redirect("home")
#     return render(request, "login.html")

#エラー時のロガーを定義
logger = logging.getLogger(__name__)

# 拡張版ログイン画面（認証時ロールに合わせてリダイレクト）
def custom_login(request):
    logger.info("custom_login %s %s", request.method, request.path)
    try:
        if request.method == "POST":
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                # 一元ルートへ集約
                return redirect("home")
            else:
                logger.warning("Login form invalid: %s", form.errors)
        else:
            form = AuthenticationForm()

        # GET やエラー時もここで描画
        return render(request, "registration/login.html", {"form": form}) 
    
    # 本番環境時のExceptionのロギング処理
    except Exception as e:
        # ここで例外の詳細とスタックトレースをログに出す
        logger.exception("custom_login failed: %s", str(e))
        # Django が500を返すように再送出
        raise

def logout_view(request):
    logout(request); return redirect("login")

# 権限によるリダイレクト処理
@login_required
def route_after_login(request):
    user = request.user

    # 管理者 or 管理権限グループ
    if user.is_superuser or is_in(user, "ADMIN"):
        # Django標準のユーザー管理画面へリダイレクト（時間があればダッシュボードを作成予定）
        return redirect("/admin/")
    # 権限が先生の場合
    if is_in(user, "TEACHER"):
        # 先生ダッシュボード画面にリダイレクト処理
        return redirect("teacher_dashboard")
    # 権限が生徒の場合
    elif is_in(user, "STUDENT"):
        # 生徒の連絡帳画面へリダイレクト
        return redirect("student_entry_new")
    # 権限が付与されていないユーザーの場合
    return HttpResponseForbidden("権限がありません")

@login_required
def student_entry_new(request):
    if not is_in(request.user, "STUDENT"):
        return HttpResponseForbidden("学生のみ利用可")

    student = get_object_or_404(Student, user=request.user)
    tdate = calc_prev_schoolday()  

    if request.method == "POST":
        content = (request.POST.get("content") or "").strip()

        # 競合対策：最新状態でロックして取得（管理画面の操作と衝突しにくくする）
        with transaction.atomic():
            entry = (Entry.objects
                     .select_for_update()
                     .filter(student=student, target_date=tdate)
                     .first())

            if entry:
                if entry.is_read:
                    # 既読なら編集不可
                    messages.info(request, "既読済みのため編集できません。")
                else:
                    # 未読（提出済）なら上書きOK
                    entry.content = content
                    # statusを併用しているなら未読＝提出済みに同期しておく
                    if hasattr(Entry, "Status"):
                        entry.status = Entry.Status.SUBMITTED
                    entry.save(update_fields=["content"] + (["status"] if hasattr(Entry, "Status") else []))
                    messages.success(request, "提出を更新しました。")
            else:
                # まだ当日（前登校日）分が無ければ新規作成
                kwargs = dict(student=student, target_date=tdate, content=content)
                if hasattr(Entry, "Status"):
                    kwargs["status"] = Entry.Status.SUBMITTED
                Entry.objects.create(**kwargs)
                messages.success(request, "提出しました。")

        # PRG（Post→Redirect→Get）：二重送信防止＆最新状態で再描画
        return redirect(reverse("student_entry_new"))

    # ---- GET表示 ----
    entry = Entry.objects.filter(student=student, target_date=tdate).first()
    can_edit = bool(entry and not entry.is_read)  # 未読なら再編集可

    return render(request, "student_entry_new.html", {
        "tdate": tdate,
        "entry": entry,
        "can_edit": can_edit,
    })

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
    tdate = calc_prev_schoolday()

    students = Student.objects.filter(class_room__in=classes).select_related("user","class_room")
    entries_today = (Entry.objects.filter(student__in=students, target_date=tdate)
                     .select_related("student","student__user","student__class_room"))

    by_student = {e.student_id: e for e in entries_today}
    not_submitted = [s for s in students if s.id not in by_student]

    history = (Entry.objects.filter(student__in=students)
               .select_related("student","student__user","student__class_room")
               .order_by("-target_date"))

    q = request.GET.get("q")
    if q:
        history = history.filter(
            Q(content__icontains=q) |
            Q(student__user__username__icontains=q) |
            Q(student__user__first_name__icontains=q) |
            Q(student__user__last_name__icontains=q) |
            Q(student__student_no__icontains=q)
        )

    return render(request, "teacher_dashboard.html", {
        "tdate": tdate,
        "entries_today": entries_today,
        "not_submitted": not_submitted,
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