# -*- coding: utf-8 -*-
"""生成《活动报名与签到管理系统》v0.2 汇报 PPT。"""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu
from lxml import etree

FONT = "Microsoft YaHei"

INK      = RGBColor(0x0F, 0x17, 0x2A)
SLATE    = RGBColor(0x33, 0x41, 0x55)
MUTED    = RGBColor(0x64, 0x74, 0x8B)
LINE     = RGBColor(0xE2, 0xE8, 0xF0)
PANEL    = RGBColor(0xF8, 0xFA, 0xFC)
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
ACCENT   = RGBColor(0x25, 0x63, 0xEB)
ACCENT_L = RGBColor(0xDB, 0xEA, 0xFE)
AMBER    = RGBColor(0xB4, 0x53, 0x09)
AMBER_L  = RGBColor(0xFE, 0xF3, 0xC7)
GREEN    = RGBColor(0x04, 0x78, 0x57)
GREEN_L  = RGBColor(0xD1, 0xFA, 0xE5)
RED      = RGBColor(0xB9, 0x1C, 0x1C)
RED_L    = RGBColor(0xFE, 0xE2, 0xE2)
NAVY_BG  = RGBColor(0x0B, 0x12, 0x24)

W, H = 13.333, 7.5
M = 0.75
CW = W - 2 * M


def new_deck():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    return prs


def blank(prs, bg=WHITE):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = bg
    return slide


def set_font(run, size, bold=False, color=INK, name=FONT):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = name
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", name)


def box(slide, x, y, w, h, fill=None, line=None, radius=0.08, line_w=1.0, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    shp.text_frame.word_wrap = True
    return shp


def write(slide, x, y, w, h, text, size=14, bold=False, color=INK,
          align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.25, after=4):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(after)
        set_font(p.add_run(), size, bold, color)
        p.runs[0].text = line
    return tb


def bullets(slide, x, y, w, h, items, size=13, color=SLATE, spacing=1.3, after=8, bullet_color=ACCENT):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        p.space_after = Pt(after)
        r0 = p.add_run()
        r0.text = "·  "
        set_font(r0, size + 2, True, bullet_color)
        r1 = p.add_run()
        r1.text = item
        set_font(r1, size, False, color)
    return tb


def header(slide, kicker, title, page):
    write(slide, M, 0.52, CW, 0.3, kicker, 11, True, ACCENT)
    write(slide, M, 0.86, CW, 0.6, title, 28, True, INK)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(M), Inches(1.52), Inches(0.9), Inches(0.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    footer(slide, page)


def footer(slide, page):
    write(slide, M, 6.98, 8.0, 0.25, "活动报名与签到管理系统 · v0.2 阶段汇报 · 2026.10.24", 9, False, MUTED)
    write(slide, W - M - 0.8, 6.98, 0.8, 0.25, f"{page:02d}", 9, True, MUTED, PP_ALIGN.RIGHT)


def pill(slide, x, y, w, text, fill, color, size=10.5):
    s = box(slide, x, y, w, 0.3, fill, None, radius=0.5)
    tf = s.text_frame
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    set_font(r, size, True, color)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ----------------------------------------------------------------------------
prs = new_deck()

# 1 封面
s = blank(prs, NAVY_BG)
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.16), Inches(H))
band.fill.solid(); band.fill.fore_color.rgb = ACCENT; band.line.fill.background(); band.shadow.inherit = False
ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.1), Inches(1.05), Inches(5.2), Inches(5.2))
ring.fill.background(); ring.line.color.rgb = RGBColor(0x1E, 0x29, 0x3B); ring.line.width = Pt(28); ring.shadow.inherit = False
ring2 = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(10.35), Inches(2.3), Inches(2.7), Inches(2.7))
ring2.fill.background(); ring2.line.color.rgb = RGBColor(0x25, 0x63, 0xEB); ring2.line.width = Pt(2); ring2.shadow.inherit = False

write(s, M, 1.35, 7.5, 0.3, "PROJECT REVIEW  ·  2026.10", 11, True, RGBColor(0x60, 0xA5, 0xFA))
write(s, M, 1.85, 7.6, 2.2, "活动报名与\n签到管理系统", 44, True, WHITE, spacing=1.15)
write(s, M, 3.72, 7.4, 0.9, "v0.2 报名闭环已完成，下一步补齐现场核销", 18, False, RGBColor(0xCB, 0xD5, 0xE1))
line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(M), Inches(4.62), Inches(1.4), Inches(0.05))
line.fill.solid(); line.fill.fore_color.rgb = ACCENT; line.line.fill.background(); line.shadow.inherit = False
write(s, M, 5.0, 6.8, 0.7,
      "单机构 · 多活动 · 管理后台 + 参与者网页版 + 微信小程序", 13, False, RGBColor(0x94, 0xA3, 0xB8))
write(s, M, 6.55, 8.0, 0.3, "汇报人：项目组      汇报日期：2026-10-24", 11, False, RGBColor(0x94, 0xA3, 0xB8))
notes(s, "开场一句话：报名闭环已经跑通，今天主要讲做到哪、怎么做的、下一步要什么支持。")

# 2 目录
s = blank(prs)
header(s, "AGENDA", "今天汇报五件事", 2)
items = [
    ("01", "项目定位", "为什么做、给谁用"),
    ("02", "当前进度", "两个版本交付了什么"),
    ("03", "已交付能力", "三端功能与技术架构"),
    ("04", "质量与风险", "验证结果、已知问题"),
    ("05", "下一步", "v0.3 计划与需要的支持"),
]
col_w = (CW - 0.5) / 2
for i, (num, title, desc) in enumerate(items):
    cx = M + (i % 2) * (col_w + 0.5)
    cy = 2.0 + (i // 2) * 1.55
    write(s, cx, cy, 1.0, 0.5, num, 26, True, RGBColor(0xBF, 0xDB, 0xFE))
    write(s, cx + 0.95, cy + 0.02, col_w - 0.95, 0.4, title, 18, True, INK)
    write(s, cx + 0.95, cy + 0.46, col_w - 0.95, 0.35, desc, 12, False, MUTED)
    if i < 4:
        ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(cx), Inches(cy + 1.18), Inches(col_w), Inches(0.01))
        ln.fill.solid(); ln.fill.fore_color.rgb = LINE; ln.line.fill.background(); ln.shadow.inherit = False
notes(s, "五块内容，重点在第二、三、五块。")

# 3 定位
s = blank(prs)
header(s, "01  项目定位", "把一场活动从「发出去」到「到场」收进一个后台", 3)
write(s, M, 1.95, 6.4, 1.7,
      "面向单个组织的活动管理平台，\n覆盖发布、报名、审核、核销、统计的完整闭环。",
      20, True, INK, spacing=1.35)
write(s, M, 3.75, 6.3, 1.2,
      "不追求通用 SaaS，也不做多租户：先把一个机构的高频场景做顺，\n把现场那一步真正跑通。",
      13, False, MUTED, spacing=1.4)
roles = [
    ("组织者", "发布活动、配置报名表、管名单、看数据", ACCENT_L, ACCENT),
    ("参与者", "手机报名、随时查看、出示电子票", GREEN_L, GREEN),
    ("现场工作人员", "扫码核销、异常兜底（v0.3）", AMBER_L, AMBER),
]
for i, (role, desc, bg, fg) in enumerate(roles):
    y = 1.95 + i * 1.45
    card = box(s, 7.35, y, 5.2, 1.2, bg, None, radius=0.12)
    dot = box(s, 7.6, y + 0.3, 0.6, 0.6, WHITE, None, radius=0.5)
    write(s, 7.6, y + 0.42, 0.6, 0.3, role[0], 15, True, fg, PP_ALIGN.CENTER)
    write(s, 8.42, y + 0.2, 3.9, 0.35, role, 15, True, fg)
    write(s, 8.42, y + 0.62, 3.9, 0.5, desc, 11.5, False, SLATE)
notes(s, "定位一句话：不是通用平台，是把单机构的报名和现场跑顺。")

# 4 进度
s = blank(prs)
header(s, "02  当前进度", "v0.2 报名闭环已交付，v0.3 尚未启动", 4)
kpis = [("3", "个客户端", "后台 / 网页版 / 小程序"),
        ("56", "个接口测试", "全部通过"),
        ("5", "张核心数据表", "活动/参与者/报名等"),
        ("1", "个待交付阶段", "v0.3 核销与导出")]
kw = (CW - 0.6) / 4
for i, (num, label, desc) in enumerate(kpis):
    x = M + i * (kw + 0.2)
    box(s, x, 1.9, kw, 1.35, PANEL, LINE, radius=0.1)
    write(s, x + 0.28, 2.02, 1.5, 0.55, num, 30, True, ACCENT)
    write(s, x + 0.28, 2.62, kw - 0.5, 0.3, label, 12, True, INK)
    write(s, x + 0.28, 2.93, kw - 0.4, 0.3, desc, 10, False, MUTED)
stages = [("v0.1", "基础骨架", "登录、活动、权限、Docker、CI", GREEN, GREEN_L),
          ("v0.2", "报名闭环", "报名、审核、电子票、网页版", GREEN, GREEN_L),
          ("v0.3", "现场核销", "核销、签到统计、Excel 导出", AMBER, AMBER_L)]
for i, (ver, name, desc, fg, bg) in enumerate(stages):
    x = M + i * (CW / 3)
    box(s, x, 3.95, CW / 3 - 0.25, 1.5, bg, None, radius=0.1)
    write(s, x + 0.3, 4.1, 2.0, 0.4, ver, 16, True, fg)
    write(s, x + 0.3, 4.55, 3.2, 0.4, name, 15, True, INK)
    write(s, x + 0.3, 4.98, 3.2, 0.4, desc, 10.5, False, SLATE)
    pill(s, x + CW / 3 - 1.55, 4.12, 1.05, "已完成" if i < 2 else "待启动", WHITE, fg, 10)
write(s, M, 5.85, CW, 0.5, "里程碑口径：v0.1 与 v0.2 均已验收，后端 56 个用例、管理后台与网页版均实机验证。", 12, False, MUTED)
notes(s, "强调两个版本已验收，v0.3 还没开始，所以需要现在定资源和排期。")

# 5 闭环
s = blank(prs)
header(s, "03  业务闭环", "五个环节完成三个，缺的是现场那一步", 5)
steps = [("活动发布", "已完成", GREEN, GREEN_L),
         ("在线报名", "已完成", GREEN, GREEN_L),
         ("名单审核", "已完成", GREEN, GREEN_L),
         ("扫码核销", "v0.3", AMBER, AMBER_L),
         ("数据统计", "部分完成", AMBER, AMBER_L)]
card_w, gap = 2.12, 0.24
for i, (name, status, fg, bg) in enumerate(steps):
    x = M + i * (card_w + gap)
    box(s, x, 2.45, card_w, 1.55, WHITE, LINE, radius=0.1)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(2.45), Inches(card_w), Inches(0.09))
    bar.fill.solid(); bar.fill.fore_color.rgb = fg; bar.line.fill.background(); bar.shadow.inherit = False
    write(s, x + 0.22, 2.68, 0.7, 0.3, "0" + str(i + 1), 11, True, RGBColor(0xBF, 0xDB, 0xFE))
    write(s, x + 0.22, 3.0, card_w - 0.35, 0.35, name, 14, True, INK)
    pill(s, x + 0.22, 3.52, 1.05, status, bg, fg, 9.5)
    if i < 4:
        arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + card_w + 0.03), Inches(3.05), Inches(0.18), Inches(0.2))
        arrow.fill.solid(); arrow.fill.fore_color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
        arrow.line.fill.background(); arrow.shadow.inherit = False
write(s, M, 4.45, CW, 0.4, "报名链路已经闭环，统计只覆盖报名侧；签到率、到场数据要等核销上线后才能产出。", 13, False, SLATE)
note_box = box(s, M, 5.15, CW, 1.15, PANEL, LINE, radius=0.08)
write(s, M + 0.4, 5.32, CW - 0.8, 0.35, "现场环节的三个刚需", 12, True, INK)
write(s, M + 0.4, 5.7, CW - 0.8, 0.45,
      "扫码 1 秒完成  ·  重复签到有提示  ·  断网/异常有手动检索兜底", 14, True, ACCENT)
notes(s, "闭环图用来解释为什么 v0.3 是重点，而不是可选项。")

# 6 已交付
s = blank(prs)
header(s, "03  已交付能力", "三端各自可用，共用一套接口", 6)
cols = [
    ("管理后台", "Vue 3 + Element Plus", [
        "活动创建、发布、下架、结束",
        "动态报名字段与预览",
        "报名名单、批量审核、统计",
        "乐观锁与审计日志",
    ], ACCENT, ACCENT_L),
    ("参与者网页版", "手机优先 H5", [
        "用户名密码自助注册登录",
        "活动列表、详情、余量与状态",
        "动态表单报名、取消、复用",
        "电子票二维码、我的报名",
    ], GREEN, GREEN_L),
    ("微信小程序", "原生，代码保留", [
        "活动、报名、我的报名页面",
        "电子票与个人中心",
        "Mock 登录可联调",
        "尚未在开发者工具验收",
    ], AMBER, AMBER_L),
]
cw3 = (CW - 0.6) / 3
for i, (title, sub, items, fg, bg) in enumerate(cols):
    x = M + i * (cw3 + 0.3)
    box(s, x, 1.9, cw3, 4.15, WHITE, LINE, radius=0.08)
    top = box(s, x, 1.9, cw3, 0.95, bg, None, radius=0.08)
    write(s, x + 0.32, 2.06, cw3 - 0.6, 0.35, title, 16, True, fg)
    write(s, x + 0.32, 2.42, cw3 - 0.6, 0.3, sub, 10.5, False, MUTED)
    bullets(s, x + 0.32, 3.12, cw3 - 0.55, 2.4, items, 12.5, SLATE, spacing=1.35, after=16)
    write(s, x + 0.32, 5.62, cw3 - 0.55, 0.3, ["已实机验证", "浏览器实测通过", "待真机验收"][i], 10, True,
          GREEN if i < 2 else AMBER)
write(s, M, 6.55, CW, 0.3, "三端共用 /api 与同一套报名、审核、电子票逻辑，小程序端目前只差真机验收。", 11, False, MUTED)
notes(s, "网页版是这一阶段新增的，解决了没有小程序时也能报名的问题。")

# 7 架构
s = blank(prs)
header(s, "03  技术架构", "一个后端，三种客户端，两种数据库环境", 7)
bands = [
    ("客户端", ["管理后台 Vue 3", "参与者 H5", "微信小程序"], RGBColor(0xEF, 0xF6, 0xFF)),
    ("接入层", ["Nginx / Vite 代理", "/api 统一前缀", "JWT 双类型鉴权"], RGBColor(0xF1, 0xF5, 0xF9)),
    ("应用层", ["FastAPI + 服务层", "报名 / 审核 / 电子票", "Alembic 迁移"], RGBColor(0xEC, 0xFD, 0xF5)),
    ("数据层", ["SQLite（本地）", "MySQL 8.4（Docker）", "预留 Redis"], RGBColor(0xFF, 0xFB, 0xEB)),
]
for i, (label, chips, bg) in enumerate(bands):
    y = 1.85 + i * 1.18
    write(s, M, y + 0.22, 1.0, 0.3, label, 12, True, MUTED)
    box(s, M + 1.05, y, 8.1, 0.95, bg, None, radius=0.08)
    for j, chip in enumerate(chips):
        cx = M + 1.3 + j * 2.75
        write(s, cx, y + 0.31, 2.55, 0.35, chip, 12, True, INK)
    if i < 3:
        arrow = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(M + 5.0), Inches(y + 0.94), Inches(0.24), Inches(0.22))
        arrow.fill.solid(); arrow.fill.fore_color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
        arrow.line.fill.background(); arrow.shadow.inherit = False
write(s, 10.15, 1.9, 2.5, 0.3, "部署形态", 11, True, MUTED)
ops = ["本地：5173 / 5174 / 8000", "Docker：8080 / 8081 / 内网", "生产：Nginx + HTTPS", "备份：mysqldump 脚本"]
bullets(s, 10.15, 2.28, 2.45, 2.6, ops, 10.5, SLATE, spacing=1.25, after=8)
box(s, 10.15, 4.35, 2.45, 1.55, PANEL, LINE, radius=0.08)
write(s, 10.35, 4.5, 2.1, 0.3, "为什么不做微服务", 10.5, True, INK)
write(s, 10.35, 4.85, 2.05, 0.9, "单机构、单机可跑，先把交付和运维成本压到最低。", 9.5, False, SLATE, spacing=1.3)
notes(s, "架构不用展开太细，讲清三点：三端一套接口、两种数据库、可单机部署。")

# 8 关键设计
s = blank(prs)
header(s, "04  关键设计", "六个容易被忽略、但决定可用性的细节", 8)
cards = [
    ("01", "名额原子扣减", "用条件 UPDATE 占名额，不做「先查后插」，并发下不超卖。", "SQL / 事务"),
    ("02", "编辑乐观锁", "活动带 version，两个管理员同时改会明确报冲突，而不是互相覆盖。", "409 冲突"),
    ("03", "电子票签名", "token 里存报名号和活动号并做 HMAC 签名，不暴露可枚举 ID。", "HMAC-SHA256"),
    ("04", "登录限流", "同一 IP + 账号连续失败 5 次锁 15 分钟，成功登录后清零。", "进程内"),
    ("05", "表单 Schema", "报名字段后端配置、前端动态渲染，提交时前后端同源校验。", "JSON Schema"),
    ("06", "审计留痕", "发布、审核、取消等关键操作写入 audit_log，可回溯。", "audit_log"),
]
cw2 = (CW - 0.5) / 2
for i, (num, title, desc, tag) in enumerate(cards):
    x = M + (i % 2) * (cw2 + 0.5)
    y = 1.85 + (i // 2) * 1.58
    box(s, x, y, cw2, 1.3, WHITE, LINE, radius=0.08)
    write(s, x + 0.3, y + 0.2, 0.6, 0.3, num, 12, True, RGBColor(0xBF, 0xDB, 0xFE))
    write(s, x + 0.82, y + 0.15, cw2 - 1.9, 0.35, title, 14, True, INK)
    write(s, x + 0.82, y + 0.55, cw2 - 1.15, 0.55, desc, 10.5, False, SLATE, spacing=1.25)
    pill(s, x + cw2 - 1.42, y + 0.18, 1.15, tag, PANEL, MUTED, 8.5)
notes(s, "挑两三个展开：原子扣减和电子票签名，能体现不是只做了界面。")

# 9 工程与安全
s = blank(prs)
header(s, "04  工程质量与安全", "能跑只是底线，部署与安全也按生产标准准备", 9)
box(s, M, 1.85, 5.85, 3.0, WHITE, LINE, radius=0.08)
write(s, M + 0.35, 2.0, 5.2, 0.35, "工程化", 14, True, INK)
bullets(s, M + 0.35, 2.45, 5.2, 2.2, [
    "Docker Compose 拉起 MySQL、后端、两个前端",
    "后端非 root、健康检查、真实 IP 透传",
    "Alembic 管理迁移，CI 跑迁移与测试",
    "统一响应体与异常处理，前端构建约 140 KB",
], 12, SLATE, spacing=1.4, after=14)
box(s, 6.85, 1.85, 5.75, 3.0, WHITE, LINE, radius=0.08)
write(s, 7.2, 2.0, 5.0, 0.35, "安全基线", 14, True, INK)
bullets(s, 7.2, 2.45, 5.0, 2.2, [
    "Argon2 密码哈希，JWT 双类型隔离",
    "生产强制校验 JWT / 电子票密钥",
    "生产强制关闭 Mock 登录",
    "备份脚本已验证，恢复流程待演练",
], 12, SLATE, spacing=1.4, after=14)
chips = ["GitHub Actions", "Alembic", "Docker", "Argon2", "HMAC", "Nginx"]
for i, c in enumerate(chips):
    pill(s, M + i * 1.95, 5.1, 1.7, c, PANEL, SLATE, 9.5)
write(s, M, 5.75, CW, 0.4, "已知短板：限流是进程内实现，多 worker 部署前需要换 Redis。", 11, False, AMBER)
notes(s, "安全和部署这块一句带过，重点是说明不是玩具项目。")

# 10 验证
s = blank(prs)
header(s, "04  验证结果", "功能、并发、部署都跑过一遍", 10)
big = [("56", "接口测试", "全部通过"), ("3", "层验证", "接口 / 页面 / 部署"), ("0", "超卖", "并发抢名额验证")]
for i, (num, label, desc) in enumerate(big):
    x = M + i * 2.15
    write(s, x, 1.95, 2.0, 0.8, num, 40, True, ACCENT)
    write(s, x, 2.78, 2.0, 0.3, label, 12, True, INK)
    write(s, x, 3.1, 2.0, 0.3, desc, 9.5, False, MUTED)
checks = [
    "登录、限流、越权、活动 CRUD、乐观锁",
    "报名 / 审核 / 取消 / 复用、名额边界",
    "电子票签名与 PNG 二维码",
    "Docker 全栈启动、非 root、备份脚本",
    "网页版注册→报名→取消→重新登录",
    "小程序语法与页面完整性校验（未运行）",
]
for i, c in enumerate(checks):
    y = 1.9 + i * 0.74
    mark = box(s, 6.95, y + 0.03, 0.28, 0.28, GREEN_L, None, radius=0.5)
    tf = mark.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "✓"; set_font(r, 10, True, GREEN)
    write(s, 7.4, y, 5.2, 0.4, c, 11.5, False, SLATE)
write(s, M, 6.35, 5.9, 0.4, "口径：自动化测试覆盖接口与并发；页面与部署为人工验证。", 10, False, MUTED)
notes(s, "数字先抛出来：56 个用例、3 端、0 超卖，然后逐条说验证范围。")

# 11 风险
s = blank(prs)
header(s, "04  风险与依赖", "四个外部条件，决定能不能按时上线", 11)
rows = [
    ("域名备案 + HTTPS", "小程序无法请求接口、无法提审", "约 1–3 周，需立刻启动", RED_L, RED),
    ("小程序主体与类目", "审核被拒或能力受限", "优先企业/组织主体", AMBER_L, AMBER),
    ("小程序未真机验收", "上线前才发现问题", "排 1 周在开发者工具 + 真机验收", AMBER_L, AMBER),
    ("限流为进程内实现", "多实例部署后失效", "上 Redis，或维持单 worker", PANEL, SLATE),
]
write(s, M, 1.82, 3.2, 0.3, "风险", 10.5, True, MUTED)
write(s, M + 3.4, 1.82, 3.6, 0.3, "影响", 10.5, True, MUTED)
write(s, M + 7.3, 1.82, 4.2, 0.3, "应对", 10.5, True, MUTED)
for i, (risk, impact, action, bg, fg) in enumerate(rows):
    y = 2.2 + i * 1.02
    box(s, M, y, CW, 0.86, WHITE, LINE, radius=0.06)
    bar = box(s, M, y, 0.07, 0.86, fg, None, radius=0)
    write(s, M + 0.28, y + 0.14, 3.0, 0.6, risk, 12.5, True, INK)
    write(s, M + 3.4, y + 0.14, 3.7, 0.6, impact, 11, False, SLATE)
    write(s, M + 7.3, y + 0.14, 4.1, 0.6, action, 11, False, fg if fg != SLATE else SLATE)
notes(s, "外部依赖是最大变量，尤其是备案，需要领导层推动。")

# 12 路线图
s = blank(prs)
header(s, "05  下一步", "v0.3：四周补齐现场核销", 12)
write(s, M, 1.82, CW, 0.35, "按 1 人全职估算；外部准备必须并行，否则第 4 周只能空等。", 12, False, MUTED)
line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(M + 0.4), Inches(2.98), Inches(CW - 0.9), Inches(0.03))
line.fill.solid(); line.fill.fore_color.rgb = LINE; line.line.fill.background(); line.shadow.inherit = False
weeks = [
    ("W1", "核销模型与接口", "签到表、签名校验、重复签到提示"),
    ("W2", "工作人员模式", "小程序核销页、扫码、手动检索"),
    ("W3", "统计与导出", "签到率、趋势、Excel 导出"),
    ("W4", "验收与上线", "真机验收、部署、安全复核"),
]
for i, (wk, name, desc) in enumerate(weeks):
    x = M + 0.15 + i * 2.95
    dot = box(s, x + 0.05, 2.82, 0.36, 0.36, ACCENT, WHITE, radius=0.5, line_w=3)
    write(s, x - 0.1, 3.32, 1.1, 0.3, wk, 12, True, ACCENT)
    write(s, x - 0.1, 3.62, 2.6, 0.4, name, 13, True, INK)
    write(s, x - 0.1, 4.03, 2.5, 0.7, desc, 10, False, MUTED, spacing=1.25)
box(s, M, 5.35, CW, 1.05, PANEL, LINE, radius=0.08)
write(s, M + 0.35, 5.5, 2.2, 0.3, "并行推进", 11, True, MUTED)
write(s, M + 0.35, 5.82, CW - 0.7, 0.35, "AppID 与主体资质  ·  域名备案  ·  服务器与对象存储  ·  网页版验证码与找回密码", 12, True, INK)
notes(s, "四周是按 1 人全职估的；外部准备必须并行，否则 W4 会空等。")

# 13 支持
s = blank(prs)
header(s, "05  需要的支持", "三件需要拍板的事", 13)
asks = [
    ("主体与类目", "用企业/组织主体申请小程序，尽早确认类目资质。", "本周"),
    ("域名与服务器", "启动备案（1–3 周），准备 2C4G 服务器与 HTTPS。", "本周"),
    ("小程序验收档期", "安排开发者工具与真机验收，预留 1 周。", "W4 前"),
]
for i, (title, desc, when) in enumerate(asks):
    y = 1.9 + i * 1.32
    box(s, M, y, CW, 1.15, WHITE, LINE, radius=0.08)
    num = box(s, M + 0.25, y + 0.28, 0.55, 0.55, ACCENT_L, None, radius=0.5)
    tf = num.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = str(i + 1); set_font(r, 14, True, ACCENT)
    write(s, M + 1.0, y + 0.2, 3.0, 0.35, title, 14, True, INK)
    write(s, M + 1.0, y + 0.62, 7.6, 0.4, desc, 11, False, SLATE)
    pill(s, W - M - 1.5, y + 0.42, 1.2, when, PANEL, SLATE, 9.5)
box(s, M, 5.95, CW, 0.75, AMBER_L, None, radius=0.08)
write(s, M + 0.35, 6.12, CW - 0.7, 0.4, "待决策：v0.3 是否包含工作人员小程序模式；首版是否接支付（建议不做）。", 11, True, AMBER)
notes(s, "把外部依赖变成具体的请求，而不是笼统说需要支持。")

# 14 结束
s = blank(prs, NAVY_BG)
band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.16), Inches(H))
band.fill.solid(); band.fill.fore_color.rgb = ACCENT; band.line.fill.background(); band.shadow.inherit = False
write(s, M, 2.0, 8.0, 0.3, "SUMMARY", 11, True, RGBColor(0x60, 0xA5, 0xFA))
write(s, M, 2.45, 9.6, 1.8, "报名闭环已跑通，\n现场核销是下一站。", 40, True, WHITE, spacing=1.2)
write(s, M, 4.55, 9.0, 0.9, "v0.2 交付了后台、网页版与小程序三端；下一步用四周补齐扫码核销、签到统计与导出。", 15, False, RGBColor(0xCB, 0xD5, 0xE1), spacing=1.4)
write(s, M, 6.3, 9.0, 0.4, "谢谢，欢迎提问", 18, True, WHITE)
write(s, M, 6.85, 9.0, 0.3, "活动报名与签到管理系统 · 2026-10-24", 10, False, RGBColor(0x94, 0xA3, 0xB8))
notes(s, "收尾回到一句话：闭环已通，缺现场；请求是主体、备案和验收档期。")

out = "活动报名与签到管理系统-汇报.pptx"
prs.save(out)
print("saved", out, "slides", len(prs.slides.__iter__.__self__._sldIdLst))
