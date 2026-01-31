import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage, QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen
from PyQt5.QtCore import Qt, QPointF, QRectF
from PIL import Image

def generate_icon():
    app = QApplication(sys.argv)
    
    # 尺寸
    size = 256
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 1. 绘制背景 (圆角矩形)
    rect = QRectF(10, 10, size-20, size-20)
    radius = 40
    
    # 背景渐变: 深蓝灰 -> 深灰
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#37474F"))
    gradient.setColorAt(1, QColor("#263238"))
    
    path_bg = QPainterPath()
    path_bg.addRoundedRect(rect, radius, radius)
    
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawPath(path_bg)
    
    # 2. 绘制装饰边框 (可选)
    pen = QPen(QColor("#546E7A"))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path_bg)
    
    # 3. 绘制太阳/月亮
    sun_color = QColor("#FFD740") # 琥珀色
    sun_radius = 25
    sun_center = QPointF(size * 0.75, size * 0.35)
    
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(sun_color))
    painter.drawEllipse(sun_center, sun_radius, sun_radius)
    
    # 4. 绘制山峰 (前景)
    # 山峰1 (大)
    mountain1 = QPainterPath()
    m1_start = QPointF(20, size - 30) # 左下
    m1_peak = QPointF(size * 0.4, size * 0.35) # 峰顶
    m1_end = QPointF(size * 0.8, size - 30) # 右下
    
    mountain1.moveTo(m1_start)
    mountain1.lineTo(m1_peak)
    mountain1.lineTo(m1_end)
    mountain1.closeSubpath()
    
    # 山峰1 渐变
    grad_m1 = QLinearGradient(0, size*0.3, 0, size)
    grad_m1.setColorAt(0, QColor("#4FC3F7")) # 亮蓝
    grad_m1.setColorAt(1, QColor("#0288D1")) # 深蓝
    
    # 山峰2 (小，重叠)
    mountain2 = QPainterPath()
    m2_start = QPointF(size * 0.5, size - 30)
    m2_peak = QPointF(size * 0.75, size * 0.55)
    m2_end = QPointF(size - 20, size - 30)
    
    mountain2.moveTo(m2_start)
    mountain2.lineTo(m2_peak)
    mountain2.lineTo(m2_end)
    mountain2.closeSubpath()
    
    grad_m2 = QLinearGradient(0, size*0.5, 0, size)
    grad_m2.setColorAt(0, QColor("#81D4FA")) # 更亮的蓝
    grad_m2.setColorAt(1, QColor("#29B6F6")) 
    
    # 绘制山峰 (先画大的，再画小的，或者反过来，看层级)
    # 这里先画大的作为背景山，再画小的作为前景山，或者交叉
    
    # 调整逻辑：先画后面的山，再画前面的山
    # 假设 m1 是大山在后， m2 是小山在前
    
    painter.setBrush(QBrush(grad_m1))
    painter.drawPath(mountain1)
    
    painter.setBrush(QBrush(grad_m2))
    painter.drawPath(mountain2)
    
    # 5. 底部裁剪 (确保山峰不超出圆角矩形)
    # 其实上面的 path_bg 已经作为底色。
    # 更好的做法是设置 Clip Path 为背景形状，这样山峰底部自动切齐
    # 但由于我们手动计算了坐标，只要坐标在 rect 内即可。
    # 为了完美，我们重新绘制一次背景的 Clip
    
    painter.end()
    
    # 为了裁剪超出圆角的部分 (如果山峰画出去了)，我们可以用 CompositionMode
    # 但简单起见，我们重新生成一个图，应用遮罩
    
    final_img = QImage(size, size, QImage.Format_ARGB32)
    final_img.fill(Qt.transparent)
    
    final_painter = QPainter(final_img)
    final_painter.setRenderHint(QPainter.Antialiasing)
    
    # 设置裁剪区域
    final_painter.setClipPath(path_bg)
    final_painter.drawImage(0, 0, img)
    final_painter.end()
    
    # 保存
    if not os.path.exists('resources'):
        os.makedirs('resources')
        
    png_path = os.path.abspath('resources/icon.png')
    final_img.save(png_path)
    print(f"Icon saved to {png_path}")
    
    # 转换为 ICO
    try:
        pil_img = Image.open(png_path)
        ico_path = os.path.abspath('resources/icon.ico')
        pil_img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print(f"Icon saved to {ico_path}")
    except Exception as e:
        print(f"Failed to save ICO: {e}")

if __name__ == "__main__":
    generate_icon()
