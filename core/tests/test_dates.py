# quest_1/tests/test_dates.py
# 前登校日（休日スキップ）判定のアサーションテストクラス

from datetime import date
from django.test import TestCase
from core.models import calc_prev_schoolday  # core/modelsの対象defをテスト

class CalcPrevSchooldayTests(TestCase):
    """calc_prev_schoolday() の曜日判定テスト"""

    def test_prev_schoolday_on_saturday(self):
        """土曜は前の金曜になる"""
        result = calc_prev_schoolday(date(2025, 10, 11))  # 土曜日
        self.assertEqual(result, date(2025, 10, 10))      # 金曜日

    def test_prev_schoolday_on_sunday(self):
        """日曜は前の金曜になる"""
        result = calc_prev_schoolday(date(2025, 10, 12))  # 日曜日
        self.assertEqual(result, date(2025, 10, 10))      # 金曜日

    def test_prev_schoolday_on_monday(self):
        """月曜は前の金曜になる"""
        result = calc_prev_schoolday(date(2025, 10, 6))
        self.assertEqual(result, date(2025, 10, 3))

    def test_prev_schoolday_on_tuesday(self):
        """火曜は前日（月曜）"""
        result = calc_prev_schoolday(date(2025, 10, 7))
        self.assertEqual(result, date(2025, 10, 6))

    def test_prev_schoolday_on_tuesday_returns_friday(self):
        """月曜が祝日の場合、火曜は前の金曜になる"""
        result = calc_prev_schoolday(date(2025, 10, 14))
        self.assertEqual(result, date(2025, 10, 10))

    def test_prev_schoolday_on_beginning_year(self):
        """2026/1/2(火)の場合、前日は2025/12/31(金)になる"""
        result = calc_prev_schoolday(date(2026, 1, 2))
        self.assertEqual(result, date(2025, 12, 31))