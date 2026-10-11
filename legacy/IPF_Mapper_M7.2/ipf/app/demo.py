"""Synthetic fixture loader. Reset replaces only the dedicated, marked demo database."""
import json
import os
import shutil
from pathlib import Path
from .controller import AppController

MARKER='ipf-m71-procurement-demo-v1'

def seed_demo(c):
    existing=c.row("SELECT value FROM app_metadata WHERE key='demo_seed'")
    if existing:
        if existing['value']!=MARKER: raise ValueError('Demo seed non riconosciuto.')
        return c.ipf_library()[0]['revision_id']
    if c.workspaces(): raise ValueError('Il seed richiede un database demo vuoto.')
    data=json.loads(Path(__file__).with_name('demo_rfq.json').read_text(encoding='utf-8'))
    w=c.create_workspace(data['name'],'Dati sintetici per validazione del dominio. Database separato.')
    _,r=c.create_model(w,data['name'],'M7.1-DEMO','AS_IS'); ids={}
    for code,name,y in data['functions']:
        ids[code]=c.add_entity(r,'INTERNAL_FUNCTION',name,code); c.save_layout(r,ids[code],0,y)
    for name in data['means']: ids[name]=c.add_entity(r,'MEANS',name)
    for e in data['elements']:
        iid=c.add_action(r,e['name'],ids.get(e.get('performer')),e['code']) if e['type']=='ACTION' else c.add_entity(r,e['type'],e['name'],e['code'])
        ids[e['code']]=iid; c.save_layout(r,iid,*e['xy'])
        for key,value in e.get('properties',{}).items(): c.set_definition_property(c.entity(r,iid)['definition_id'],key,value)
    for group,children in data['groups'].items():
        for child in children: c.add_relation(r,'CONTAINS',ids[group],ids[child])
    for s,t,info,means,lt in data['flows']:
        c.create_information_flow(r,ids[s],ids[t],ids[means],lead_time=lt,information_identity_id=ids[info])
    for action,info,semantic in data['information_links']: c.add_relation(r,semantic,ids[action],ids[info])
    for code,value in data['parameters'].items(): c.set_parameter(r,code,code,'BOOLEAN' if isinstance(value,bool) else 'NUMBER',value)
    for spec in data['rules']:
        recipe=spec['recipe']
        if recipe.get('kind')=='completed': recipe['identity_id']=ids[recipe.pop('element')]
        for side in ('left','right'):
            if side in recipe and 'element' in recipe[side]: recipe[side]['identity_id']=ids[recipe[side].pop('element')]
        c.save_state_rule(r,spec['name'],ids[spec['target']],spec['purpose'],recipe,spec['true'],spec['false'])
    execution=c.create_execution_snapshot(r,'DEMO PROJECT #001'); instances={}
    for event in data['observations']:
        instance=c.instantiate(execution,c.entity(r,ids[event['element']])['definition_id']); instances[event['key']]=instance
        for prop,value in event['values'].items(): c.observe(execution,instance,prop,value,event['recorded_at'])
    for newer,older in data['corrections']: c.add_correction(execution,instances[newer],instances[older])
    # Runtime relations are observed explicitly; they are never inferred from canvas geometry.
    for source,target,semantic in data.get('runtime_relations',[]):
        c.executions.instantiate_relation(execution,c.uow.catalogs.semantic(semantic)['id'],instances[source],instances[target])
    with c.con: c.con.execute('INSERT INTO app_metadata VALUES(?,?)',('demo_seed',MARKER))
    if c.rows('PRAGMA foreign_key_check'): raise ValueError('Violazione FK nel demo.')
    return r

class DemoStore:
    def __init__(self,directory):
        self.path=Path(directory)/'demo_m71.db'; self.controller=None
    def open(self):
        if not self.path.exists():return self.reset()
        self.controller=AppController(self.path)
        seed_demo(self.controller)
        return self.controller
    def reset(self):
        if self.controller:
            marker=self.controller.row("SELECT value FROM app_metadata WHERE key='demo_seed'")
            if not marker or marker['value']!=MARKER: raise ValueError('Reset consentito soltanto sul database demo identificato.')
        temp=self.path.with_suffix('.building.db')
        if temp.exists():
            raise ValueError('Esiste un precedente file demo in costruzione: conservarlo e rinominarlo prima di riprovare.')
        bundled=Path(__file__).parents[2]/'resources'/'demo_m71.db'
        temp.parent.mkdir(parents=True,exist_ok=True)
        if bundled.exists():shutil.copyfile(bundled,temp)
        fresh=AppController(temp)
        try:
            seed_demo(fresh)
            if fresh.rows('PRAGMA foreign_key_check'):raise ValueError('Demo non integro.')
        finally: fresh.close()
        if self.controller: self.controller.close()
        os.replace(temp,self.path)
        self.controller=AppController(self.path); return self.controller
