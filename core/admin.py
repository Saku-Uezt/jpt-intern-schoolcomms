#モデルクラス（管理者画面でのDB更新）

from django.contrib import admin, messages
from .models import Grade, ClassRoom, Student, Entry
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.contrib.admin.utils import unquote
from django.db.models.functions import Cast
from django.db.models import IntegerField

# 学年項目のDB編集処理
@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("id","name","year")
    search_fields = ("name",) 

# 学級項目のDB編集処理
@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("id","grade","name","homeroom_teacher")
    autocomplete_fields = ("grade","homeroom_teacher",)
    search_fields = ("name",) 

# 生徒項目のDB編集処理
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("id","student_no","user","class_room")
    search_fields = ("student_no","user__username","user__first_name","user__last_name")
    autocomplete_fields = ("user","class_room",)
 
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            student_no_int=Cast("student_no", IntegerField())
        )
        # Cast結果で強制的に並べ替え
        return qs.order_by("class_room_id", "student_no_int", "id")


# 連絡帳データ項目のDB編集処理
@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("student","target_date","is_read","read_by","read_at","status")
    list_filter = ("status","target_date","student__class_room")
    search_fields = ("student__user__username","student__student_no","content",)
    readonly_fields = ("status","read_by","read_at")
    change_form_template = "admin/core/entry/change_form.html"

    # 連絡帳データを未提出に戻してデータを削除する処理
    @admin.action(description="未提出に戻す（選択した提出データを削除）")
    def revert_to_unsubmitted(modeladmin, request, queryset):
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"{count}件を未提出に戻しました。")
    
    # 連絡帳データを未読に戻してデータを更新する処理
    @admin.action(description="未読に戻す（既読を解除）")
    def revert_to_unread(self, request, queryset):
        count = queryset.update(read_at=None, read_by=None,status=Entry.Status.SUBMITTED,)
        self.message_user(request, f"{count}件を未読に戻しました。", level=messages.SUCCESS)

    # 連絡帳データを既読に戻してデータを更新する処理
    @admin.action(description="既読にする")
    def mark_as_read(self, request, queryset):
        count = queryset.update(read_at=timezone.now(), read_by=request.user, status=Entry.Status.READ,)
        self.message_user(request, f"{count}件を既読にしました。", level=messages.SUCCESS)

    # 既読→未読にするための処理メソッド
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == "POST" and "_unread" in request.POST:
            obj = self.get_object(request, unquote(object_id))
            Entry.objects.filter(pk=obj.pk).update(
                status=Entry.Status.SUBMITTED,
                read_at=None,
                read_by=None,
            )
            self.message_user(request, "既読を未読に戻しました。")
            return HttpResponseRedirect(request.path)
        return super().changeform_view(request, object_id, form_url, extra_context)

    # 変更処理のレスポンス処理
    def response_change(self, request, obj):
        return super().response_change(request, obj)

    actions = ["mark_as_read", "revert_to_unread"]