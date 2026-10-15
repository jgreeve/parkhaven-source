"""Build the ParkHaven progress presentation and four-minute speaker script."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "ParkHaven-progress-presentation.pptx"
SCRIPT_OUTPUT = ROOT / "artifacts" / "ParkHaven-4-minute-script.md"
LOGO = ROOT / "app" / "static" / "parkhaven-logo.png"
CAPTURE_ROOT = (
    Path.home()
    / "AppData/Local/Temp/opencode/parkhaven-import-ilpgfpi0"
    / "9ff5fac1-3ab1-4ecf-86fe-cc256b7faa9f/runs"
    / "1c1c2520-366b-4f43-8cc4-3aee71a0f03e/data/view-evidence"
    / "6b3cb532-cc88-468c-beb9-42e7b4bf583f"
)

W, H = Inches(13.333), Inches(7.5)
TEAL = "163A3B"
INK = "18352F"
GREEN = "1F684E"
MID_GREEN = "52966A"
MINT = "B7E6C8"
PAPER = "F8FAF6"
BG = "ECEFE9"
LINE = "D5DDD6"
MUTED = "687B75"
ORANGE = "D9683F"
GOLD = "D7A35D"
BLUE = "2F80ED"
PURPLE = "9B51E0"
SOFT_BLUE = "548093"
WHITE = "FFFFFF"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def rect(slide, x, y, w, h, fill, line=None, radius=False):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.color.rgb = rgb(line or fill)
    if radius:
        shape.adjustments[0] = 0.08
    return shape


def text(slide, value, x, y, w, h, size=18, color=INK, bold=False,
         font="Segoe UI", align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP,
         margin=0, tracking=None):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.margin_left = frame.margin_right = Inches(margin)
    frame.margin_top = frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = value
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    if tracking is not None:
        run.font._element.set("spc", str(tracking))
    return box


def rich_text(slide, runs, x, y, w, h, size=18, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.margin_left = frame.margin_right = 0
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    for value, run_color, bold in runs:
        run = paragraph.add_run()
        run.text = value
        run.font.name = "Segoe UI"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(run_color or color)
    return box


def title(slide, kicker, heading, number):
    text(slide, kicker.upper(), 0.62, 0.35, 7.7, 0.3, 9, MUTED, True)
    text(slide, heading, 0.62, 0.70, 11.8, 0.68, 27, INK, True)
    text(slide, f"0{number}", 12.15, 0.40, 0.55, 0.28, 9, MUTED, True, align=PP_ALIGN.RIGHT)
    rect(slide, 0.62, 1.45, 12.08, 0.015, LINE)


def footer(slide):
    slide.shapes.add_picture(str(LOGO), Inches(0.62), Inches(6.96), height=Inches(0.37))
    rich_text(slide, [("PARKHAVEN ", INK, True), ("STUDIO", MUTED, False)],
              1.02, 7.03, 2.2, 0.2, 8)
    text(slide, "LOCAL • TRACEABLE • MODEL-GROUNDED", 9.25, 7.03, 3.45, 0.2,
         7, MUTED, True, align=PP_ALIGN.RIGHT)


def add_notes(slide, script):
    slide.notes_slide.notes_text_frame.text = script


def arrow(slide, x1, y1, x2, y2, color=GREEN, width=2.2):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    line.line.color.rgb = rgb(color)
    line.line.width = Pt(width)
    line.line.end_arrowhead = True
    return line


def step_card(slide, x, number, label, detail, color):
    rect(slide, x, 2.15, 2.12, 2.55, PAPER, LINE, True)
    rect(slide, x + 0.18, 2.34, 0.5, 0.5, color, color, True)
    text(slide, f"{number:02d}", x + 0.18, 2.43, 0.5, 0.18, 9, WHITE, True,
         align=PP_ALIGN.CENTER)
    text(slide, label, x + 0.18, 3.02, 1.76, 0.48, 17, INK, True)
    text(slide, detail, x + 0.18, 3.63, 1.76, 0.72, 10, MUTED)
    rect(slide, x + 0.18, 4.43, 0.66, 0.055, color)


def metric_card(slide, x, y, w, label, value, unit, accent=GREEN):
    rect(slide, x, y, w, 1.05, PAPER, LINE, True)
    text(slide, label.upper(), x + 0.18, y + 0.16, w - 0.36, 0.2, 8, MUTED, True)
    rich_text(slide, [(value, INK, True), (unit, MUTED, False)],
              x + 0.18, y + 0.45, w - 0.36, 0.38, 19)
    rect(slide, x, y, 0.055, 1.05, accent)


scripts = [
    """ParkHaven Studio turns a Rhino massing model into a traceable design review. The goal is not to replace the designer. It is to connect geometry, repeatable Grasshopper calculations, clear visual evidence, and bounded AI advice in one local workflow. The current prototype already handles a real Parkhaven model, produces controlled views and metrics, and exports an English PDF report. Everything shown today runs around Rhino 8 on the designer's Windows workstation.""",
    """The workflow has five controlled steps. First, the designer imports a 3DM file. The app hashes and preserves that source, then works only on a copy. Second, the designer positions the model and approves its units. Third, Rhino and Grasshopper run the analysis. Fourth, the app captures four standardized model views and combines those with calculated metrics for optional AI review. Finally, the app builds a printable report. Each transition has a gate, so incomplete placement, stale evidence, or failed analysis cannot silently flow into the final output.""",
    """The architecture is intentionally local-first. The desktop shell starts an authenticated local backend. That backend creates an isolated run folder and launches Rhino visibly, using a packaged Grasshopper definition. Grasshopper writes the scene, geometry summary, and result JSON; the app verifies their hashes before displaying them. Only a bounded text evidence package can go to an OpenAI-compatible endpoint. The model images remain local. This separation makes it clear which values came from deterministic calculation and which statements are AI hypotheses.""",
    """This is the evidence layer from the real massa fase 2 model. The exporter gives each analytical mass a stable color: Volume A is blue, B orange, and C purple. The viewer then captures top, overview, facade-side, and park-side cameras at a fixed resolution. Analysis overlays are hidden in those evidence images so the masses remain readable, while the measured results stay available in the dashboard. The report uses the same color legend instead of floating point labels, which makes every referenced volume easy to identify across all views.""",
    """The analysis produces decision-ready screening metrics. In this run the gross floor area is about fifty-one thousand nine hundred square metres, visibility is twenty-four point five percent, and indicative cost is ninety-three point four million euros. The climate screen reports four point three mean sun hours and a maximum UTCI of eighteen point five degrees for one selected weather condition. Foundation screening estimates two hundred forty-nine load-based piles. These are transparent screening values, not final engineering design, and the report labels that limitation explicitly.""",
    """Trust controls are part of the product, not an afterthought. The original 3DM stays unchanged, and every run carries source, definition, weather, scene, and evidence hashes. A report only accepts advice tied to the current evidence and current policy version. We also found no authoritative plot, access, or tunnel envelope in the available data. Therefore the server rejects advice to shift, widen, set back, or rotate a mass. The AI can propose tests within the current footprint, but it cannot invent site clearance from an aerial photograph.""",
    """The current build has passed one hundred twenty-seven app tests, twenty-five analyzer tests, real Rhino acceptance, four controlled WebGL captures, installed-bundle smoke testing, and a two-page PDF review. The installer and report workflow are working end to end. The next major step is to add authoritative site constraints, followed by signed distribution and clean-machine acceptance. In short, ParkHaven Studio now provides a usable bridge from Rhino geometry to a review that is visual, measurable, and auditable.""",
]


def build() -> None:
    required = [LOGO, *(CAPTURE_ROOT / name for name in ("top.png", "overview.png", "facade-side.png", "park-side.png"))]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing presentation assets: " + ", ".join(missing))

    presentation = Presentation()
    presentation.slide_width = W
    presentation.slide_height = H
    blank = presentation.slide_layouts[6]

    # 1. Opening
    slide = presentation.slides.add_slide(blank)
    rect(slide, 0, 0, 13.333, 7.5, BG)
    slide.shapes.add_picture(str(CAPTURE_ROOT / "overview.png"), Inches(7.58), Inches(0),
                             width=Inches(5.753), height=Inches(7.5))
    rect(slide, 0, 0, 7.78, 7.5, TEAL)
    text(slide, "PROGRESS PRESENTATION / V0.1", 0.72, 0.55, 5.8, 0.3, 10, MINT, True)
    text(slide, "From Rhino model\nto grounded design.", 0.72, 1.38, 6.2, 1.85, 34, WHITE, True)
    text(slide, "How ParkHaven Studio works", 0.72, 3.58, 5.7, 0.4, 17, MINT)
    rect(slide, 0.72, 4.20, 1.05, 0.06, ORANGE)
    text(slide, "Local analysis • controlled evidence • bounded AI • printable report",
         0.72, 4.52, 5.9, 0.8, 13, WHITE)
    slide.shapes.add_picture(str(LOGO), Inches(5.88), Inches(5.38), height=Inches(1.52))
    text(slide, "4 MIN", 0.72, 6.73, 1.2, 0.2, 8, MINT, True)
    add_notes(slide, scripts[0])

    # 2. Workflow
    slide = presentation.slides.add_slide(blank)
    rect(slide, 0, 0, 13.333, 7.5, BG)
    title(slide, "End-to-end workflow", "One model, five controlled gates", 2)
    labels = [
        ("Import", "Preserve and hash the source 3DM", BLUE),
        ("Position", "Approve coordinates and model units", GOLD),
        ("Analyze", "Run Rhino + Grasshopper locally", GREEN),
        ("Evidence", "Capture views and bounded metrics", PURPLE),
        ("Report", "Review advice and export PDF", ORANGE),
    ]
    for index, (label, detail, color) in enumerate(labels):
        x = 0.62 + index * 2.45
        step_card(slide, x, index + 1, label, detail, color)
        if index < len(labels) - 1:
            arrow(slide, x + 2.12, 3.43, x + 2.39, 3.43, MUTED, 1.5)
    rect(slide, 0.62, 5.18, 12.08, 0.92, TEAL, TEAL, True)
    text(slide, "Every output is linked to the approved run. Stale or incomplete evidence stops here.",
         0.95, 5.47, 11.45, 0.28, 14, WHITE, True, align=PP_ALIGN.CENTER)
    footer(slide)
    add_notes(slide, scripts[1])

    # 3. Architecture
    slide = presentation.slides.add_slide(blank)
    rect(slide, 0, 0, 13.333, 7.5, BG)
    title(slide, "Local architecture", "Deterministic calculation, bounded interpretation", 3)
    nodes = [
        (0.72, 2.18, 2.15, "SOURCE", "Rhino .3dm", "unchanged + SHA-256", BLUE),
        (3.25, 2.18, 2.15, "DESKTOP APP", "Local backend", "isolated run folder", GREEN),
        (5.78, 2.18, 2.15, "CALCULATION", "Rhino + Grasshopper", "visible, repeatable solve", GOLD),
        (8.31, 2.18, 2.15, "EVIDENCE", "JSON + four views", "hash-linked artifacts", PURPLE),
        (10.84, 2.18, 1.78, "OUTPUT", "PDF review", "metrics + hypotheses", ORANGE),
    ]
    for x, y, width, kicker, heading, detail, accent in nodes:
        rect(slide, x, y, width, 1.62, PAPER, LINE, True)
        rect(slide, x, y, 0.055, 1.62, accent)
        text(slide, kicker, x + 0.18, y + 0.18, width - 0.36, 0.2, 8, accent, True)
        text(slide, heading, x + 0.18, y + 0.53, width - 0.36, 0.34, 14, INK, True)
        text(slide, detail, x + 0.18, y + 1.04, width - 0.36, 0.35, 9, MUTED)
    for x in (2.87, 5.40, 7.93, 10.46):
        arrow(slide, x, 2.99, x + 0.32, 2.99, MUTED, 1.5)
    rect(slide, 3.25, 4.46, 4.68, 1.18, TEAL, TEAL, True)
    text(slide, "AUTHORITATIVE", 3.53, 4.68, 1.25, 0.2, 8, MINT, True)
    text(slide, "Grasshopper metrics", 3.53, 5.03, 3.9, 0.3, 16, WHITE, True)
    rect(slide, 8.31, 4.46, 4.31, 1.18, PAPER, LINE, True)
    text(slide, "OPTIONAL AI", 8.59, 4.68, 1.2, 0.2, 8, ORANGE, True)
    text(slide, "Bounded text only — images stay local", 8.59, 5.03, 3.7, 0.3, 14, INK, True)
    arrow(slide, 7.93, 5.05, 8.25, 5.05, ORANGE, 1.5)
    footer(slide)
    add_notes(slide, scripts[2])

    # 4. Evidence views
    slide = presentation.slides.add_slide(blank)
    rect(slide, 0, 0, 13.333, 7.5, BG)
    title(slide, "Model evidence", "Stable colors replace floating labels", 4)
    slide.shapes.add_picture(str(CAPTURE_ROOT / "top.png"), Inches(0.62), Inches(1.78),
                             width=Inches(5.92), height=Inches(3.95))
    slide.shapes.add_picture(str(CAPTURE_ROOT / "overview.png"), Inches(6.78), Inches(1.78),
                             width=Inches(5.92), height=Inches(3.95))
    text(slide, "TOP VIEW", 0.82, 5.46, 1.4, 0.2, 8, WHITE, True)
    text(slide, "OVERVIEW", 6.98, 5.46, 1.4, 0.2, 8, WHITE, True)
    legend = [("Volume A", BLUE), ("Volume B", "F2994A"), ("Volume C", PURPLE)]
    for index, (label, color) in enumerate(legend):
        x = 0.72 + index * 1.62
        rect(slide, x, 6.08, 0.2, 0.2, color, color, True)
        text(slide, label, x + 0.28, 6.07, 1.12, 0.24, 10, INK, True)
    text(slide, "4 cameras • 768 × 512 • analysis overlays hidden", 7.52, 6.08, 5.08, 0.25,
         10, MUTED, True, align=PP_ALIGN.RIGHT)
    footer(slide)
    add_notes(slide, scripts[3])

    # 5. Results
    slide = presentation.slides.add_slide(blank)
    rect(slide, 0, 0, 13.333, 7.5, BG)
    title(slide, "Screening results", "Numbers for comparison, not final engineering", 5)
    metric_card(slide, 0.62, 1.78, 3.75, "Gross floor area", "51,868", " m²", GREEN)
    metric_card(slide, 4.55, 1.78, 3.75, "Visibility", "24.5", "%", BLUE)
    metric_card(slide, 8.48, 1.78, 4.22, "Indicative cost", "€ 93.4", " million", ORANGE)
    rect(slide, 0.62, 3.16, 6.0, 2.92, PAPER, LINE, True)
    text(slide, "CLIMATE SCREENING", 0.88, 3.43, 2.3, 0.22, 9, MUTED, True)
    climate = [("Mean sun hours", 4.3, 11.0, GOLD), ("Maximum UTCI", 18.5, 45.0, ORANGE),
               ("Sunlit area", 78.9, 100.0, GREEN)]
    for i, (label, value, maximum, color) in enumerate(climate):
        y = 3.92 + i * 0.62
        text(slide, label, 0.88, y, 1.55, 0.22, 10, INK, True)
        rect(slide, 2.55, y + 0.02, 2.84, 0.18, "E3E9E4", "E3E9E4", True)
        rect(slide, 2.55, y + 0.02, 2.84 * value / maximum, 0.18, color, color, True)
        text(slide, f"{value:g}" + (" h" if i == 0 else " °C" if i == 1 else "%"),
             5.47, y - 0.01, 0.8, 0.24, 10, color, True, align=PP_ALIGN.RIGHT)
    rect(slide, 6.88, 3.16, 5.82, 2.92, TEAL, TEAL, True)
    text(slide, "FOUNDATION SCREENING", 7.18, 3.43, 2.4, 0.22, 9, MINT, True)
    text(slide, "249", 7.18, 3.90, 2.1, 0.76, 35, WHITE, True)
    text(slide, "load-based piles", 7.18, 4.67, 2.2, 0.3, 13, MINT)
    rect(slide, 9.82, 3.94, 0.02, 1.36, "496766")
    text(slide, "6.0 m", 10.18, 3.94, 1.9, 0.45, 22, WHITE, True)
    text(slide, "grid centres", 10.18, 4.47, 1.9, 0.28, 11, MINT)
    text(slide, "INDICATIVE — requires engineering verification", 7.18, 5.51, 4.9, 0.22,
         8, "9DBDB5", True)
    footer(slide)
    add_notes(slide, scripts[4])

    # 6. Trust controls
    slide = presentation.slides.add_slide(blank)
    rect(slide, 0, 0, 13.333, 7.5, BG)
    title(slide, "Trust controls", "The app blocks unsupported conclusions", 6)
    controls = [
        ("SOURCE", "Original 3DM unchanged", "SHA-256 linked", BLUE),
        ("EVIDENCE", "Current run only", "scene + metrics + views", PURPLE),
        ("POLICY", "Site constraints unavailable", "no horizontal movement", ORANGE),
    ]
    for i, (kicker, heading, detail, color) in enumerate(controls):
        x = 0.62 + i * 4.04
        rect(slide, x, 1.86, 3.72, 1.45, PAPER, LINE, True)
        rect(slide, x, 1.86, 0.06, 1.45, color)
        text(slide, kicker, x + 0.24, 2.08, 1.2, 0.2, 8, color, True)
        text(slide, heading, x + 0.24, 2.46, 3.18, 0.3, 15, INK, True)
        text(slide, detail, x + 0.24, 2.90, 3.18, 0.2, 9, MUTED)
    text(slide, "AI PROPOSAL", 0.82, 4.02, 1.7, 0.22, 9, MUTED, True)
    rect(slide, 0.62, 4.36, 3.12, 1.02, PAPER, LINE, True)
    text(slide, "“Shift Volume A toward the tunnel”", 0.87, 4.68, 2.62, 0.34, 13, INK, True)
    arrow(slide, 3.75, 4.87, 4.55, 4.87, ORANGE, 2.2)
    rect(slide, 4.58, 4.20, 2.36, 1.34, ORANGE, ORANGE, True)
    text(slide, "BLOCKED", 4.78, 4.52, 1.96, 0.3, 20, WHITE, True, align=PP_ALIGN.CENTER)
    text(slide, "no verified envelope", 4.78, 4.95, 1.96, 0.22, 9, WHITE, False, align=PP_ALIGN.CENTER)
    arrow(slide, 6.95, 4.87, 7.74, 4.87, GREEN, 2.2)
    rect(slide, 7.78, 4.36, 4.92, 1.02, TEAL, TEAL, True)
    text(slide, "Allowed: test changes within the current footprint", 8.08, 4.68, 4.32, 0.34,
         13, WHITE, True, align=PP_ALIGN.CENTER)
    footer(slide)
    add_notes(slide, scripts[5])

    # 7. Progress
    slide = presentation.slides.add_slide(blank)
    rect(slide, 0, 0, 13.333, 7.5, TEAL)
    text(slide, "CURRENT PROGRESS / OCTOBER 2026", 0.72, 0.52, 5.8, 0.3, 10, MINT, True)
    text(slide, "Working end to end.", 0.72, 1.08, 6.2, 0.62, 30, WHITE, True)
    text(slide, "Verified with the real Parkhaven massing model", 0.72, 1.87, 5.9, 0.35, 15, MINT)
    stats = [("127", "app tests"), ("25", "analyzer tests"), ("4", "controlled views"), ("2", "PDF pages")]
    for i, (value, label) in enumerate(stats):
        x = 0.72 + i * 2.35
        rect(slide, x, 2.70, 2.02, 1.46, "214849", "496766", True)
        text(slide, value, x + 0.18, 2.96, 1.66, 0.5, 25, WHITE, True, align=PP_ALIGN.CENTER)
        text(slide, label.upper(), x + 0.18, 3.59, 1.66, 0.22, 8, MINT, True, align=PP_ALIGN.CENTER)
    rect(slide, 10.18, 2.70, 2.42, 1.46, ORANGE, ORANGE, True)
    text(slide, "PASS", 10.38, 2.98, 2.02, 0.42, 23, WHITE, True, align=PP_ALIGN.CENTER)
    text(slide, "INSTALLED BUNDLE", 10.38, 3.60, 2.02, 0.22, 8, WHITE, True, align=PP_ALIGN.CENTER)
    rect(slide, 0.72, 4.72, 11.88, 0.02, "496766")
    text(slide, "NEXT", 0.72, 5.18, 0.8, 0.24, 9, ORANGE, True)
    text(slide, "Authoritative site constraints", 1.66, 5.10, 3.1, 0.38, 17, WHITE, True)
    text(slide, "Signed distribution", 5.07, 5.10, 2.5, 0.38, 17, WHITE, True)
    text(slide, "Clean-machine acceptance", 8.10, 5.10, 3.3, 0.38, 17, WHITE, True)
    text(slide, "VISUAL  •  MEASURABLE  •  AUDITABLE", 0.72, 6.43, 6.2, 0.3, 11, MINT, True)
    slide.shapes.add_picture(str(LOGO), Inches(11.62), Inches(5.56), height=Inches(1.34))
    add_notes(slide, scripts[6])

    presentation.core_properties.title = "ParkHaven Studio progress presentation"
    presentation.core_properties.subject = "Four-minute explanation of the ParkHaven workflow"
    presentation.core_properties.author = "ParkHaven Studio"
    presentation.save(OUTPUT)

    sections = ["Opening", "Workflow", "Architecture", "Evidence", "Results", "Trust", "Progress"]
    script_lines = ["# ParkHaven Studio — 4-minute presentation script", ""]
    for index, (section, script) in enumerate(zip(sections, scripts), start=1):
        script_lines.extend((f"## Slide {index}: {section}", script, ""))
    SCRIPT_OUTPUT.write_text("\n".join(script_lines), encoding="utf-8")
    print(f"Created {OUTPUT}")
    print(f"Created {SCRIPT_OUTPUT}")


if __name__ == "__main__":
    build()
