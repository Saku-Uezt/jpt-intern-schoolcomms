from django.urls import reverse

def home_link(request):
    user = request.user
    url = reverse("home")  # デフォルト（未ログイン時など）

    if user.is_authenticated:
        if user.is_superuser or user.groups.filter(name__in=["ADMIN"]).exists():
            url = "/admin/"
        elif user.groups.filter(name="TEACHER").exists():
            url = reverse("teacher_dashboard")
        elif user.groups.filter(name="STUDENT").exists():
            # 提出画面にいると“リロード”に見えるので、ホームは履歴へ寄せる
            url = reverse("student_entries")

    # 今いるURLと同じならリンクを隠す
    show = (request.path != url)
    return {"HOME_URL": url, "SHOW_HOME_LINK": show}