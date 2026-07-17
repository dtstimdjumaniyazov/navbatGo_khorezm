import re

import markdown as md
from django.conf import settings
from django.urls import reverse
from django.views.generic import TemplateView

LEGAL_DIR = settings.BASE_DIR / "docs" / "legal"

# [текст в квадратных скобках] — реквизиты-плейсхолдеры для юриста,
# подсвечиваем жёлтым, как раньше в ручной вёрстке. Ограничение длины — на
# случай переноса строки внутри плейсхолдера в исходном markdown, но чтобы
# не поймать случайный «[» и «]» в разных местах документа.
_PLACEHOLDER_RE = re.compile(r"\[([^\]]{1,120})\]")


def _render_legal_markdown(filename: str) -> str:
    text = (LEGAL_DIR / filename).read_text(encoding="utf-8")
    html = md.markdown(text, extensions=["tables"])
    return _PLACEHOLDER_RE.sub(r'<span class="placeholder">[\1]</span>', html)


class LegalDocView(TemplateView):
    """
    Общий рендер публичных юридических страниц из markdown-черновиков в
    docs/legal/ — один файл-источник и для юриста, и для сайта, вместо
    дублирования текста в вёрстке на двух языках.
    """

    template_name = "legal/document.html"
    md_ru: str = ""
    md_uz: str = ""
    url_ru: str = ""
    url_uz: str = ""
    title_ru: str = ""
    title_uz: str = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lang = self.kwargs.get("lang", "ru")
        filename = self.md_uz if lang == "uz" else self.md_ru
        ctx["body"] = _render_legal_markdown(filename)
        ctx["switch_url"] = reverse(self.url_uz) if lang == "ru" else reverse(self.url_ru)
        ctx["switch_label"] = "ЎЗ" if lang == "ru" else "RU"
        ctx["page_lang"] = lang
        ctx["page_title"] = self.title_uz if lang == "uz" else self.title_ru
        return ctx


class PrivacyPolicyView(LegalDocView):
    """Публичная страница политики конфиденциальности — ссылка из бота/веба/мобилки."""

    md_ru = "privacy-policy.md"
    md_uz = "privacy-policy.uz.md"
    url_ru = "legal-privacy"
    url_uz = "legal-privacy-uz"
    title_ru = "Политика конфиденциальности — NavbatGo"
    title_uz = "Махфийлик сиёсати — NavbatGo"


class OfertaView(LegalDocView):
    """Публичная страница оферты (правил пользования сервисом)."""

    md_ru = "oferta.md"
    md_uz = "oferta.uz.md"
    url_ru = "legal-oferta"
    url_uz = "legal-oferta-uz"
    title_ru = "Публичная оферта — NavbatGo"
    title_uz = "Оммавий оферта — NavbatGo"


class DeleteAccountView(LegalDocView):
    """Публичная страница запроса удаления аккаунта — обязательное требование Google Play."""

    md_ru = "delete-account.md"
    md_uz = "delete-account.uz.md"
    url_ru = "legal-delete-account"
    url_uz = "legal-delete-account-uz"
    title_ru = "Удаление аккаунта — NavbatGo"
    title_uz = "Hisobni o'chirish — NavbatGo"
