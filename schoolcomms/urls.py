from django.contrib import admin
from django.urls import path,include
from core import views
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def health(_):
    return HttpResponse("ok", content_type="text/plain", status=200)

urlpatterns = [
    path("admin/", admin.site.urls),
    # トップは“実体ビュー”を返す（ここでリダイレクトしない）
    path("", views.custom_login, name="index"),  # あるいは固定の home 画面ビュー
    # ログイン後の振り分け（LOGIN_REDIRECT_URL="home" がここを指す）
    path("route/", views.route_after_login, name="home"),
    
    # 生徒の画面
    path("student/entry/new/", views.student_entry_new, name="student_entry_new"),
    path("student/entries/", views.student_entries, name="student_entries"),
    
    # 教師用の画面
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/entry/<int:entry_id>/read/", views.mark_read, name="mark_read"),
    
    # custom_login画面（/accounts/login/ を自作で処理、処理順の関係から標準ログイン画面より先の処理順で実装）
    path("accounts/login/", views.custom_login, name="custom_login"),
    # ログイン画面
    path("accounts/", include("django.contrib.auth.urls")),

    # ✅ 最後に一時的な確認用ルートを追加
    path("check/", lambda request: HttpResponse("OK", content_type="text/plain")),
]