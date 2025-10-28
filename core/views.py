from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.db import models
from django.db.models import Q
from django.db.models.functions import Concat
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

        # 数値化 + 1..5 に丸め（不正値はデフォルト3に）
        def _to_scale(v):
            try:
                n = int(v)
                return n if 1 <= n <= 5 else 3
            except (TypeError, ValueError):
                return 3

        condition = _to_scale(request.POST.get("condition"))
        mental    = _to_scale(request.POST.get("mental"))

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
                    entry.condition = condition
                    entry.mental    = mental
                    fields = ["content", "condition", "mental"]
                    # statusを併用しているなら未読＝提出済みに同期しておく
                    if hasattr(Entry, "Status"):
                        entry.status = Entry.Status.SUBMITTED
                        fields.append("status")
                    entry.save(update_fields=fields)
                    messages.success(request, "提出を更新しました。")
            else:
                # まだ当日（前登校日）分が無ければ新規作成
                kwargs = dict(student=student, 
                              target_date=tdate, 
                              content=content,
                              condition=condition,
                              mental=mental,
                              )
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
        "SHOW_HOME_LINK": True,
        "HOME_URL": reverse("student_entries"),
        "HOME_LABEL": "連絡帳履歴に移動",
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
    # 先生（担任）以外は利用不可
    if not is_in(request.user, "TEACHER"):
        return HttpResponseForbidden("担任のみ利用可")

    # 担任に紐づくクラスの生徒のみ、本日提出分（前日の連絡帳）を表示する
    classes = ClassRoom.objects.filter(homeroom_teacher=request.user)
    tdate = calc_prev_schoolday()  # 例：月曜アクセス→金曜

    students = Student.objects.filter(class_room__in=classes) \
                              .select_related("user", "class_room")

    entries_today = Entry.objects.filter(student__in=students, target_date=tdate) \
                                 .select_related("student", "student__user", "student__class_room")

    # entries_today の各エントリ(e)をキー化して提出/未提出の生徒を判定
    # by_student = {e.student_id: e for e in entries_today}
    # not_submitted = [s for s in students if s.id not in by_student]
    by_student = {e.student_id: e for e in entries_today}
    not_submitted = [s for s in students if s.id not in by_student]

    # 履歴ベースのクエリセット
    history = Entry.objects.filter(student__in=students) \
                           .select_related("student", "student__user", "student__class_room")

    # テンプレートから渡された検索キーワード(q)をもとに、
    # 入力内容・ユーザーID・氏名・生徒番号のいずれかに部分一致する履歴を絞り込み
    q = (request.GET.get("q") or "").strip()
    if q:
        history = history.filter(
            Q(content__icontains=q) |
            Q(student__user__username__icontains=q) |
            Q(student__user__first_name__icontains=q) |
            Q(student__user__last_name__icontains=q) |
            Q(student__student_no__icontains=q)
        )

    # 生徒タイムライン（sid）の構築
    sid_raw = request.GET.get("sid")
    try:
        sid = int(sid_raw) if sid_raw is not None else None
    except (TypeError, ValueError):
        sid = None

    selected_student = None # 変数定義と初期化

    if sid and students.filter(id=sid).exists():
        history = history.filter(student_id=sid)
        # 表示用に対象生徒を取得
        selected_student = students.select_related("user").get(id=sid)

    # 並び安定化 → スライス
    history = history.order_by("-target_date", "-id")[:200]

    return render(request, "teacher_dashboard.html", {
        "tdate": tdate,
        "entries_today": entries_today,
        "not_submitted": not_submitted,
        "history": history,
        "selected_student": selected_student,
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