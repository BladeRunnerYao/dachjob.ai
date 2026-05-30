def render_resume_pdf(html: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
