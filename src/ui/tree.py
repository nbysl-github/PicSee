from PyQt5.QtWidgets import QProxyStyle, QStyle
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QPainterPath

# 自定义树视图样式 (用于绘制可见的折叠箭头)
class TreeStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorBranch:
            painter.save()

            # 获取颜色 (适配暗黑模式)
            color = option.palette.text().color()
            painter.setRenderHint(QPainter.Antialiasing, True)

            rect = option.rect
            cx = rect.center().x()
            cy = rect.center().y()

            # 等边三角形尺寸
            side = 10
            h = side * 0.866  # ~8.66

            path = QPainterPath()

            # 判断是否有子节点 (实心/空心)
            has_children = option.state & QStyle.State_Children
            is_open = option.state & QStyle.State_Open

            # 确定所属根节点 (此电脑 / 收藏目录 / 历史目录)
            is_favorites_or_history = False
            is_root_itself = False

            if widget:
                # 通过位置获取当前项的索引
                index = widget.indexAt(rect.center())
                if index.isValid():
                    # 检查是否是根节点本身
                    if index.data(Qt.UserRole) in ["root_favorites", "root_history"]:
                        is_root_itself = True

                    # 向上追溯到根节点
                    temp = index
                    while temp.parent().isValid():
                        temp = temp.parent()

                    # 检查根节点标识
                    root_data = temp.data(Qt.UserRole)
                    if root_data in ["root_favorites", "root_history"]:
                        is_favorites_or_history = True

            # 绘制逻辑分流
            # 如果是收藏/历史目录的子节点 (非根节点本身)
            if is_favorites_or_history and not is_root_itself:
                if has_children:
                    # 有子目录 -> 实心三角形
                    if is_open:  # 向下
                        p1 = QPointF(cx - side / 2, cy - h / 2)
                        p2 = QPointF(cx + side / 2, cy - h / 2)
                        p3 = QPointF(cx, cy + h / 2)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)
                    else:  # 向右
                        p1 = QPointF(cx - h / 2, cy - side / 2)
                        p2 = QPointF(cx - h / 2, cy + side / 2)
                        p3 = QPointF(cx + h / 2, cy)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)

                    path.closeSubpath()
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color)
                    painter.drawPath(path)
                else:
                    # 无子目录时不绘制
                    pass

            else:
                # 其他区域 (此电脑) 以及 收藏/历史的根节点 -> 实心三角形
                if has_children:
                    if is_open:  # 向下
                        p1 = QPointF(cx - side / 2, cy - h / 2)
                        p2 = QPointF(cx + side / 2, cy - h / 2)
                        p3 = QPointF(cx, cy + h / 2)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)
                    else:  # 向右
                        p1 = QPointF(cx - h / 2, cy - side / 2)
                        p2 = QPointF(cx - h / 2, cy + side / 2)
                        p3 = QPointF(cx + h / 2, cy)
                        path.moveTo(p1)
                        path.lineTo(p2)
                        path.lineTo(p3)

                    path.closeSubpath()
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color)
                    painter.drawPath(path)
                # 无子目录时不绘制

            painter.restore()
            return

        super().drawPrimitive(element, option, painter, widget)
