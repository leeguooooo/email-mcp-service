import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EmailProvider(Enum):
    NETEASE_163 = "163"
    NETEASE_126 = "126"
    QQ = "qq"
    GMAIL = "gmail"
    OUTLOOK = "outlook"


@dataclass
class EmailConfig:
    provider: EmailProvider
    email: str
    password: str
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    use_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "EmailConfig":
        provider = EmailProvider(os.getenv("EMAIL_PROVIDER", "163"))
        email = os.getenv("EMAIL_ADDRESS")
        password = os.getenv("EMAIL_PASSWORD")
        
        if not email or not password:
            raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD must be set")
        
        config = cls(
            provider=provider,
            email=email,
            password=password,
            imap_host=os.getenv("IMAP_HOST"),
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "465")),
            use_ssl=os.getenv("USE_SSL", "true").lower() == "true",
        )
        
        # Set default hosts based on provider if not specified
        if not config.imap_host:
            config.imap_host = _get_default_imap_host(provider)
        if not config.smtp_host:
            config.smtp_host = _get_default_smtp_host(provider)
            
        return config


def _get_default_imap_host(provider: EmailProvider) -> str:
    hosts = {
        EmailProvider.NETEASE_163: "imap.163.com",
        EmailProvider.NETEASE_126: "imap.126.com",
        EmailProvider.QQ: "imap.qq.com",
        EmailProvider.GMAIL: "imap.gmail.com",
        EmailProvider.OUTLOOK: "outlook.office365.com",
    }
    return hosts.get(provider, "")


def _get_default_smtp_host(provider: EmailProvider) -> str:
    hosts = {
        EmailProvider.NETEASE_163: "smtp.163.com",
        EmailProvider.NETEASE_126: "smtp.126.com",
        EmailProvider.QQ: "smtp.qq.com",
        EmailProvider.GMAIL: "smtp.gmail.com",
        EmailProvider.OUTLOOK: "smtp.office365.com",
    }
    return hosts.get(provider, "")


@dataclass
class Email:
    id: str
    subject: str
    from_addr: str
    to_addr: list[str]
    date: str
    body: Optional[str] = None
    html_body: Optional[str] = None
    attachments: list[str] = None
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []