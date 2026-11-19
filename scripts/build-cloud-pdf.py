#!/usr/bin/env python3
"""Build the Cloud report from configuration and explicitly recorded evidence.

No network, Git, cloud or secret-store calls. Missing evidence stays PENDENTE.
Use --manifest evidencias/aws/manifest.json for the AWS Cloud report.
The default manifest preserves the Azure IA checkpoint. --check never creates a PDF.
Requires reportlab/Pillow.
"""
from __future__ import annotations

import argparse
from functools import partial
from hashlib import sha256
from html import escape
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit

from PIL import Image as PILImage
from reportlab import rl_config
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.2.0"
DOCUMENT_DATE = "19/11/2026"
DEFAULT_REPO = "https://github.com/Salvittis/ponto-certo"
DEFAULT_OUTPUT = ROOT / "output/pdf/Ponto-Certo-Deploy-Blindado.pdf"
AZURE_IA_URL = "https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com"
INK = colors.HexColor("#102A43")
TEAL = colors.HexColor("#007F83")
MUTED = colors.HexColor("#536575")
PALE = colors.HexColor("#EAF5F4")
LINE = colors.HexColor("#D8E3E8")
AMBER = colors.HexColor("#9B5B00")
WIDTH = A4[0] - 88
LANDSCAPE = landscape(A4)
APPENDIX_WIDTH = LANDSCAPE[0] - 88
APPENDIX_HEIGHT = LANDSCAPE[1] - 48 - 43
SCREENSHOTS = (
    ("public_app", "MVP e interface", "public_app"),
    ("container", "Containers e execução", "docker"),
    ("terraform", "Provisionamento Terraform", "terraform"),
    ("pipeline_block", "Pipeline barrado", "ci_block"),
    ("pipeline_pass", "Pipeline aprovado", "ci_pass"),
    ("dashboard", "Dashboard e métricas", "metrics"),
    ("alert", "Alerta disparado", "alert"),
    ("recovery", "Recuperação", "recovery"),
)
CHECKS = (
    ("docker", "Containers e IA"), ("terraform", "Terraform aplicado"),
    ("ci_pass", "CI aprovado"), ("ci_block", "CI barrado e deploy impedido"),
    ("public_app", "MVP público com LLM"), ("restart", "Reinício e persistência"),
    ("metrics", "Quatro métricas"), ("alert", "Alerta disparado"),
    ("recovery", "Recuperação verificada"),
)
SCOPE = {"local": "LOCAL", "public": "PÚBLICO", "configuration": "CONFIGURAÇÃO"}
SOURCES = [
    ("Azure for Students / benefício", "https://learn.microsoft.com/azure/education-hub/about-azure-for-students"),
    ("Students / esgotamento do crédito", "https://learn.microsoft.com/azure/cost-management-billing/manage/azurestudents-subscription-disabled"),
    ("B2als_v2 / CPU credits", "https://learn.microsoft.com/azure/virtual-machines/sizes/general-purpose/basv2-series"),
    ("Microsoft Retail Prices API", "https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices"),
    ("Azure / Managed Run Command", "https://learn.microsoft.com/azure/virtual-machines/linux/run-command-managed"),
    ("Azure / GitHub OIDC", "https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect"),
    ("Terraform / state e dados sensíveis", "https://developer.hashicorp.com/terraform/language/manage-sensitive-data"),
    ("Azure / responsabilidade compartilhada", "https://learn.microsoft.com/azure/security/fundamentals/shared-responsibility"),
    ("ANPD / transferência internacional", "https://www.gov.br/anpd/pt-br/assuntos/assuntos-internacionais/transferencia-internacional-de-dados"),
    ("Prometheus / regras de alerta", "https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/"),
    ("Qwen / modelo e licença", "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF"),
    ("SPTrans / documentação Olho Vivo", "https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api"),
]
AWS_SOURCES = [
    ("AWS Academy / programa", "https://aws.amazon.com/training/awsacademy/"),
    ("Sandbox / instruções do curso", "https://awsacademy.instructure.com/courses/182549/modules/items/18007039"),
    ("EC2 / créditos CPU Standard", "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-standard-mode.html"),
    ("AWS / preços EC2", "https://aws.amazon.com/ec2/pricing/on-demand/"),
    ("AWS / preços EBS", "https://aws.amazon.com/ebs/pricing/"),
    ("AWS / preços IPv4 público", "https://aws.amazon.com/vpc/pricing/"),
    ("SSM / segurança e SecureString", "https://docs.aws.amazon.com/systems-manager/latest/userguide/security-best-practices.html"),
    ("AWS / responsabilidade compartilhada", "https://aws.amazon.com/compliance/shared-responsibility-model/"),
    SOURCES[6], SOURCES[8], SOURCES[9], SOURCES[10], SOURCES[11],
    ("GitHub Actions / cobrança", "https://docs.github.com/en/billing/concepts/product-billing/github-actions"),
    ("GitHub Packages / cobrança", "https://docs.github.com/en/billing/concepts/product-billing/github-packages"),
]


def clean(value, limit=1800):
    """Only allowlisted manifest fields pass here; normalize PDF punctuation."""
    if value is None or value == "":
        return "PENDENTE"
    text = str(value).replace("\x00", "")
    for char in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(char, "-")
    return text[:limit]


def public_url(value):
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query):
        return None
    return value


def local_file(value):
    if not isinstance(value, str) or not value:
        return None
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        return None
    # Never use private/runtime/state files as evidence, even when referenced.
    relative = path.relative_to(ROOT)
    if any(part.startswith(".") or part == "private" for part in relative.parts):
        return None
    if path.suffix in {".env", ".tfstate", ".tfvars", ".pem", ".key"}:
        return None
    return path


def read_json(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError(f"JSON de evidência ilegível: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Objeto JSON esperado: {path.name}")
    return value


def register_fonts():
    candidates = [
        (Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
         Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont("PCBody", str(regular)))
            pdfmetrics.registerFont(TTFont("PCBold", str(bold)))
            pdfmetrics.registerFontFamily("PCBody", normal="PCBody", bold="PCBold",
                                          italic="PCBody", boldItalic="PCBold")
            return "PCBody", "PCBold"
    return "Helvetica", "Helvetica-Bold"


class EvidenceAppendix(Flowable):
    """One complete, uncropped capture per landscape page, with readable context."""

    def __init__(self, report, item):
        super().__init__()
        self.report, self.item = report, item
        self.width, self.height = APPENDIX_WIDTH, APPENDIX_HEIGHT

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        report, item = self.report, self.item
        self.canv.bookmarkPage(item["anchor"])
        self.canv.addOutlineEntry(item["heading"], item["anchor"], level=0, closed=False)
        heading = report.p(item["heading"], "appendix_title")
        _, heading_height = heading.wrap(self.width, self.height)
        heading.drawOn(self.canv, 0, self.height - heading_height)

        # Captions remain text in the PDF, rather than tiny text baked into images.
        caption = report.p(f"<b>{escape(item['scope'])}</b> | " +
                           escape(item["caption"]), "appendix_caption", markup=True)
        _, caption_height = caption.wrap(self.width, self.height)
        origin = report.p(report.link("Abrir fonte ou execução", item["url"]) +
                          " | " + report.repo_link("Abrir captura original", item["relative_path"]),
                          "small", markup=True)
        _, origin_height = origin.wrap(self.width, self.height)
        origin.drawOn(self.canv, 0, 0)
        caption.drawOn(self.canv, 0, origin_height + 7)
        image_bottom = origin_height + 7 + caption_height + 10
        image_top = self.height - heading_height - 10
        image_height = image_top - image_bottom
        if image_height < 100:
            raise ValueError("Legenda excessiva para uma captura legível: " + item["key"])
        source_width, source_height = item["pixels"]
        scale = min(self.width / source_width, image_height / source_height)
        width, height = source_width * scale, source_height * scale
        self.canv.drawImage(str(item["path"]), (self.width - width) / 2,
                           image_bottom + (image_height - height) / 2,
                           width=width, height=height, mask="auto")


class Report:
    def __init__(self, manifest_path):
        self.manifest_path = manifest_path
        self.data = read_json(manifest_path)
        hint = "aws" if manifest_path.parent.resolve() == (ROOT / "evidencias/aws").resolve() else "azure"
        requested_provider = self.data.get("provider", hint)
        self.provider = "aws" if requested_provider in ("aws", "aws-academy") else requested_provider
        if self.provider not in ("aws", "azure"):
            raise ValueError("Provedor do manifesto deve ser aws, aws-academy ou azure")
        self.is_aws = self.provider == "aws"
        self.provider_label = "AWS Academy Sandbox" if self.is_aws else "Azure / histórico da IA"
        self.sources = AWS_SOURCES if self.is_aws else SOURCES
        hosting = self.data.get("ia_hosting", {})
        hosting = hosting if isinstance(hosting, dict) else {}
        self.ia_url = public_url(hosting.get("public_url")) or AZURE_IA_URL
        self.repo = public_url(self.data.get("repository_url")) or DEFAULT_REPO
        revision = self.data.get("revision", "")
        self.revision = revision if re.fullmatch(r"[0-9a-f]{40}", str(revision)) else "PENDENTE"
        self.ref = self.revision if self.revision != "PENDENTE" else "main"
        self.updated = clean(self.data.get("updated_at"), 80)
        self.url = public_url(self.data.get("public_url"))
        self.body_font, self.bold_font = register_fonts()
        base = getSampleStyleSheet()["BodyText"]
        self.styles = {
            "body": ParagraphStyle("PCBodyStyle", parent=base, fontName=self.body_font,
                fontSize=10.2, leading=14.2, textColor=INK, spaceAfter=8,
                splitLongWords=True, allowWidows=0, allowOrphans=0),
            "title": ParagraphStyle("PCTitle", fontName=self.bold_font, fontSize=23,
                leading=28, textColor=INK, spaceAfter=13),
            "h2": ParagraphStyle("PCSub", fontName=self.bold_font, fontSize=12.2,
                leading=17, textColor=TEAL, spaceBefore=9, spaceAfter=7),
            "small": ParagraphStyle("PCSmall", fontName=self.body_font, fontSize=8.6,
                leading=11.7, textColor=MUTED, spaceAfter=6, splitLongWords=True),
            "cell": ParagraphStyle("PCCell", fontName=self.body_font, fontSize=9,
                leading=12.2, textColor=INK, spaceAfter=0, splitLongWords=True),
            "caption": ParagraphStyle("PCCaption", fontName=self.body_font, fontSize=8.2,
                leading=11.1, textColor=MUTED, spaceBefore=4, spaceAfter=9),
            "code": ParagraphStyle("PCCode", fontName="Courier", fontSize=8,
                leading=11, textColor=INK, backColor=PALE, borderPadding=8,
                spaceBefore=5, spaceAfter=10, splitLongWords=True),
            "appendix_title": ParagraphStyle("PCAppendixTitle", fontName=self.bold_font,
                fontSize=16, leading=20, textColor=INK),
            "appendix_caption": ParagraphStyle("PCAppendixCaption", fontName=self.body_font,
                fontSize=10, leading=13, textColor=INK, splitLongWords=True),
        }
        self.sections = []
        self.team = self.read_team()
        self.ficha = self.read_ficha()
        self.appendices = self.screenshot_inventory()

    def read_team(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        matches = re.findall(r"^\|\s*([^|\n]+?)\s*\|\s*(RM\d+)\s*\|", readme, re.M)
        if not matches:
            raise ValueError("Ficha Técnica sem nomes/RMs no README; não serão inventados")
        return [(name.strip(), rm.strip()) for name, rm in matches]

    def read_ficha(self):
        # README is the team's canonical Ficha; never invent missing fields.
        opening = (ROOT / "README.md").read_text(encoding="utf-8").split("\n## ", 1)[0]
        fields = {}
        for name in ("Modelo", "Indicadores de impacto"):
            match = re.search(r"^\|\s*" + re.escape(name) + r"\s*\|\s*([^|\n]+)\s*\|", opening, re.M)
            if not match:
                raise ValueError("Ficha Técnica sem campo obrigatório no README: " + name)
            # These values enter ReportLab as escaped text, not executable markup.
            fields[name] = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", match.group(1)).replace("`", "").replace("**", "").strip()
        return fields

    def p(self, text, style="body", markup=False):
        value = clean(text)
        return Paragraph(value if markup else escape(value), self.styles[style])

    def link(self, label, url):
        safe = public_url(url)
        if not safe:
            return escape(clean(label)) + " (PENDENTE)"
        return f'<link href="{escape(safe, quote=True)}" color="#007F83">{escape(clean(label))}</link>'

    def repo_link(self, label, path):
        return self.link(label, self.artifact_url(path))

    def artifact_url(self, path):
        # Final evidence can be attached to the immutable release after deployment,
        # avoiding a document commit that changes the SHA of the published service.
        assets = self.data.get("artifact_urls", {})
        asset = assets.get(path) if isinstance(assets, dict) else None
        return public_url(asset) or f"{self.repo}/blob/{self.ref}/{quote(path, safe='/')}"

    def table(self, rows, widths=None, header=True):
        cells = [[self.p(cell, "cell", markup=True) for cell in row] for row in rows]
        table = Table(cells, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ]
        if header:
            commands.extend([("BACKGROUND", (0, 0), (-1, 0), PALE)])
        table.setStyle(TableStyle(commands))
        return table

    def section(self, title, subtitle=None):
        flow = [self.p(title, "title")]
        if subtitle:
            flow.append(self.p(subtitle, "small"))
        self.sections.append(flow)
        return flow

    def record(self, key):
        checks = self.data.get("checks", {})
        record = checks.get(key, {}) if isinstance(checks, dict) else {}
        return record if isinstance(record, dict) else {}

    def references(self, record):
        values = record.get("evidence", [])
        if not isinstance(values, list):
            values = [values]
        if record.get("url"):
            values = [record["url"], *values]
        links = []
        for value in values[:8]:
            if isinstance(value, dict):
                value = value.get("path") or value.get("url")
            if public_url(value):
                links.append((clean(value, 180), value))
            elif (path := local_file(value)) is not None:
                rel = path.relative_to(ROOT).as_posix()
                links.append((rel, self.artifact_url(rel)))
        return links

    def status(self, record):
        raw = str(record.get("status", "pending")).lower()
        scope = SCOPE.get(record.get("scope"))
        documented = bool(scope and record.get("checked_at") and self.references(record))
        record_provider = record.get("provider", self.provider)
        record_provider = "aws" if record_provider == "aws-academy" else record_provider
        if record_provider not in (self.provider, "shared"):
            return "PENDENTE / PROVEDOR DIVERGENTE"
        if not documented:
            return "PENDENTE"
        label = {"passed": "VALIDADO", "failed": "FALHOU", "partial": "PARCIAL",
                 "in_progress": "EM CURSO"}.get(raw, "PENDENTE")
        return f"{label} / {scope}"

    def evidence_note(self, key):
        record = self.record(key)
        links = self.references(record)
        content = f"<b>{escape(self.status(record))}</b>"
        if record.get("checked_at"):
            content += " | " + escape(clean(record["checked_at"], 90))
        if record.get("summary"):
            content += "<br/>" + escape(clean(record["summary"], 650))
        if links:
            content += "<br/>" + "<br/>".join(self.link(label, url) for label, url in links[:3])
        else:
            content += "<br/>Sem evidência referenciada. Configuração não é validação."
        return self.p(content, "small", markup=True)

    def image(self, path, caption, max_height=180):
        with PILImage.open(path) as source:
            width, height = source.size
        scale = min(WIDTH / width, max_height / height)
        picture = Image(str(path), width=width * scale, height=height * scale)
        picture.hAlign = "LEFT"
        return KeepTogether([picture, self.p(caption, "caption")])

    def screenshot_inventory(self):
        shots = self.data.get("screenshots", {})
        results = []
        for key, title, check in SCREENSHOTS:
            item = shots.get(key, {}) if isinstance(shots, dict) else {}
            if isinstance(item, str):
                item = {"path": item}
            if not isinstance(item, dict):
                continue
            item_provider = item.get("provider", self.provider)
            item_provider = "aws" if item_provider == "aws-academy" else item_provider
            if item_provider not in (self.provider, "shared"):
                continue
            path = local_file(item.get("path"))
            if not path or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            with PILImage.open(path) as source:
                pixels = source.size
            relative_path = path.relative_to(ROOT).as_posix()
            original_url = self.artifact_url(relative_path)
            results.append({"key": key, "path": path, "pixels": pixels,
                "relative_path": relative_path, "anchor": "appendix-" + key,
                "heading": f"Apêndice {chr(65 + len(results))} / {title}",
                "scope": SCOPE.get(item.get("scope"), "ESCOPO NÃO INFORMADO"),
                "caption": clean(item.get("caption", title), 700),
                "url": public_url(item.get("url")) or public_url(self.record(check).get("url")) or original_url})
        return results

    def screenshot(self, key, max_height=None):
        # Keep the core report compact; full captures get their own landscape pages.
        item = next((value for value in self.appendices if value["key"] == key), None)
        if item is None:
            return self.p("Captura PENDENTE: " + key + ".", "small")
        return self.p(f'<link href="#{item["anchor"]}" color="#007F83">'
                      f'{escape(item["heading"])}</link> - captura integral em paisagem. '
                      f'Escopo: {escape(item["scope"])}.', "small", markup=True)

    def architecture(self):
        diagram = Drawing(WIDTH, 204)
        def box(x, y, w, h, title, detail, fill=PALE):
            diagram.add(Rect(x, y, w, h, rx=7, ry=7, strokeColor=LINE, fillColor=fill))
            diagram.add(String(x + 10, y + h - 18, title, fontName=self.bold_font,
                               fontSize=9.4, fillColor=INK))
            diagram.add(String(x + 10, y + 13, detail, fontName=self.body_font,
                               fontSize=8, fillColor=MUTED))
        def arrow(x1, y1, x2, y2):
            diagram.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=1.3))
            if x2 != x1:
                sign = 1 if x2 > x1 else -1
                points = [x2, y2, x2 - sign * 5, y2 + 3, x2 - sign * 5, y2 - 3]
            else:
                sign = 1 if y2 > y1 else -1
                points = [x2, y2, x2 - 3, y2 - sign * 5, x2 + 3, y2 - sign * 5]
            diagram.add(Polygon(points, fillColor=TEAL, strokeColor=TEAL))
        diagram.add(Rect(122, 6, WIDTH - 123, 140, rx=9, ry=9,
                         fillColor=colors.HexColor("#F5F8FA"), strokeColor=LINE))
        diagram.add(String(134, 134, "EC2 AWS / us-east-1" if self.is_aws else "VM Azure / Chile Central", fontName=self.bold_font,
                           fontSize=9, fillColor=INK))
        box(0, 67, 102, 53, "Navegador", "Internet / HTTPS")
        box(133, 67, 108, 53, "Caddy", "80/443 no host")
        box(262, 67, 108, 53, "FastAPI", "8000 / não root")
        box(391, 67, WIDTH - 392, 53, "Qwen local", "8081 / privada")
        arrow(102, 93, 133, 93)
        arrow(241, 93, 262, 93)
        arrow(370, 93, 391, 93)
        box(262, 12, 108, 43, "Base documental", "+ fixtures demo")
        arrow(316, 55, 316, 67)
        box(0, 12, 102, 43, "SPTrans", "live pendente")
        # Dashed external data path is conditional; fixtures supply the demo.
        for x1, y1, x2, y2 in [(102, 34, 114, 34), (114, 34, 114, 58),
                              (114, 58, 250, 58), (250, 58, 250, 82)]:
            diagram.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=1.1, strokeDashArray=[3, 2]))
        arrow(250, 82, 262, 82)
        box(0, 153, 225, 48, "GitHub Actions / GHCR", "Gates > digest > SSM / Lab" if self.is_aws else "Gates > digest aprovado > OIDC")
        box(272, 153, WIDTH - 272, 48, "Prometheus / Grafana locais", "HTTPS /metrics + Bearer; /readyz")
        arrow(187, 153, 187, 146)
        arrow(316, 153, 316, 146)
        diagram.add(String(135, 32, "SG: só 80/443" if self.is_aws else "NSG: só 80/443", fontName=self.body_font, fontSize=8.3, fillColor=MUTED))
        diagram.add(String(135, 20, "Sem SSH público", fontName=self.body_font, fontSize=8.3, fillColor=MUTED))
        diagram.add(String(391, 36, "Demo: sintético", fontName=self.body_font, fontSize=8, fillColor=MUTED))
        diagram.add(String(391, 24, "Tracejado: live", fontName=self.body_font, fontSize=8, fillColor=MUTED))
        diagram.add(String(391, 12, "ainda não validado", fontName=self.body_font, fontSize=8, fillColor=MUTED))
        return diagram

    def aws_infrastructure(self, provisioning, provision_text):
        p = self.p
        return [p("Provisionamento: " + self.status(provisioning), "h2"),
            p("Região registrada: " + clean(provisioning.get("region"), 80) +
              ". Tipo registrado: " + clean(provisioning.get("instance_type", provisioning.get("vm_size")), 80) +
              ". O status acima depende das evidências do manifesto AWS.", "small"),
            p(provision_text + "Configuração versionada: VPC/subnet/IGW/rotas próprios; EC2 t2.medium "
              "Standard, 2 vCPUs/4 GiB; Ubuntu 24.04 x86_64/HVM da Canonical, AMI explícita; "
              "EBS gp2 cifrado de 32 GiB, removido com a instância. Provider AWS 6.73.0 fixado."),
            self.table([["Superfície", "Controle preparado"],
                ["Rede pública", "Security Group permite somente TCP 80/443. Sem SSH, keypair ou porta pública da LLM."],
                ["Gestão", "SSM pela conexão de saída do agente; IMDSv2 obrigatório, hop limit 1."],
                ["Identidade", "LabInstanceProfile existente, imposto pelo laboratório. Terraform não cria IAM."],
                ["Bootstrap", "Docker/Compose, AWS CLI e agente SSM. Marker não comprova SSM Online nem aplicação."],
                ["Segredos", "SecureString temporário; comando contém nome/versão. runtime.env 600; diretório 700."]], [109, WIDTH - 109]),
            p("State isolado e conta autorizada", "h2"),
            p("infra/aws/tf.sh usa ~/.local/share/ponto-certo/terraform-aws fora do Git e separado do "
              "state Azure; diretórios 700, umask 077 e lock local, com um operador. Credenciais da "
              "sessão não são variáveis Terraform. allowed_account_ids restringe a conta Academy. "
              "State/plan/tfvars nunca são publicados. Não se presume backup AWS sem evidência."),
            p("As permissões do perfil são as disponibilizadas pelo Sandbox, não um papel IAM criado "
              "pela equipe. Guards verificam conta, instância/tag, x86_64 e SSM Online; não substituem "
              "a política IAM. SSM Run Command tem poder administrativo no host.", "small"),
            self.evidence_note("terraform"),
            p(self.repo_link("Terraform AWS e controles", "infra/aws/main.tf") + " | " +
              self.repo_link("State AWS", "infra/aws/tf.sh") + " | " +
              self.repo_link("Operação do deploy AWS", "security/AWS-DEPLOY.md"), "small", markup=True)]

    def aws_reproduction(self):
        p = self.p
        return [p("1. Reproduzir aplicação e modelo", "h2"),
            p("Docker/Compose; METRICS_TOKEN por arquivo/ambiente protegido. Mesmo código, pesos e "
              "dados demo da IA; sem token SPTrans no modo demo."),
            p("docker compose -f compose.yaml config --quiet<br/>"
              "docker compose -f compose.yaml up -d --build<br/>"
              "python3 scripts/smoke.py --base-url http://127.0.0.1:8000<br/>"
              "# --expect-mode demo --output reports/smoke-local.json", "code", markup=True),
            p("2. Sessão Academy e Terraform AWS", "h2"),
            p("Iniciar a sessão autorizada e conferir prazo restante. Usar credenciais temporárias "
              "da conta do laboratório, fora de arquivos públicos. Verificar STS, AMI Canonical "
              "24.04 e disponibilidade t2.medium na zona de us-east-1. Fornecer allowed_account_ids, "
              "ubuntu_ami_id e availability_zone em tfvars externo. Revisar plano antes do apply."),
            p("bash infra/aws/tf.sh init<br/>bash infra/aws/tf.sh validate<br/>"
              "aws sts get-caller-identity --region us-east-1<br/>"
              "# plan/apply com tfvars e plano no diretório AWS externo protegido", "code", markup=True),
            p("3. Gates, SSM e observação pública", "h2"),
            p("Environment aws-academy limitado à main; habilitar AWS_ENABLED somente na sessão. "
              "Secrets: as três credenciais AWS temporárias e AWS_METRICS_TOKEN; SPTrans apenas "
              "para live. Variables identificam conta, região, instância, URL e limite da sessão. "
              "O deploy usa digests aprovados, valida SSM Online e depois HTTPS, revisão e smoke. "
              "IP/sslip.io sugeridos pelo Terraform não comprovam DNS, certificado ou publicação."),
            p("python3 scripts/configure-monitoring-aws.py<br/>"
              "  --url https://URL-AWS-VALIDADA<br/>"
              "  --metrics-token-file /CAMINHO-EXTERNO/token-aws<br/>"
              "  --runtime-dir /CAMINHO-EXTERNO/monitoring-aws<br/>"
              "# Comando acima em uma linha; token fonte com permissão 600.<br/>"
              "export PC_AWS_MONITORING_DIR=/CAMINHO-EXTERNO/monitoring-aws<br/>"
              "docker compose -f compose.monitoring.aws.yaml up -d", "code", markup=True),
            p("Gerar tráfego real; registrar quatro métricas, reinício da LLM, disparo e recuperação. "
              "A AWS usa projeto/volumes próprios e portas locais 9091/3002; o monitor Azure "
              "permanece separado. Em nova sessão, preservar evidências e trocar explicitamente "
              "o alvo AWS; o coletor rejeita histórico misturado nos últimos dez minutos. Exportar evidências antes do fim da "
              "sessão. Expiração interrompe operações; credenciais não se renovam automaticamente."),
            p(self.repo_link("Procedimento completo e nova sessão", "docs/CLOUD-AWS.md"), "small", markup=True)]

    def aws_costs_and_session(self, cost, money):
        p = self.p
        session = self.data.get("session", {})
        session = session if isinstance(session, dict) else {}
        hours = session.get("duration_hours", 3)
        hours = hours if isinstance(hours, (int, float)) and not isinstance(hours, bool) and math.isfinite(hours) and hours > 0 else None
        return [p("O alvo é a conta educacional AWS Academy Sandbox autorizada. O operador informou "
              "uma sessão de 3 horas; a janela não equivale a crédito monetário. Não foi autorizada "
              "contratação em conta pessoal/corporativa. Não se presume saldo em dólares, fatura "
              "pessoal ou custo zero a partir do cronômetro."),
            self.table([["Sessão registrada", "Valor"],
                ["Duração anunciada (horas)", escape(clean(hours, 30))],
                ["Início / expiração", escape(clean(session.get("started_at"), 55) + " / " + clean(session.get("expires_at"), 55))],
                ["Crédito monetário confirmado", money("lab_budget_usd")]], [230, WIDTH - 230]),
            p("Estimativa comercial de referência", "h2"),
            self.table([["Cotação AWS registrada", "Valor"],
                ["Região / data da consulta", escape(clean(cost.get("region"), 60) + " / " + clean(cost.get("checked_at"), 65))],
                ["Período estimado em horas", escape(clean(cost.get("hours"), 30))],
                ["t2.medium por hora", money("vm_hourly_usd")],
                ["IPv4 público por hora", money("ip_hourly_usd")],
                ["EBS gp2 32 GiB por mês", money("disk_monthly_usd")],
                ["Total estimado de referência", money("total_estimate_usd")]], [290, WIDTH - 290]),
            p("Valores ausentes ficam PENDENTE e não herdam preços Azure. A estimativa usa preços "
              "públicos e premissas do manifesto; não é cobrança observada no Sandbox. Egress, "
              "serviços adicionais e duração podem alterar o total. Créditos CPU do modo Standard "
              "são unidades de desempenho, não saldo financeiro; esgotá-los reduz desempenho.", "small"),
            p("GitHub: runners padrão de repositório público não cobram minutos; GHCR informa "
              "armazenamento/tráfego de containers gratuitos atualmente. Artefatos e caches do Actions "
              "têm regras próprias: imagens de transferência ficam por 2 dias e relatórios por 14; "
              "retenção não comprova ausência de cobrança. Não foram ativados runners pagos.", "small"),
            p("Janela efêmera e continuidade da IA", "h2"),
            p("O guia do Sandbox informa remoção de dados e recursos ao terminar a sessão ou "
              "zerar o cronômetro. IP/URL AWS são temporários; não prometer disponibilidade AWS "
              "durante toda a semana de correção. O professor aceitou o Sandbox conforme relato "
              "de Pedro. Preservar prints/JSON, manifesto e comandos para reproduzir nova sessão."),
            p("Plano de manutenção: manter a Azure para IA até pelo menos 27/11/2026 às 23h55 de São Paulo, "
              "sujeita ao crédito Students e à manutenção documentada; não desligá-la ao encerrar "
              "a AWS. Antes de terminar o laboratório, preservar evidências, desabilitar o deploy "
              "AWS e remover credenciais temporárias. Expiração não substitui verificação de limpeza."),
            p(self.link("Preços EC2", AWS_SOURCES[3][1]) + " | " +
              self.link("EBS", AWS_SOURCES[4][1]) + " | " + self.link("IPv4", AWS_SOURCES[5][1]) + " | " +
              self.repo_link("Procedimento AWS", "security/AWS-DEPLOY.md"), "small", markup=True)]

    def build_sections(self):
        self.sections = []
        p = self.p
        provisioning = self.data.get("provisioning", {})
        provisioning = provisioning if isinstance(provisioning, dict) else {}
        provisioned = self.status(provisioning) == "VALIDADO / PÚBLICO"
        selected_region = "us-east-1 / Norte da Virgínia" if self.is_aws else "chilecentral / Chile Central"
        location = "Norte da Virgínia, Estados Unidos" if self.is_aws else "Chile Central, Chile"
        resource_kind = "Instância EC2" if self.is_aws else "VM"
        if provisioned:
            provision_text = ("O manifesto registra provisionamento concluído em " +
                clean(provisioning.get("region"), 80) + ". A evidência de apply e leitura da API "
                "confirma alocação; a validação da aplicação pública é registrada separadamente. ")
            location_text = (resource_kind + " alocada na região " + clean(provisioning.get("region"), 80) +
                ", conforme evidência de provisionamento. " + location + ", fora do Brasil. ")
        else:
            provision_text = ("Seleção configurada: " + selected_region + ". A conclusão do apply ainda "
                "não está validada no manifesto; configuração e preflight não comprovam alocação. ")
            location_text = ("Região registrada: " + clean(provisioning.get("region"), 80) +
                ". Seleção: " + location + ", fora do Brasil. Alocação ainda sem validação completa "
                "no manifesto. ")
        sec = self.section("Ficha Técnica", "PONTO CERTO / DEPLOY BLINDADO / CLOUD COMPUTING")
        sec += [p("Informação de ônibus com evidência, IA local e uma publicação verificável."),
                self.table([["Campo", "Definição"],
                    ["Produto / território", "Ponto Certo / ônibus municipais de São Paulo"],
                    ["Cidadão / problema", "Pessoas que dependem do ônibus; espera e informação incerta"],
                    ["Disciplina", "Secure DevOps Tools &amp; Cloud Computing / FIAP / CitizenTech 2026.2"],
                    ["Ambiente deste relatório", escape(self.provider_label)],
                    ["Arquitetura", "FastAPI + recuperação e consultas controladas + Qwen local + Caddy"],
                    ["Fontes / modo", "SPTrans e base documental; demonstração sintética, live depende de token"],
                    ["Modelo", escape(self.ficha["Modelo"])],
                    ["Indicadores de impacto", escape(self.ficha["Indicadores de impacto"])],
                    ["ODS / impacto", "ODS 11 / contribuição proposta; redução de espera não medida"]], [127, WIDTH - 127]),
                Spacer(1, 10), self.table([["Integrante", "RM"], *[[escape(a), b] for a, b in self.team]], [WIDTH - 90, 90]),
                p("Responsável por IA e Cloud: Pedro Henrique Salvitti Habiro.", "small"),
                p(self.link("Repositório e código", self.repo) + "<br/>" +
                  (self.link("MVP deste ambiente: " + self.url, self.url) if self.url else "MVP deste ambiente: <b>PENDENTE</b>"), markup=True),
                p(f"Documento v{VERSION} | {DOCUMENT_DATE}. Evidências atualizadas: {self.updated}.<br/>"
                  f"Revisão Git registrada: {self.revision}.", "small", markup=True),
                p("Uma URL registrada não comprova disponibilidade. O manifesto distingue configuração, "
                  "teste local e execução pública; lacunas permanecem PENDENTE.", "small")]

        sec = self.section("01 / Arquitetura da mesma IA", "Configuração de publicação, sem trocar a aplicação avaliada")
        sec += [self.architecture(), Spacer(1, 8),
                p("AWS Sandbox é a entrega Cloud, conforme aceite do professor relatado por Pedro. "
                  "A Azure permanece como hospedagem persistente da IA, separada desta implantação. " +
                  self.link("Abrir IA na Azure", self.ia_url), "small", markup=True) if self.is_aws else
                p("Este relatório preserva o checkpoint Azure da IA. A nova entrega Cloud usa AWS Sandbox "
                  "e precisa de manifesto e evidências próprios.", "small"),
                p("O navegador acessa Caddy por HTTPS. FastAPI recupera documentos e executa consultas "
                  "controladas; a geração usa Qwen2.5-1.5B-Instruct Q4_K_M no llama.cpp b12464, "
                  "dentro da infraestrutura do projeto. Não há API comercial de LLM."),
                p("A rede backend do Compose isola a porta 8081. App e modelo não publicam portas "
                  "diretamente no host. A app usa saída para SPTrans no modo live; não há política "
                  "restritiva de egress. Caddy atende 80/443 por portas internas altas, sem root."),
                p("Em demo, linha, parada e previsões são sintéticas e identificadas. A inferência é real. "
                  "Consulta documental pode usar informação estável; disponibilidade de dados não é "
                  "confundida com prontidão do processo. Sem suporte, o sistema esclarece, recusa ou informa falha."),
                p("Uma VM e um slot de inferência: sem alta disponibilidade e sem promessa de capacidade "
                  "populacional. CPU e RAM precisam ser medidas em produção. O desempenho do Mac local "
                  "com Metal não serve como benchmark da VM x64."),
                p(self.repo_link("Contrato IA e endpoints", "docs/CONTRATO-IA-CLOUD.md") + " | " +
                  self.repo_link("Relatório e limitações da IA", "docs/RELATORIO-IA.md"), "small", markup=True),
                self.evidence_note("public_app")]
        if any(item["key"] == "public_app" for item in self.appendices):
            sec.append(self.screenshot("public_app"))

        sec = self.section("02 / Containers e integração", "Rubrica: 2 pontos / configuração e execução são registros distintos")
        sec += [self.table([["Controle", "Implementação"],
                    ["Usuário", "App e LLM: UID/GID 10001; proxy não root. Daemon Docker do host continua privilegiado."],
                    ["Imutabilidade", "Bases por digest; pesos por revisão/SHA-256; filesystem read-only e tmpfs limitado."],
                    ["Isolamento", "cap_drop ALL, no-new-privileges; LLM privada; sem socket Docker nos containers."],
                    ["Recursos", "LLM 3 GiB, app 512 MiB, proxy 128 MiB; limites não reservam recursos nem eliminam OOM."],
                    ["Reinício", "unless-stopped; pesos na imagem e certificados persistentes. Healthchecks + readiness + smoke."],
                    ["Segredos", "Runtime protegido; nenhum token em imagem, repositório, cloud-init ou state."]], [100, WIDTH - 100]),
                self.evidence_note("docker")]
        smoke = {} if self.is_aws else read_json(ROOT / "evidencias/cloud/smoke-compose.json")
        if smoke:
            checks = smoke.get("checks", [])
            checks = checks if isinstance(checks, list) else []
            passed = sum(item.get("passed") is True for item in checks if isinstance(item, dict))
            sec.append(p(f"Smoke Compose LOCAL registrado: {passed}/{len(checks)} checks; "
                         f"alvo {clean(smoke.get('base_url'), 90)}; "
                         f"horário {clean(smoke.get('finished_at'), 70)}. "
                         "Não comprova URL pública nem desempenho Azure.", "small"))
        if any(item["key"] == "container" for item in self.appendices):
            sec.append(self.screenshot("container"))
        if self.is_aws:
            sec.extend([p("Reinício e persistência", "h2"), self.evidence_note("restart")])
        sec.append(p(self.repo_link("Compose produção", "compose.production.yaml") + " | " +
                     self.repo_link("Dockerfile app", "Dockerfile") + " | " +
                     self.repo_link("Dockerfile modelo", "Dockerfile.llm"), "small", markup=True))

        sec = self.section("03 / Terraform e acesso", "Rubrica: 3 pontos / fronteira administrativa restrita")
        if self.is_aws:
            sec += self.aws_infrastructure(provisioning, provision_text)
        else:
            sec += [p("Provisionamento: " + self.status(provisioning), "h2"),
                    p("Região registrada: " + clean(provisioning.get("region"), 80) +
                      ". SKU: " + clean(provisioning.get("vm_size"), 80) +
                      ". Conclusão do apply conforme o status acima.", "small"),
                    p(provision_text + "Terraform administra "
                      "RG FIAP, VNet/subnet, NIC, NSG, IP Standard/DNS, VM Ubuntu 24.04 e SSD de 32 GiB. "
                      "A imagem Ubuntu exige versão numérica; provider AzureRM 5.14.0 e checksums ficam no lockfile."),
                    self.table([["Superfície", "Controle preparado"],
                        ["Entrada pública", "Só TCP 80/443; negar outras entradas, inclusive SSH 22. Sem senha administrativa."],
                        ["Bootstrap", "Docker/Compose via apt oficial, diretórios e rotação de logs. Sem aplicação ou credenciais."],
                        ["CI / identidade", "OIDC GitHub para environment production; identidade não anexada à VM."],
                        ["RBAC", "VM/instanceView read e Managed Run Commands read/write/delete, apenas nesta VM."],
                        ["Segredos", "protectedParameters por JSON temporário 600; /opt/ponto-certo/runtime.env 600, diretório 700."]], [109, WIDTH - 109]),
                    p("State fora do Git", "h2"),
                    p("O wrapper infra/tf.sh usa diretório externo ~/.local/share/ponto-certo/terraform, "
                      "permissão 700 e umask 077. State, planos, tfvars e chaves privadas nunca são artefatos "
                      "de CI. State local é texto. FileVault protege o disco; o backup verificado é uma cópia "
                      "nesse mesmo disco cifrado, não offsite, e não protege contra perda do computador. O lock é local "
                      "e há um único operador; sensitive não cifra valores."),
                    p("O environment GitHub deve restringir branch main. Com environment, o subject OIDC "
                      "não inclui branch: essa regra não é garantida só pelo Terraform. Run Command "
                      "continua sendo administração do host, mesmo com RBAC restrito.", "small"),
                    self.evidence_note("terraform"),
                    p(self.repo_link("Operação, pré-requisitos e state", "infra/OPERACAO.md"), "small", markup=True)]
        if any(item["key"] == "terraform" for item in self.appendices):
            sec.append(self.screenshot("terraform"))

        sec = self.section("04 / Pipeline que bloqueia", "Rubrica: 4 pontos / CI executa em push e pull request")
        sec += [p("Gitleaks (histórico) + Semgrep (política) + testes + build/Trivy (app e LLM) + "
                  "Trivy (Caddy). Os gates são dependências da publicação; severidade HIGH/CRITICAL e "
                  "segredos barram as imagens. Ações e versões são fixadas."),
                p("Push na main publica as mesmas três imagens examinadas, sem rebuild. O job AWS "
                  "depende da publicação aprovada e só executa com AWS_ENABLED=true, no environment "
                  "aws-academy. STS/instância/SSM Online são verificados; depois do SSM Run Command, "
                  "HTTPS, revisão, prontidão e smoke com LLM real precisam passar. O job Azure é separado.") if self.is_aws else
                p("Push na main publica os mesmos arquivos de imagem examinados, sem rebuild. O GHCR "
                  "fornece os digests de app, LLM e proxy; production usa OIDC e Managed Run Command. "
                  "Depois, o job verifica TLS, revisão, prontidão e smoke com LLM real."),
                p("AWS usa credenciais temporárias de três partes da sessão em GitHub Secrets. "
                  "Tokens de runtime/GHCR passam por SecureString Standard temporário, alias/aws/ssm; "
                  "o Run Command contém apenas nome/versão, não valores. EC2 lê pelo perfil Lab. "
                  "O parâmetro é excluído ao final; limpeza não confirmada falha o job. Login Docker "
                  "usa stdin e configuração temporária removida após pull. Falha pública aciona tentativa "
                  "de rollback por revisão; registrar o resultado real.", "small") if self.is_aws else
                p("Não se presume GHCR público. Pull privado usa GITHUB_TOKEN efêmero com packages: read, "
                  "parâmetro protegido e login Docker temporário removido ao final. O código público "
                  "permite reprodução por build das fontes.", "small"),
                p("Ensaio: fixture sintética nunca executada introduz eval; Semgrep deve barrar o commit "
                  "e impedir deploy. Remover a fixture e repetir a mesma política deve aprovar a correção. "
                  "Não usar segredo real, desabilitar scanner ou abrandar severidade."),
                self.evidence_note("ci_block"), self.screenshot("pipeline_block", 120),
                self.evidence_note("ci_pass"), self.screenshot("pipeline_pass", 120),
                p(self.repo_link("Workflow e gates", ".github/workflows/devsecops.yml") + " | " +
                  self.repo_link("Deploy AWS e credenciais" if self.is_aws else "Ensaio controlado",
                                 "security/AWS-DEPLOY.md" if self.is_aws else "scripts/security-demo.py"), "small", markup=True)]

        sec = self.section("05 / Quatro métricas de ouro", "Rubrica: 3 pontos com alerta / medir a mesma URL publicada")
        metrics = self.data.get("metrics", {})
        metrics = metrics if isinstance(metrics, dict) else {}
        metrics_provider = metrics.get("provider", self.provider)
        metrics_provider = "aws" if metrics_provider == "aws-academy" else metrics_provider
        metric_target_matches = bool(self.url and metrics.get("target") == self.url and metrics_provider == self.provider)
        def measured(key, unit):
            value = metrics.get(key)
            if not metric_target_matches or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return "PENDENTE"
            return f"{value:.4g} {unit}"
        sec += [self.table([["Sinal", "Definição", "Valor registrado"],
                    ["Latência", "p95 /api/ask, histograma e janela de 5 min", measured("latency_p95_seconds", "s")],
                    ["Tráfego", "rate de perguntas /api/ask em 5 min", measured("traffic_requests_per_second", "req/s")],
                    ["Erros", "HTTP 5xx / total de perguntas em 5 min", measured("error_rate_percent", "%")],
                    ["Saturação", "Slots LLM ocupados / capacidade (1 slot)", measured("saturation_percent", "%")]], [78, 290, WIDTH - 368]),
                p("Escopo: " + SCOPE.get(metrics.get("scope"), "PENDENTE") +
                  ". Alvo: " + clean(metrics.get("target"), 150) +
                  ". Janela: " + clean(metrics.get("window"), 150) + ".", "small"),
                p("Prometheus/Grafana ficam locais, conforme permissão da rubrica, e coletam HTTPS "
                  "da aplicação. /metrics exige Bearer em cabeçalho; /readyz é público. Somente loopback "
                  "expõe as interfaces de monitoramento. Coleta e avaliação: 15 s."),
                p("Saturação mede slot, não CPU. RSS mede só Python, não o modelo. Sem tráfego, "
                  "latência/percentual não significam zero. not_found e clarification não são falhas "
                  "de infraestrutura. Perguntas e IPs não viram rótulos."),
                self.evidence_note("metrics"), self.screenshot("dashboard", 210),
                p(self.repo_link("PromQL, configuração e limites", "docs/OBSERVABILIDADE-AWS.md" if self.is_aws else "docs/OBSERVABILIDADE.md"), "small", markup=True)]

        sec = self.section("06 / Alerta e recuperação", "Evidência operacional, sem substituir serviço real por série sintética")
        sec += [self.table([["Regra", "Condição persistente"],
                    ["PublicReadyUnavailable", "probe_success == 0 por 1 min; inclui HTTP, DNS, rede e TLS"],
                    ["ModelNotReady", "ponto_certo_model_ready == 0 por 1 min"],
                    ["MetricsUnavailable", "up == 0 por 1 min; telemetria indisponível, não conclui queda do app"]], [160, WIDTH - 160]),
                p("O limiar de 1 min reduz ruído de uma falha isolada e cobre múltiplas sondagens de "
                  "15 s. Reservar cerca de 90 s no ensaio. Prometheus mostra firing; não foi configurada "
                  "notificação por e-mail ou WhatsApp."),
                p("Registrar baseline saudável e alvo; interromper brevemente a LLM monitorada com "
                  "restauração preparada; preservar firing e horário; restaurar; conferir /readyz, "
                  "inferência e alerta resolvido. Se o teste for falha de token de métricas, identificá-lo "
                  "como falha de telemetria, sem atribuí-lo à LLM."),
                self.evidence_note("alert"), self.screenshot("alert", 160),
                self.evidence_note("recovery"), self.screenshot("recovery", 100),
                p("Testes promtool usam séries sintéticas identificadas e verificam a regra. "
                  "Não substituem um disparo observado contra o serviço real.", "small")]

        sec = self.section("07 / Reproduzir e atualizar", "Execução local primeiro; publicação depende da assinatura e do pipeline")
        if self.is_aws:
            sec += self.aws_reproduction()
        else:
            sec += [p("1. Containers locais", "h2"),
                    p("Na raiz do repositório, com Docker/Compose. Configure METRICS_TOKEN por arquivo "
                      "protegido/ambiente, sem colocá-lo no comando ou nas evidências. Demo não exige SPTrans."),
                    p("docker compose -f compose.yaml config --quiet<br/>"
                      "docker compose -f compose.yaml up -d --build<br/>"
                      "python3 scripts/smoke.py --base-url http://127.0.0.1:8000<br/>"
                      "# --expect-mode demo --output reports/smoke-local.json", "code", markup=True),
                    p("2. Infraestrutura acadêmica", "h2"),
                    p("Confirmar Students, crédito, spending limit, SKU/região/quota. Chile Central passou "
                      "no preflight com B2als_v2. Usar assinatura "
                      "acadêmica separada. Criar chave específica e tfvars fora do Git. Init/validate são "
                      "locais; plan consulta a conta, apply cria recursos. Revisar o plano antes de aplicar."),
                    p("bash infra/tf.sh init<br/>bash infra/tf.sh validate<br/>"
                      "az vm image show --location chilecentral<br/>"
                      "  --urn Canonical:ubuntu-24_04-lts:server:24.04.202611170<br/>"
                      "# Comando Azure em uma linha; não selecionar imagem por prefixo.<br/>"
                      "# plan/apply: tfvars e plano no diretório externo protegido", "code", markup=True),
                    p("3. Release e observabilidade", "h2"),
                    p("Configurar production limitado à main; Secrets de IDs Azure, METRICS_TOKEN e "
                      "SPTRANS_TOKEN somente no modo live; Variables de RG/VM/URL. O pipeline publica "
                      "digests aprovados, aplica Compose e verifica a revisão. Pesos vêm na imagem, "
                      "certificados persistem e a configuração anterior é mantida para tentativa de rollback."),
                    p("python3 observability/configure.py --url https://URL-REAL<br/>"
                      "docker compose -f compose.monitoring.yaml up -d", "code", markup=True),
                    p("Confirmar TLS, readiness, inferência, fontes/modo, porta 22 fechada, reinício e "
                      "versão. Gerar tráfego real e coletar métricas, alerta e recuperação. Falha da "
                      "validação externa aciona tentativa de recuperação; a primeira release não tem "
                      "antecessora e é interrompida. Registrar resultado, sem presumir recuperação."),
                    self.evidence_note("restart")]

        sec = self.section("08 / Dados e responsabilidades", "Minimização, acesso e localização documentados sem certificar conformidade")
        sec += [self.table([["Camada", "Responsável"],
                    ["Datacenter, host físico, virtualização", "AWS na oferta IaaS" if self.is_aws else "Microsoft na oferta IaaS"],
                    ["Conta e identidade", "Academy disponibiliza conta/perfil; equipe protege sessão e segredos" if self.is_aws else "Equipe protege conta, federação e segredos"],
                    ["Rede, SO, patches e Docker", "Equipe / Pedro, operador IA e Cloud"],
                    ["Aplicação, modelo, dados, segredos", "Equipe / Pedro; validação e correção do sistema"],
                    ["Monitoramento, restore e evidências", "Operador; computador local ativo para coleta"],
                    ["Envio e confirmação acadêmica", "Pedro ou integrante designado"]], [235, WIDTH - 235]),
                p("Não há cadastro, CPF, telefone, geolocalização ou histórico de conversa. O usuário "
                  "é orientado a não enviar dados pessoais, mas texto livre pode contê-los; processamento "
                  "transitório continua sendo tratamento. Ausência de banco não implica ausência de dados."),
                p("Access logs de Uvicorn/Caddy desabilitados. Métricas têm rótulos controlados, sem "
                  "pergunta/IP/linha. Logs técnicos são rotacionados e precisam de inspeção. Evidências "
                  "não incluem tokens, perguntas pessoais, payloads protegidos ou state."),
                p(location_text +
                  ("A Azure da IA permanece no Chile, em implantação separada. " if self.is_aws else "Brasil Sul foi descartado por restrições de SKU. ") +
                  "Verificar fluxos de metadados, "
                  "controle e contratos; não prometer residência integral por inferência."),
                p("Antes de uso ampliado com dados pessoais, definir finalidade, base legal, aviso, "
                  "canal de direitos, retenção e eventual mecanismo de transferência internacional. "
                  "A arquitetura acadêmica não constitui certificação LGPD."),
                p(self.link("Responsabilidade compartilhada AWS" if self.is_aws else "Responsabilidade compartilhada Microsoft",
                            AWS_SOURCES[7][1] if self.is_aws else SOURCES[7][1]) + "<br/>" +
                  self.link("ANPD: transferência internacional", SOURCES[8][1]), "small", markup=True),
                p("Sessão AWS temporária e SecureString não eliminam o acesso administrativo do "
                  "perfil Lab e do SSM. Não criar IAM fora das permissões do curso; proteger environment, "
                  "secrets, parâmetros e saídas. A exclusão no fim da sessão não comprova remoção de "
                  "todas as cópias ou logs do provedor.") if self.is_aws else
                p("Segredos ficam no servidor e no canal de configuração autorizado. OIDC evita "
                  "uma senha duradoura Azure; não elimina a necessidade de proteger branch, environment, "
                  "contas e o poder administrativo do Run Command.")]

        sec = self.section("09 / Sessão, custo e manutenção" if self.is_aws else "09 / Crédito e manutenção",
                           "Academy: tempo de sessão, créditos CPU e preço de referência são grandezas distintas" if self.is_aws else
                           "R$0 desembolsado é a intenção; consumo de crédito precisa ser acompanhado")
        cost = self.data.get("costs", {})
        cost = cost if isinstance(cost, dict) else {}
        def money(key):
            number = cost.get(key)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                return "PENDENTE"
            return f"US${number:.4f}"
        if self.is_aws:
            sec += self.aws_costs_and_session(cost, money)
        else:
            sec += [p("Azure for Students oferece US$100 por 12 meses a elegíveis, sem cartão. A conta "
                      "acadêmica foi ativada segundo a verificação do operador; acompanhar saldo e "
                      "spending limit durante toda a correção. Crédito expirado/esgotado "
                      "pode desabilitar o serviço. Não remover o limite nem converter para plano pago."),
                    self.table([["Cotação regional registrada", "Valor"],
                        ["Região / consulta", escape(clean(cost.get("region"), 70) + " / " + clean(cost.get("checked_at"), 70))],
                        ["Período em horas", escape(clean(cost.get("hours"), 30))],
                        ["VM por hora", money("vm_hourly_usd")],
                        ["IPv4 por hora", money("ip_hourly_usd")],
                        ["SSD por mês", money("disk_monthly_usd")],
                        ["Total estimado de crédito", money("total_estimate_usd")]], [290, WIDTH - 290]),
                    p("Estimativa selecionada: chilecentral / 216 h (9 dias) / VM US$0,0526/h "
                      "+ IP US$0,005/h + SSD US$3,36/mês = US$13,4496 de crédito (~US$13,45). "
                      "Disco proporcional por mês de 30 dias. Consulta Retail API em 19/11/2026. "
                      "Operações SSD US$0,0028/10 mil, egress e duração maior alteram o total; "
                      "estimativa não é gasto realizado.", "small"),
                    p("Manter até 27/11/2026", "h2"),
                    p("Aplicação, repositório e evidências acessíveis até pelo menos 27/11/2026 às 23h55 "
                      "de São Paulo, confirmando fim da correção antes de encerrar. Não há desligamento "
                      "automático. Verificar saldo/expiração, disco, readiness, créditos de CPU e alertas."),
                    p("B2als_v2 compartilha capacidade burstable; créditos esgotados podem aumentar a "
                      "latência. Manter monitoramento local ativo e registrar lacunas. Ao encerrar, somente "
                      "após liberação: preservar evidências/backup cifrado, revisar destroy, remover recursos "
                      "acadêmicos e revogar federação/segredos. Parar a VM não remove custo de disco/IP."),
                    p(self.link("Preços oficiais Microsoft", SOURCES[3][1]) + " | " +
                      self.repo_link("Planilha textual e operação", "infra/OPERACAO.md"), "small", markup=True)]

        sec = self.section("10 / Matriz de evidências", "O manifesto é um índice revisável; arquivos precisam de inspeção humana")
        rows = [["Verificação", "Situação registrada", "Escopo / data"]]
        for key, label in CHECKS:
            record = self.record(key)
            rows.append([label, escape(self.status(record)),
                         escape(SCOPE.get(record.get("scope"), "PENDENTE") + " / " + clean(record.get("checked_at"), 65))])
        sec += [self.table(rows, [155, 155, WIDTH - 310]),
                Spacer(1, 8), self.table([["Rubrica", "Peso", "Critério de evidência"],
                    ["Containers", "2", "Build, não root, healthcheck, inferência e reinício"],
                    ["Terraform", "3", "Apply, recursos/rede e state protegido, sanitizados"],
                    ["CI/CD seguro", "4", "Runs barrado/aprovado, commits e deploy controlado"],
                    ["Observabilidade", "3", "Quatro valores, alvo, janela, firing e recuperação"],
                    ["Documentação", "2", "Ficha, arquitetura, reprodução, links e PDF revisado"]], [120, 45, WIDTH - 165]),
                p("VALIDADO exige no manifesto status passed, escopo, data e referência existente "
                  "ou URL. A presença da referência não autentica seu conteúdo. LOCAL e CONFIGURAÇÃO "
                  "não são prova PÚBLICA. Campos incompletos aparecem PENDENTE; não se calcula nota "
                  "automática nem se presume atendimento integral.", "small")]
        if self.manifest_path.is_file():
            digest = sha256(self.manifest_path.read_bytes()).hexdigest()
            sec.append(p("Manifesto usado / SHA-256: " + digest, "small"))
            if public_url(self.data.get("manifest_url")):
                sec.append(p(self.link("Abrir o manifesto desta entrega", self.data["manifest_url"]),
                             "small", markup=True))
        else:
            sec.append(p("Manifesto selecionado ausente. Nenhuma validação foi inferida.", "small"))

        sec = self.section("11 / Entrega e referências", "Reprodução e rastreabilidade para quem avalia")
        sec += [p("Prazo publicado: 19/11/2026 às 23h55, America/Sao_Paulo. O material oficial "
                  "traz 10 pontos/Teams na regra geral p.24 e 14 pontos/portal na rubrica Cloud "
                  "p.52-53. A divergência fica registrada; confirmar o canal institucional. "
                  "Pedro/equipe realizam o envio. Preparação técnica não comprova submissão."),
                p("Conferir antes de enviar: URL abre externamente; mesma revisão e LLM; modo demo "
                  "identificado; pipeline e evidências sem segredo; métricas com amostras; alerta e "
                  "recuperação; PDF renderizado e legível. Pendências não devem ser ocultadas."),
                p("Entrega Cloud: AWS Sandbox, conforme aceite do professor relatado por Pedro. "
                  "Registrar a janela de acesso temporário e a necessidade de nova sessão para "
                  "reproduzir. A URL Azure da IA preserva acesso ao produto, mas não substitui provas "
                  "de infraestrutura/deploy/alerta AWS.", "small") if self.is_aws else
                p("Este documento preserva a implantação Azure da IA. A entrega Cloud em AWS precisa "
                  "usar seu manifesto próprio; não alterar o provedor das provas históricas.", "small"),
                p(self.repo_link("Documento Cloud e operação", "docs/CLOUD-AWS.md" if self.is_aws else "docs/CLOUD.md") + "<br/>" +
                  self.repo_link("Estado operacional", "docs/STATUS-CLOUD.md") + "<br/>" +
                  self.repo_link("Gerador reproduzível deste PDF", "scripts/build-cloud-pdf.py"), "small", markup=True),
                p("Fontes oficiais", "h2")]
        source_rows = []
        for index in range(0, len(self.sources), 2):
            source_rows.append([self.link(*self.sources[index]),
                                self.link(*self.sources[index + 1]) if index + 1 < len(self.sources) else "&#160;"])
        sec += [self.table(source_rows, [WIDTH / 2, WIDTH / 2], header=False),
                p("Documento institucional: Desafio-FIAP-GS-CitizenTech 4ES.pdf, p.18-25 (Ficha/regras), "
                  "p.28-31 (IA), p.51-53 (Cloud), preservado na pasta FIAP. Links técnicos foram "
                  "consultados em 19/11/2026; verificar mudanças ao reproduzir.", "small"),
                p("A geração lê somente campos permitidos do manifesto e imagens locais existentes. "
                  "Não usa rede, Git, cloud ou cofre. Prints locais são identificados; ausências não "
                  "recebem imagens fictícias. Atualizar manifesto, gerar novamente e revisar visualmente.", "small")]
        return self.sections

    def decorate(self, canv, doc):
        canv.saveState()
        page_width, page_height = canv._pagesize
        canv.setStrokeColor(TEAL)
        canv.setLineWidth(2)
        canv.line(44, page_height - 36, page_width - 44, page_height - 36)
        canv.setFont(self.bold_font, 8)
        canv.setFillColor(INK)
        canv.drawString(44, page_height - 27, "PONTO CERTO")
        canv.setFont(self.body_font, 8)
        canv.setFillColor(MUTED)
        canv.drawRightString(page_width - 44, page_height - 27, "FIAP / CLOUD / " + self.provider.upper() + " / 2026.2")
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.5)
        canv.line(44, 37, page_width - 44, 37)
        canv.setFont(self.body_font, 7.5)
        canv.drawString(44, 24, f"v{VERSION} | revisão {self.revision[:12]} | evidência ≠ configuração".replace("≠", "não é"))
        canv.drawRightString(page_width - 44, 24, f"{doc.page:02d}")
        canv.restoreState()

    def write(self, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        rl_config.invariant = True
        story = []
        for index, section in enumerate(self.build_sections()):
            if index:
                story.append(PageBreak())
            story.extend(section)
        if self.appendices:
            story.extend([NextPageTemplate("landscape"), PageBreak()])
            for index, item in enumerate(self.appendices):
                if index:
                    story.append(PageBreak())
                story.append(EvidenceAppendix(self, item))
        document = BaseDocTemplate(str(destination), pagesize=A4, leftMargin=44,
            rightMargin=44, topMargin=59, bottomMargin=49, title="Ponto Certo - Deploy Blindado",
            author="Equipe Ponto Certo / Pedro Henrique Salvitti Habiro",
            subject="Cloud Computing: configuração e evidências registradas", pageCompression=1)
        portrait_frame = Frame(44, 49, WIDTH, A4[1] - 59 - 49,
            id="portrait-content", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        landscape_frame = Frame(44, 43, APPENDIX_WIDTH, APPENDIX_HEIGHT,
            id="landscape-capture", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        document.addPageTemplates([
            PageTemplate(id="portrait", frames=[portrait_frame], pagesize=A4, onPage=self.decorate),
            PageTemplate(id="landscape", frames=[landscape_frame], pagesize=LANDSCAPE, onPage=self.decorate),
        ])
        document.build(story, canvasmaker=partial(canvas.Canvas, invariant=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "evidencias/cloud/manifest.json",
                        help="Use evidencias/aws/manifest.json for AWS; default preserves the Azure IA checkpoint")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Validate inputs, without creating a PDF")
    args = parser.parse_args()
    report = Report(args.manifest.resolve())
    if args.check:
        sections = report.build_sections()
        print(json.dumps({"manifest_present": args.manifest.is_file(),
                          "provider": report.provider,
                          "sections": len(sections), "team_members": len(report.team),
                          "landscape_appendices": len(report.appendices),
                          "captures": [{"key": item["key"], "pixels": item["pixels"],
                                        "scope": item["scope"]} for item in report.appendices],
                          "statuses": {key: report.status(report.record(key)) for key, _ in CHECKS},
                          "pdf_created": False}, ensure_ascii=False, indent=2))
        return
    report.write(args.output.resolve())
    print(str(args.output.resolve()))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("Não foi possível gerar o documento: " + str(error), file=sys.stderr)
        sys.exit(1)
