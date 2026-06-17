"""Email digest via Gmail SMTP.

Sends an HTML summary of the day's drafts to NOTIFICATION_EMAIL using a
Gmail App Password over SSL. Rendering is decoupled from sending so the
template can be tested without credentials.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import settings
from ..generator.brand import POST_FORMATS

log = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "jinja"]),
)

_FORMAT_LABELS = {
    "punchy_take": "Punchy Take",
    "explainer": "Explainer",
    "psa_alert": "Public Safety Alert",
    "thought_leadership": "Thought Leadership",
    "myth_bust": "Myth-Bust",
}


def _post_view(post) -> dict:
    body = post.body or ""
    preview = body.replace("\n", " ").strip()
    preview = preview[:180] + ("…" if len(preview) > 180 else "")
    return {
        "headline": post.headline,
        "preview": preview,
        "format_label": _FORMAT_LABELS.get(post.format_type, post.format_type.title()),
        "source_name": post.source_name or "",
        "image_url": post.image_url,
        "image_recommended": post.image_recommended,
        "is_pivotal": post.is_pivotal,
    }


def render_digest(posts, run_date: str | None = None) -> str:
    run_date = run_date or datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    template = _env.get_template("digest.html.jinja")
    return template.render(
        posts=[_post_view(p) for p in posts],
        run_date=run_date,
        editor_url=settings.frontend_url,
    )


def send_digest(posts, subject: str | None = None) -> bool:
    """Render and send the digest. Returns False (and logs) if not configured."""
    html = render_digest(posts)
    if not settings.has_email:
        log.warning("Email not configured (GMAIL_ADDRESS/APP_PASSWORD missing) — "
                    "skipping send. Digest rendered but not delivered.")
        return False

    subject = subject or f"QuantrixLabs · {len(posts)} LinkedIn drafts ready"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.gmail_address
    msg["To"] = settings.notification_email
    msg.attach(MIMEText("Open the editor to review today's drafts.", "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                              context=context, timeout=30) as server:
            server.login(settings.gmail_address, settings.gmail_app_password)
            server.sendmail(settings.gmail_address,
                            [settings.notification_email], msg.as_string())
        log.info("Digest sent to %s", settings.notification_email)
        return True
    except Exception as exc:  # pragma: no cover - network/credential variance
        log.error("Failed to send digest: %s", exc)
        return False
