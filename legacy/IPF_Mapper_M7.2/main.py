from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from ipf.app.controller import AppController
from ipf.ui.main_window import MainWindow
from ipf.app.demo import DemoStore
import argparse

def main():
    app=QApplication(sys.argv); app.setApplicationName('IPF Mapper')
    parser=argparse.ArgumentParser(description='IPF Mapper M7.1')
    parser.add_argument('--data-dir',type=Path,default=Path.home()/'.ipf_mapper')
    args=parser.parse_args()
    controller=AppController(args.data_dir/'ipf_mapper.db'); demo=DemoStore(args.data_dir); demo.open()
    win=MainWindow(controller,demo); win.show()
    try:return app.exec()
    finally:
        controller.close()
        if demo.controller:demo.controller.close()

if __name__=='__main__': raise SystemExit(main())
