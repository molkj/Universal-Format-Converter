"""生成应用图标 assets/app.ico / app.png（需 Pillow）
设计：蓝紫渐变圆角方块 + 白色"文件 + 转换箭头"——左文件、右箭头，
一眼看懂"格式转换"，比双箭头 ⇄ 更简单直观，贴合界面蓝紫渐变风格。
"""
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
os.makedirs(ASSETS, exist_ok=True)

SS = 4  # 超采样


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make(size: int) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # ---- 对角渐变背景（左上亮蓝 -> 右下紫罗兰） ----
    c1 = (91, 124, 250)   # #5B7CFA
    c2 = (124, 58, 237)   # #7C3AED
    grad = Image.new("RGB", (s, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / s
        gd.line([(0, y), (s, y)], fill=lerp(c1, c2, t))

    # 左上高光（径向，更柔和）
    hl = Image.new("L", (s, s), 0)
    hd = ImageDraw.Draw(hl)
    for r in range(int(s * 0.9), 0, -6):
        a = int(46 * (1 - r / (s * 0.9)))
        if a <= 0:
            continue
        hd.ellipse([s * 0.12 - r, s * 0.08 - r,
                    s * 0.12 + r, s * 0.08 + r], fill=a)
    white = Image.new("RGB", (s, s), (255, 255, 255))
    grad = Image.composite(white, grad, hl)

    # 圆角遮罩
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=255)
    img = Image.merge("RGBA", (*grad.split(), mask))

    d = ImageDraw.Draw(img)

    # ---- 白色文件纸（左，带折角 + 内容线） ----
    fx, fy, fw, fh = s * 0.24, s * 0.28, s * 0.34, s * 0.46
    fold = s * 0.075                      # 右上折角大小
    paper = [
        (fx, fy),
        (fx + fw - fold, fy),
        (fx + fw, fy + fold),
        (fx + fw, fy + fh),
        (fx, fy + fh),
    ]
    # 纸阴影
    sh = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    shd = ImageDraw.Draw(sh)
    shd.polygon(paper, fill=(31, 41, 55, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(int(s * 0.015)))
    img.alpha_composite(sh, (int(s * 0.012), int(s * 0.016)))
    d = ImageDraw.Draw(img)
    # 纸面
    d.polygon(paper, fill=(255, 255, 255, 252))
    # 折角阴影三角（纸背折叠）
    d.polygon(
        [(fx + fw - fold, fy), (fx + fw, fy + fold), (fx + fw - fold, fy + fold)],
        fill=(203, 213, 236, 255))
    # 内容线
    lw = int(s * 0.016)
    lx0, lx1 = fx + s * 0.045, fx + fw - s * 0.045
    for i, ly in enumerate((fy + s * 0.105, fy + s * 0.155, fy + s * 0.205)):
        d.line([(lx0, ly), (lx1 if i < 2 else lx0 + s * 0.14, ly)],
               fill=(205, 213, 235, 255), width=lw)

    # ---- 转换箭头（右，白，圆头圆尾） ----
    ay = s * 0.50
    ax0, ax1 = s * 0.63, s * 0.80          # 杆
    tip_x = s * 0.88                       # 箭头尖
    aw = int(s * 0.075)                    # 杆宽
    ah = int(s * 0.115)                    # 箭头半高
    d.line([(ax0, ay), (ax1, ay)], fill=(255, 255, 255, 255), width=aw)
    d.polygon([(tip_x, ay),
               (ax1, ay - ah),
               (ax1, ay + ah)], fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.LANCZOS)


def main():
    img = make(256)
    img.save(os.path.join(ASSETS, "app.png"))
    img.save(os.path.join(ASSETS, "app.ico"),
             sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("新图标已生成：assets/app.ico, assets/app.png")


if __name__ == "__main__":
    main()
