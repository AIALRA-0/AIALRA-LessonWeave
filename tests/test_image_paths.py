"""项目根路径与磁盘路径分别定位，Windows 上的图像路径继续落在当前案例中"""
from lessonweave.agents import image_path


def test_project_absolute_image_path_uses_current_project(tmp_path):
    assert image_path(tmp_path,'/00_source/materials/assets/figure.png')==tmp_path/'00_source/materials/assets/figure.png'
    assert image_path(tmp_path,'01_tree/history/run1/page.png')==tmp_path/'01_tree/history/run1/page.png'


def test_disk_absolute_image_path_is_preserved(tmp_path):
    image=tmp_path/'image.png'
    assert image_path(tmp_path,image)==image
