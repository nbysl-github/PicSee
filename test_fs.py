
from PyQt5.QtWidgets import QApplication, QTreeView, QFileSystemModel
from PyQt5.QtCore import QDir

app = QApplication([])
model = QFileSystemModel()
# model.setRootPath(QDir.rootPath())
model.setRootPath("::{20D04FE0-3AEA-1069-A2D8-08002B30309D}") # My Computer CLSID
view = QTreeView()
view.setModel(model)
view.show()
print(f"Root Path: {model.rootPath()}")
# app.exec_()
