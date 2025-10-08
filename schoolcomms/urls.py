from django.contrib import admin
from django.urls import path,include
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    # 既存のトップ画面
    path("", views.home, name="home"),  
    # ログイン後のルート振り分け
    path("route/", views.route_after_login, name="route_after_login"),
    
    # 生徒の画面
    path("student/entry/new/", views.student_entry_new, name="student_entry_new"),
    path("student/entries/", views.student_entries, name="student_entries"),
    
    # 教師用の画面
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/entry/<int:entry_id>/read/", views.mark_read, name="mark_read"),
    
    # custom_login画面（/accounts/login/ を自作で処理、処理順の関係から標準ログイン画面より先の処理順で実装）
    path("accounts/login/", views.custom_login, name="login"),
    # ログイン画面
    path("accounts/", include("django.contrib.auth.urls")),
]