"""Rasterize an actual KiCad SVG with QtSvg, without changing the board geometry."""
import argparse
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage,QPainter,QColor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('svg');parser.add_argument('png');parser.add_argument('--width',type=int,default=2200)
    args=parser.parse_args();app=QApplication([]);svg=QSvgRenderer(args.svg)
    if not svg.isValid():raise ValueError('Invalid KiCad SVG')
    size=svg.defaultSize();height=round(args.width*size.height()/size.width())
    image=QImage(args.width,height,QImage.Format.Format_ARGB32);image.fill(QColor('#101a23'))
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    svg.render(painter,QRectF(0,0,args.width,height));painter.end()
    if not image.save(args.png):raise IOError(args.png)
