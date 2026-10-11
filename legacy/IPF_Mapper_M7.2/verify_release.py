"""Repeatable release checks: full suite, imports, FK/integrity, Qt screenshots."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import argparse
import compileall
import importlib
import json
import pkgutil
from pathlib import Path
import tempfile
import unittest

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--out',type=Path,default=Path('verification')); args=parser.parse_args(); out=args.out; out.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.discover('ipf/tests')
    with (out/'tests.txt').open('w',encoding='utf-8') as log:result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    syntax=compileall.compile_dir('ipf',quiet=1) and compileall.compile_file('main.py',quiet=1)
    import ipf
    imports=[]
    for module in pkgutil.walk_packages(ipf.__path__,'ipf.'):
        if '.tests' not in module.name:importlib.import_module(module.name); imports.append(module.name)
    from ipf.app.controller import AppController
    from ipf.app.demo import DemoStore
    from ipf.ui.main_window import MainWindow
    from ipf.ui.forms import ElementDialog,FlowDialog,RuleDialog
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    app=QApplication.instance() or QApplication([])
    for font in ('segoeui.ttf','segoeuib.ttf'):
        file=Path('C:/Windows/Fonts')/font
        if file.exists():QFontDatabase.addApplicationFont(str(file))
    with tempfile.TemporaryDirectory() as directory:
        user=AppController(Path(directory)/'ipf_mapper.db'); demo=DemoStore(directory); demo.open(); window=MainWindow(user,demo); window.show(); app.processEvents(); app.processEvents(); window.grab().save(str(out/'canvas.png'))
        rid=window.revision_id; ex=window.c.executions_for_revision(rid)[0]['id']; ids={e['stable_code']:e['identity_id'] for e in window.c.entities(rid) if e['stable_code']}
        for name,page in [('rules',window.rules_page),('execution',window.execution_page),('analysis',window.analysis_page)]:
            window.show_page(page); app.processEvents(); window.grab().save(str(out/(name+'.png')))
        window.show_canvas(); window.show_properties(window.c.entity(rid,ids['TA'])); app.processEvents(); window.grab().save(str(out/'inspector.png'))
        for name,dialog in [('means',ElementDialog(window.c,rid,'MEANS',window)),('flow',FlowDialog(window.c,rid,window)),('rule_editor',RuleDialog(window.c,rid,window,data=window.c.configured_rules(rid)[0]))]:
            dialog.show(); app.processEvents(); dialog.grab().save(str(out/(name+'.png'))); dialog.close()
        a=window.c.runtime_analysis(rid,ex); foreign_keys=window.c.rows('PRAGMA foreign_key_check'); integrity=window.c.row('PRAGMA integrity_check'); snap=window.c.row('SELECT model_revision_id FROM model_execution WHERE id=?',(ex,))['model_revision_id']
        initial=a['active'].by_identity(ids['APPROVE']).requirement.value
        window.c.set_parameter(rid,'MANAGEMENT_APPROVAL_THRESHOLD','Threshold','NUMBER',750000)
        changed=window.c.evaluate_states(rid,ex)[0].by_identity(ids['APPROVE']).requirement.value; historical=window.c.evaluate_states(snap,ex)[0].by_identity(ids['APPROVE']).requirement.value
        report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'syntax':syntax,'imported_modules':imports,'foreign_key_check':foreign_keys,'integrity_check':integrity,'qt_rendering':'PySide6 6.11.2 offscreen, Windows fonts explicitly loaded','policy':{'500000':initial,'750000':changed,'execution_snapshot':historical},'graphs':a['graphs'],'screenshots':sorted(p.name for p in out.glob('*.png'))}
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); window.close(); user.close(); demo.controller.close()
    print(json.dumps(report,ensure_ascii=True)); return 0 if result.wasSuccessful() and syntax and not foreign_keys else 1

if __name__=='__main__':raise SystemExit(main())
