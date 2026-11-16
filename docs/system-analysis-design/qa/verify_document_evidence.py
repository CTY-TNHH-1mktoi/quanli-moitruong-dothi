from pathlib import Path
import sys, unittest, json, datetime, hashlib

PROJECT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(PROJECT/'tests'))
modules=['test_locations','test_environment_reports','test_air_quality_map','test_chat_scope','test_chat_intents','test_chat_social','test_chat_knowledge','test_chat_advice','test_chat_relevance','test_chat_stream','test_chat_air_data','test_chat_weather_forecast','test_chat_clarification','test_chat_reading_followups','test_chat_followup_context','test_chat_consultation_why','test_chat_text_feedback','test_chat_feedback','test_chat_learning','test_chat_reviewed_safety','test_chat_training_state','test_restored_training_seed']

class Recorder(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append({'id':test.id(),'status':'passed'})
    def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'id':test.id(),'status':'failed'})
    def addError(self,test,err):super().addError(test,err);self.records.append({'id':test.id(),'status':'error'})
    def addSkip(self,test,reason):super().addSkip(test,reason);self.records.append({'id':test.id(),'status':'skipped','reason':reason})

suite=unittest.TestLoader().loadTestsFromNames(modules)
with (Path(__file__).parent/'document-evidence-tests.txt').open('w',encoding='utf-8') as log:
    result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=Recorder).run(suite)
state=json.loads((PROJECT/'recovery/history-restoration-20261027/restoration-state.json').read_text(encoding='utf-8'))
data={'checked_at':datetime.datetime.now().astimezone().isoformat(),'tests_run':result.testsRun,'passed':sum(x['status']=='passed' for x in result.records),'failures':len(result.failures),'errors':len(result.errors),'tests':result.records,'source_hashes':{name:hashlib.sha256((PROJECT/name).read_bytes()).hexdigest() for name in state['source_sha256'] if (PROJECT/name).is_file()},'changes_since_recorded_tests':[name for name,h in state['source_sha256'].items() if (PROJECT/name).is_file() and hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()!=h]}
(Path(__file__).parent/'document-evidence-tests.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in data.items() if k not in ['tests','source_hashes']},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() else 1)
