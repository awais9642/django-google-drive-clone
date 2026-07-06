from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_share_email(self, shared_by_name, shared_with_email,
                     shared_with_name, item_type, item_name,
                     permission, access_link):
    """
    Sends a formatted HTML share notification email.

    Uses @shared_task so this task is discovered by Celery's autodiscover
    without needing to import the Celery app directly here.

    bind=True gives us access to `self` for retry logic.
    max_retries=3 with 60s delay means if Gmail is temporarily down,
    Celery retries up to 3 times before giving up — the share itself
    already happened (DB saved), only the email might be delayed.

    Args passed as primitives (not ORM objects) because Celery serializes
    task arguments to JSON. Passing a User or File object directly would
    fail — always pass IDs or simple values.
    """
    context = {
        'shared_by': shared_by_name,
        'shared_with_name': shared_with_name,
        'item_type': item_type,
        'item_name': item_name,
        'permission': permission,
        'access_link': access_link,
    }

    subject = f'{shared_by_name} shared "{item_name}" with you on Drive Clone'

    # Render both versions of the email
    text_body = render_to_string('emails/share_notification.txt', context)
    html_body = render_to_string('emails/share_notification.html', context)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,           # plain text fallback
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[shared_with_email],
        )
        msg.attach_alternative(html_body, 'text/html')  # HTML version
        msg.send()

    except Exception as exc:
        # Retry the task if sending fails (network error, Gmail rate limit, etc.)
        # This will not re-run the share logic — only re-attempt the email
        raise self.retry(exc=exc)