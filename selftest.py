"""转换引擎自测：验证各格式转换是否正常（开发用，不参与打包）"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from converter import get_available_targets, convert_file  # noqa: E402
from PIL import Image  # noqa: E402

WORK = tempfile.mkdtemp(prefix="fc_test_")
SRC = os.path.join(WORK, "src")
OUT = os.path.join(WORK, "out")
os.makedirs(SRC, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

PASS = 0
FAIL = 0


def progress(done, total, msg):
    pass


def check(name, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  ✅ {name}")
        PASS += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        FAIL += 1


def make_pdf():
    from fpdf import FPDF  # 仅在测试时使用

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=14)
    pdf.cell(0, 10, "Hello FileConverter Test")
    pdf.ln()
    pdf.cell(0, 10, "Second line for testing")
    p = os.path.join(SRC, "sample.pdf")
    pdf.output(p)
    return p


def main():
    print("== 图片转换测试 ==")
    img = Image.new("RGBA", (200, 100), (255, 0, 0, 200))
    img.save(os.path.join(SRC, "pic.png"))

    check("PNG → JPG", lambda: convert_file(os.path.join(SRC, "pic.png"), "jpg", OUT, progress))
    check("PNG → WebP", lambda: convert_file(os.path.join(SRC, "pic.png"), "webp", OUT, progress))
    check("PNG → ICO", lambda: convert_file(os.path.join(SRC, "pic.png"), "ico", OUT, progress))

    print("== 文本/文档转换测试 ==")
    txt = os.path.join(SRC, "note.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("这是一段测试文本\n# 标题\n- 列表项")

    check("TXT → DOCX", lambda: convert_file(txt, "docx", OUT, progress))
    md = os.path.join(SRC, "readme.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# 大标题\n\n## 小标题\n\n- 项目一\n- 项目二\n\n正文内容")
    check("MD → HTML", lambda: convert_file(md, "html", OUT, progress))
    check("HTML → TXT", lambda: convert_file(os.path.join(OUT, "readme.html"), "txt", OUT, progress))

    print("== CSV/Excel 转换测试 ==")
    csv = os.path.join(SRC, "data.csv")
    with open(csv, "w", encoding="utf-8", newline="") as f:
        f.write("姓名,年龄,城市\n张三,28,北京\n李四,35,上海")
    check("CSV → XLSX", lambda: convert_file(csv, "xlsx", OUT, progress))

    print("== 压缩包测试 ==")
    check("文件夹 → ZIP", lambda: convert_file(SRC, "zip", OUT, progress))
    check("ZIP → 7Z", lambda: convert_file(os.path.join(OUT, "src.zip"), "7z", OUT, progress))

    print(f"\n结果：通过 {PASS}，失败 {FAIL}")
    print(f"测试目录：{WORK}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
