"""生成应用图标 assets/app.ico / app.png（需 Pillow）
设计：深蓝紫对角渐变圆角方块 + 白色"交换"双箭头（⇄），极简现代。
"""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
os.makedirs(ASSETS, exist_ok=True)

SS = 4  # 超采样


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make(size: int) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # ---- 对角渐变背景（左上亮蓝 -> 右下深紫） ----
    c1 = (91, 124, 250)    # #5B7CFA
    c2 = (76, 29, 149)     # #4C1D95 深紫
    grad = Image.new("RGB", (s, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / s
        gd.line([(0, y), (s, y)], fill=lerp(c1, c2, t))
    # 左上高光叠加
    overlay = Image.new("L", (s, s), 0)
    od = ImageDraw.Draw(overlay)
    for y in range(s):
        for x in range(0, s, 6):
            v = int(255 * max(0.0, 1 - (x + y) / (2 * s)) * 0.22)
            od.line([(x, y), (min(x + 5, s), y)], fill=v)
    white = Image.new("RGB", (s, s), (255, 255, 255))
    grad = Image.composite(white, grad, overlay)

    # 圆角遮罩（更圆润：0.25）
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.25), fill=255)
    img = Image.merge("RGBA", (*grad.split(), mask))

    d = ImageDraw.Draw(img)
    W = int(s * 0.10)      # 箭头线宽
    white_c = (255, 255, 255, 255)

    def arrow_head(tip, base_x, half_h, w):
        """画三角形箭头；tip 为尖点，base_x 为底边中心 x"""
        d.polygon([tip,
                   (base_x, tip[1] - half_h),
                   (base_x, tip[1] + half_h)],
                  fill=white_c)

    # ---- 上箭头（向右）：线 + 右端三角 ----
    y1 = s * 0.38
    x1a, x1b = s * 0.24, s * 0.56
    d.line([(x1a, y1), (x1b, y1)], fill=white_c, width=W)
    arrow_head((s * 0.68, y1), s * 0.50, s * 0.085, W)

    # ---- 下箭头（向左）：线 + 左端三角 ----
    y2 = s * 0.62
    x2a, x2b = s * 0.76, s * 0.44
    d.line([(x2a, y2), (x2b, y2)], fill=white_c, width=W)
    arrow_head((s * 0.32, y2), s * 0.50, s * 0.085, W)

    return img.resize((size, size), Image.LANCZOS)


def main():
    img = make(256)
    img.save(os.path.join(ASSETS, "app.png"))
    img.save(os.path.join(ASSETS, "app.ico"),
             sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("图标已重新生成：assets/app.ico, assets/app.png")


if __name__ == "__main__":
    main()
