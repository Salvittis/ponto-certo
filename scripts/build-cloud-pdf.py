#!/usr/bin/env python3
"""Build the Cloud report from configuration and explicitly recorded evidence.

No network, Git, cloud or secret-store calls. Missing evidence stays PENDENTE.
Use --check to validate inputs without creating a PDF. Requires reportlab/Pillow.
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
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
DOCUMENT_DATE = "19/11/2026"
DEFAULT_REPO = "https://github.com/Salvittis/ponto-certo"
DEFAULT_OUTPUT = ROOT / "output/pdf/Ponto-Certo-Deploy-Blindado.pdf"
INK = colors.HexColor("#102A43")
TEAL = colors.HexColor("#007F83")
MUTED = colors.HexColor("#536575")
PALE = colors.HexColor("#EAF5F4")
LINE = colors.HexColor("#D8E3E8")
AMBER = colors.HexColor("#9B5B00")
WIDTH = A4[0] - 88
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


class Report:
    def __init__(self, manifest_path):
        self.manifest_path = manifest_path
        self.data = read_json(manifest_path)
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
        }
        self.sections = []
        self.team = self.read_team()

    def read_team(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        matches = re.findall(r"^\|\s*([^|\n]+?)\s*\|\s*(RM\d+)\s*\|", readme, re.M)
        if not matches:
            raise ValueError("Ficha Técnica sem nomes/RMs no README; não serão inventados")
        return [(name.strip(), rm.strip()) for name, rm in matches]

    def p(self, text, style="body", markup=False):
        value = clean(text)
        return Paragraph(value if markup else escape(value), self.styles[style])

    def link(self, label, url):
        safe = public_url(url)
        if not safe:
            return escape(clean(label)) + " (PENDENTE)"
        return f'<link href="{escape(safe, quote=True)}" color="#007F83">{escape(clean(label))}</link>'

    def repo_link(self, label, path):
        return self.link(label, f"{self.repo}/blob/{self.ref}/{quote(path, safe='/')}")

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
                links.append((rel, f"{self.repo}/blob/{self.ref}/{quote(rel, safe='/')}"))
        return links

    def status(self, record):
        raw = str(record.get("status", "pending")).lower()
        scope = SCOPE.get(record.get("scope"))
        documented = bool(scope and record.get("checked_at") and self.references(record))
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

    def screenshot(self, key, max_height=150):
        shots = self.data.get("screenshots", {})
        item = shots.get(key, {}) if isinstance(shots, dict) else {}
        if isinstance(item, str):
            item = {"path": item}
        if not isinstance(item, dict):
            return self.p("Captura PENDENTE: " + key + ". Nenhum espaço de imagem é reservado.", "small")
        path = local_file(item.get("path"))
        if not path or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            return self.p("Captura PENDENTE: " + key + ".", "small")
        scope = SCOPE.get(item.get("scope"), "ESCOPO NÃO INFORMADO")
        caption = f"{scope} | {clean(item.get('caption', key), 420)} | {path.relative_to(ROOT)}"
        return self.image(path, caption, max_height)

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
        diagram.add(Rect(122, 12, WIDTH - 123, 132, rx=9, ry=9,
                         fillColor=colors.HexColor("#F5F8FA"), strokeColor=LINE))
        diagram.add(String(134, 127, "VM Azure proposta / fronteira de rede", fontName=self.bold_font,
                           fontSize=9, fillColor=INK))
        box(0, 59, 102, 53, "Navegador", "Internet / HTTPS")
        box(133, 59, 108, 53, "Caddy", "80/443 no host")
        box(262, 59, 108, 53, "FastAPI", "8000 / não root")
        box(391, 59, WIDTH - 392, 53, "Qwen local", "8081 / privada")
        arrow(102, 85, 133, 85)
        arrow(241, 85, 262, 85)
        arrow(370, 85, 391, 85)
        box(0, 153, 225, 48, "GitHub Actions / GHCR", "Gates → digest aprovado → OIDC".replace("→", ">"))
        box(272, 153, WIDTH - 272, 48, "Prometheus / Grafana locais", "HTTPS /metrics + Bearer; /readyz")
        arrow(187, 153, 187, 144)
        arrow(316, 153, 316, 144)
        diagram.add(String(135, 28, "NSG: só 80/443. Sem SSH, Docker socket ou LLM públicos.",
                           fontName=self.body_font, fontSize=8.3, fillColor=MUTED))
        return diagram

    def build_sections(self):
        p = self.p
        sec = self.section("Ficha Técnica", "PONTO CERTO / DEPLOY BLINDADO / CLOUD COMPUTING")
        sec += [p("Informação de ônibus com evidência, IA local e uma publicação verificável."),
                self.table([["Campo", "Definição"],
                    ["Produto / território", "Ponto Certo / ônibus municipais de São Paulo"],
                    ["Cidadão / problema", "Pessoas que dependem do ônibus; espera e informação incerta"],
                    ["Disciplina", "Secure DevOps Tools &amp; Cloud Computing / FIAP / CitizenTech 2026.2"],
                    ["Arquitetura", "FastAPI + recuperação e consultas controladas + Qwen local + Caddy"],
                    ["Fontes / modo", "SPTrans e base documental; demonstração sintética, live depende de token"],
                    ["ODS / impacto", "ODS 11 / contribuição proposta; redução de espera não medida"]], [127, WIDTH - 127]),
                Spacer(1, 10), self.table([["Integrante", "RM"], *[[escape(a), b] for a, b in self.team]], [WIDTH - 90, 90]),
                p("Responsável por IA e Cloud: Pedro Henrique Salvitti Habiro.", "small"),
                p(self.link("Repositório e código", self.repo) + "<br/>" +
                  (self.link("MVP público: " + self.url, self.url) if self.url else "MVP público: <b>PENDENTE</b>"), markup=True),
                p(f"Documento v{VERSION} | {DOCUMENT_DATE}. Evidências atualizadas: {self.updated}.<br/>"
                  f"Revisão Git registrada: {self.revision}.", "small", markup=True),
                p("Uma URL registrada não comprova disponibilidade. O manifesto distingue configuração, "
                  "teste local e execução pública; lacunas permanecem PENDENTE.", "small")]

        sec = self.section("01 / Arquitetura da mesma IA", "Configuração de publicação, sem trocar a aplicação avaliada")
        sec += [self.architecture(), Spacer(1, 8),
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

        sec = self.section("02 / Containers e integração", "Rubrica: 2 pontos / configuração e execução são registros distintos")
        sec += [self.table([["Controle", "Implementação"],
                    ["Usuário", "App e LLM: UID/GID 10001; proxy não root. Daemon Docker do host continua privilegiado."],
                    ["Imutabilidade", "Bases por digest; pesos por revisão/SHA-256; filesystem read-only e tmpfs limitado."],
                    ["Isolamento", "cap_drop ALL, no-new-privileges; LLM privada; sem socket Docker nos containers."],
                    ["Recursos", "LLM 3 GiB, app 512 MiB, proxy 128 MiB; limites não reservam recursos nem eliminam OOM."],
                    ["Reinício", "unless-stopped; pesos na imagem e certificados persistentes. Healthchecks + readiness + smoke."],
                    ["Segredos", "Runtime protegido; nenhum token em imagem, repositório, cloud-init ou state."]], [100, WIDTH - 100]),
                self.evidence_note("docker")]
        smoke = read_json(ROOT / "evidencias/cloud/smoke-compose.json")
        if smoke:
            checks = smoke.get("checks", [])
            checks = checks if isinstance(checks, list) else []
            passed = sum(item.get("passed") is True for item in checks if isinstance(item, dict))
            sec.append(p(f"Smoke Compose LOCAL registrado: {passed}/{len(checks)} checks; "
                         f"alvo {clean(smoke.get('base_url'), 90)}; "
                         f"horário {clean(smoke.get('finished_at'), 70)}. "
                         "Não comprova URL pública nem desempenho Azure.", "small"))
        shot = local_file("evidencias/interface-chegada.jpg")
        if shot:
            sec.append(self.image(shot, "IA real local / dados demo. Captura de chegada simulada; "
                                  "não é evidência de SPTrans ao vivo nem de nuvem.", 145))
        sec.append(p(self.repo_link("Compose produção", "compose.production.yaml") + " | " +
                     self.repo_link("Dockerfile app", "Dockerfile") + " | " +
                     self.repo_link("Dockerfile modelo", "Dockerfile.llm"), "small", markup=True))

        sec = self.section("03 / Terraform e acesso", "Rubrica: 3 pontos / fronteira administrativa restrita")
        provisioning = self.data.get("provisioning", {})
        provisioning = provisioning if isinstance(provisioning, dict) else {}
        sec += [p("Provisionamento: " + self.status(provisioning), "h2"),
                p("Região registrada: " + clean(provisioning.get("region"), 80) +
                  ". SKU: " + clean(provisioning.get("vm_size"), 80) +
                  ". Conclusão do apply conforme o status acima.", "small"),
                p("Seleção: Chile Central (chilecentral). SKU/quota passaram no preflight; plano "
                  "de 12 criações revisado e apply iniciado. Só seu resultado comprova alocação. Terraform cria "
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
                  "de CI. State local é texto: FileVault e backup cifrado protegem o disco. O lock é local "
                  "e há um único operador; sensitive não cifra valores."),
                p("O environment GitHub deve restringir branch main. Com environment, o subject OIDC "
                  "não inclui branch: essa regra não é garantida só pelo Terraform. Run Command "
                  "continua sendo administração do host, mesmo com RBAC restrito.", "small"),
                self.evidence_note("terraform"),
                p(self.repo_link("Operação, pré-requisitos e state", "infra/OPERACAO.md"), "small", markup=True)]

        sec = self.section("04 / Pipeline que bloqueia", "Rubrica: 4 pontos / CI executa em push e pull request")
        sec += [p("Gitleaks (histórico) + Semgrep (política) + testes + build/Trivy (app e LLM) + "
                  "Trivy (Caddy). Os gates são dependências da publicação; severidade HIGH/CRITICAL e "
                  "segredos barram as imagens. Ações e versões são fixadas."),
                p("Push na main publica os mesmos arquivos de imagem examinados, sem rebuild. O GHCR "
                  "fornece os digests de app, LLM e proxy; production usa OIDC e Managed Run Command. "
                  "Depois, o job verifica TLS, revisão, prontidão e smoke com LLM real."),
                p("Não se presume GHCR público. Pull privado usa GITHUB_TOKEN efêmero com packages: read, "
                  "parâmetro protegido e login Docker temporário removido ao final. O código público "
                  "permite reprodução por build das fontes.", "small"),
                p("Ensaio: fixture sintética nunca executada introduz eval; Semgrep deve barrar o commit "
                  "e impedir deploy. Remover a fixture e repetir a mesma política deve aprovar a correção. "
                  "Não usar segredo real, desabilitar scanner ou abrandar severidade."),
                self.evidence_note("ci_block"), self.screenshot("pipeline_block", 120),
                self.evidence_note("ci_pass"), self.screenshot("pipeline_pass", 120),
                p(self.repo_link("Workflow e gates", ".github/workflows/devsecops.yml") + " | " +
                  self.repo_link("Ensaio controlado", "scripts/security-demo.py"), "small", markup=True)]

        sec = self.section("05 / Quatro métricas de ouro", "Rubrica: 3 pontos com alerta / medir a mesma URL publicada")
        metrics = self.data.get("metrics", {})
        metrics = metrics if isinstance(metrics, dict) else {}
        def measured(key, unit):
            value = metrics.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
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
                p(self.repo_link("PromQL, configuração e limites", "docs/OBSERVABILIDADE.md"), "small", markup=True)]

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
                    ["Datacenter, host físico, virtualização", "Microsoft na oferta IaaS"],
                    ["Identidade, NSG, SO, patches, Docker", "Equipe / Pedro, operador IA e Cloud"],
                    ["Aplicação, modelo, dados, segredos", "Equipe / Pedro; validação e correção do sistema"],
                    ["Monitoramento, restore e evidências", "Operador; computador local ativo para coleta"],
                    ["Envio e confirmação acadêmica", "Pedro ou integrante designado"]], [235, WIDTH - 235]),
                p("Não há cadastro, CPF, telefone, geolocalização ou histórico de conversa. O usuário "
                  "é orientado a não enviar dados pessoais, mas texto livre pode contê-los; processamento "
                  "transitório continua sendo tratamento. Ausência de banco não implica ausência de dados."),
                p("Access logs de Uvicorn/Caddy desabilitados. Métricas têm rótulos controlados, sem "
                  "pergunta/IP/linha. Logs técnicos são rotacionados e precisam de inspeção. Evidências "
                  "não incluem tokens, perguntas pessoais, payloads protegidos ou state."),
                p("Localização registrada no manifesto: " + clean(provisioning.get("region"), 80) +
                  ". Seleção atual: Chile Central, fora do Brasil. Confirmar a alocação no apply; "
                  "Brasil Sul foi descartado por restrições de SKU. Verificar fluxos de metadados, "
                  "controle e contratos; não prometer residência integral por inferência."),
                p("Antes de uso ampliado com dados pessoais, definir finalidade, base legal, aviso, "
                  "canal de direitos, retenção e eventual mecanismo de transferência internacional. "
                  "A arquitetura acadêmica não constitui certificação LGPD."),
                p(self.link("Responsabilidade compartilhada Microsoft", SOURCES[7][1]) + "<br/>" +
                  self.link("ANPD: transferência internacional", SOURCES[8][1]), "small", markup=True),
                p("Segredos ficam no servidor e no canal de configuração autorizado. OIDC evita "
                  "uma senha duradoura Azure; não elimina a necessidade de proteger branch, environment, "
                  "contas e o poder administrativo do Run Command.")]

        sec = self.section("09 / Crédito e manutenção", "R$0 desembolsado é a intenção; consumo de crédito precisa ser acompanhado")
        cost = self.data.get("costs", {})
        cost = cost if isinstance(cost, dict) else {}
        def money(key):
            number = cost.get(key)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                return "PENDENTE"
            return f"US${number:.4f}"
        sec += [p("Azure for Students oferece US$100 por 12 meses a elegíveis, sem cartão. A conta "
                  "acadêmica foi ativada segundo a verificação do operador; saldo/spending limit "
                  "e capacidade devem ser confirmados antes do apply. Crédito expirado/esgotado "
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
        else:
            sec.append(p("Manifesto ausente: evidencias/cloud/manifest.json. Nenhuma validação foi inferida.", "small"))

        sec = self.section("11 / Entrega e referências", "Reprodução e rastreabilidade para quem avalia")
        sec += [p("Prazo publicado: 19/11/2026 às 23h55, America/Sao_Paulo. O material oficial "
                  "traz 10 pontos/Teams na regra geral p.24 e 14 pontos/portal na rubrica Cloud "
                  "p.52-53. A divergência fica registrada; confirmar o canal institucional. "
                  "Pedro/equipe realizam o envio. Preparação técnica não comprova submissão."),
                p("Conferir antes de enviar: URL abre externamente; mesma revisão e LLM; modo demo "
                  "identificado; pipeline e evidências sem segredo; métricas com amostras; alerta e "
                  "recuperação; PDF renderizado e legível. Pendências não devem ser ocultadas."),
                p(self.repo_link("Documento Cloud e esquema do manifesto", "docs/CLOUD.md") + "<br/>" +
                  self.repo_link("Estado operacional", "docs/STATUS-CLOUD.md") + "<br/>" +
                  self.repo_link("Gerador reproduzível deste PDF", "scripts/build-cloud-pdf.py"), "small", markup=True),
                p("Fontes oficiais", "h2")]
        source_rows = []
        for index in range(0, len(SOURCES), 2):
            source_rows.append([self.link(*SOURCES[index]), self.link(*SOURCES[index + 1])])
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
        canv.setStrokeColor(TEAL)
        canv.setLineWidth(2)
        canv.line(44, A4[1] - 36, A4[0] - 44, A4[1] - 36)
        canv.setFont(self.bold_font, 8)
        canv.setFillColor(INK)
        canv.drawString(44, A4[1] - 27, "PONTO CERTO")
        canv.setFont(self.body_font, 8)
        canv.setFillColor(MUTED)
        canv.drawRightString(A4[0] - 44, A4[1] - 27, "FIAP / CLOUD / 2026.2")
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.5)
        canv.line(44, 37, A4[0] - 44, 37)
        canv.setFont(self.body_font, 7.5)
        canv.drawString(44, 24, f"v{VERSION} | revisão {self.revision[:12]} | evidência ≠ configuração".replace("≠", "não é"))
        canv.drawRightString(A4[0] - 44, 24, f"{doc.page:02d}")
        canv.restoreState()

    def write(self, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        rl_config.invariant = True
        story = []
        for index, section in enumerate(self.build_sections()):
            if index:
                story.append(PageBreak())
            story.extend(section)
        document = SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=44,
            rightMargin=44, topMargin=59, bottomMargin=49, title="Ponto Certo - Deploy Blindado",
            author="Equipe Ponto Certo / Pedro Henrique Salvitti Habiro",
            subject="Cloud Computing: configuração e evidências registradas", pageCompression=1)
        document.build(story, onFirstPage=self.decorate, onLaterPages=self.decorate,
                       canvasmaker=partial(canvas.Canvas, invariant=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "evidencias/cloud/manifest.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Validate inputs, without creating a PDF")
    args = parser.parse_args()
    report = Report(args.manifest.resolve())
    if args.check:
        sections = report.build_sections()
        print(json.dumps({"manifest_present": args.manifest.is_file(),
                          "sections": len(sections), "team_members": len(report.team),
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
