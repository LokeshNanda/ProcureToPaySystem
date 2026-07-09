import logging

logger = logging.getLogger("mail")


def send_email(to: str, subject: str, body: str) -> None:
    # Slice 0: SMTP delivery is stubbed. Real delivery lands with PLT-04.
    logger.info("email.send", extra={"to": to, "subject": subject})
