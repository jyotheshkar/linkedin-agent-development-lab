"""Editable, deterministic teaching diagrams. Run: python docs/architecture/diagrams.py.

SVG is the canonical vector artifact. If Pillow is installed, this same layout
also produces PNG previews. No external fonts/assets/network service required.
These are architecture maps, not evidence that an integration was executed.
"""
from __future__ import annotations
from html import escape
from pathlib import Path
import textwrap

OUT = Path(__file__).resolve().parent
INK = '#183333'
TEAL = '#087f7b'
MUTED = '#607575'
LINE = '#cbded9'
PALE = '#eef8f5'


class Diagram:
    def __init__(self, name, title, subtitle, height=900):
        self.name, self.title, self.subtitle = name, title, subtitle
        self.width, self.height = 1120, height
        self.items = []
        self.text(48, 52, title, 30, INK, True)
        self.text(48, 84, subtitle, 15, MUTED)

    def text(self, x, y, value, size=15, color=INK, bold=False):
        self.items.append(('text', x, y, value, size, color, bold))

    def rect(self, x, y, width, height, fill='#ffffff', stroke=LINE, radius=12, dash=False):
        self.items.append(('rect', x, y, width, height, fill, stroke, radius, dash))

    def box(self, x, y, width, height, title, lines=(), accent=False, dash=False):
        self.rect(x, y, width, height, PALE if accent else '#ffffff', TEAL if accent else LINE, dash=dash)
        self.text(x+18, y+29, title, 17, TEAL if accent else INK, True)
        cursor = y+53
        chars = max(18, int((width-36)/6.8))
        for line in lines:
            for wrapped in textwrap.wrap(line, width=chars) or ['']:
                self.text(x+18, cursor, wrapped, 13, MUTED)
                cursor += 19
        if cursor > y+height+5:
            raise ValueError(f'Box text exceeds layout: {self.name}/{title}')

    def arrow(self, points, label=None):
        self.items.append(('arrow', points, label))

    def note(self, y, text):
        self.rect(48, y, 1024, 62, PALE, LINE, 9)
        self.text(65, y+25, text[0], 14, TEAL, True)
        if len(text)>1:
            self.text(65, y+47, text[1], 13, MUTED)

    def save(self):
        svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" role="img" aria-labelledby="title description">',
             f'<title id="title">{escape(self.title)}</title><desc id="description">{escape(self.subtitle)}</desc>',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#087f7b"/></marker></defs>',
             '<rect width="100%" height="100%" fill="#ffffff"/>']
        for item in self.items:
            if item[0]=='rect':
                _,x,y,w,h,fill,stroke,radius,dash=item
                attr=' stroke-dasharray="7 5"' if dash else ''
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"{attr}/>')
            elif item[0]=='text':
                _,x,y,value,size,color,bold=item
                svg.append(f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{650 if bold else 400}" fill="{color}">{escape(value)}</text>')
            else:
                _,points,label=item
                coords=' '.join(f'{x},{y}' for x,y in points)
                svg.append(f'<polyline points="{coords}" fill="none" stroke="{TEAL}" stroke-width="1.8" marker-end="url(#arrow)"/>')
                if label:
                    x,y,value=label
                    svg.append(f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial,sans-serif" font-size="12" fill="{TEAL}">{escape(value)}</text>')
        svg.append('</svg>')
        (OUT/(self.name+'.svg')).write_text('\n'.join(svg)+'\n',encoding='utf-8')
        self.png()

    def png(self):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return
        image=Image.new('RGB',(self.width,self.height),'white'); draw=ImageDraw.Draw(image)
        def font(size,bold=False):
            candidates=[Path('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
            for path in candidates:
                if path.exists(): return ImageFont.truetype(str(path),size)
            return ImageFont.load_default()
        for item in self.items:
            if item[0]=='rect':
                _,x,y,w,h,fill,stroke,radius,dash=item
                draw.rounded_rectangle((x,y,x+w,y+h),radius=radius,fill=fill,outline=stroke,width=1)
            elif item[0]=='text':
                _,x,y,value,size,color,bold=item
                draw.text((x,y-size),value,font=font(size,bold),fill=color)
            else:
                _,points,label=item
                draw.line(points,fill=TEAL,width=2)
                (x0,y0),(x,y)=points[-2:]
                if x>x0: triangle=[(x,y),(x-8,y-4),(x-8,y+4)]
                elif x<x0: triangle=[(x,y),(x+8,y-4),(x+8,y+4)]
                elif y>y0: triangle=[(x,y),(x-4,y-8),(x+4,y-8)]
                else: triangle=[(x,y),(x-4,y+8),(x+4,y+8)]
                draw.polygon(triangle,fill=TEAL)
                if label:
                    lx,ly,value=label;draw.text((lx,ly-12),value,font=font(12),fill=TEAL)
        image.save(OUT/(self.name+'.png'))


def system():
    d=Diagram('system-anatomy','System anatomy','Development tools contain the runtime; future hosting is a separate, unexecuted delivery choice.',920)
    d.text(48,125,'DEVELOPMENT AND SOURCE',12,TEAL,True)
    d.box(48,145,310,106,'GitHub repository',['Private source + history','Tests, lock, lessons, diagrams'])
    d.box(405,145,310,106,'GitHub Codespace',['Python 3.12 development','Terminal + private preview'],True)
    d.box(762,145,310,106,'Future hosting',['Prepared configuration only','No deployment by this build'],dash=True)
    d.arrow([(358,198),(405,198)])
    d.rect(48,295,1024,472,'#f8fcfa',LINE)
    d.text(70,325,'PYTHON APPLICATION RUNTIME',12,TEAL,True)
    d.box(70,350,270,112,'CLI / FastAPI / console',['cli.py, web_api.py','Thin interfaces; same services'])
    d.box(405,350,310,112,'ApplicationService',['application.py','Input, artifacts, review, report'],True)
    d.box(780,350,270,112,'Workflow / LangGraph',['workflow.py + agent.py','State, policy, bounded tools'])
    d.arrow([(340,406),(405,406)]);d.arrow([(715,406),(780,406)])
    d.box(70,565,270,126,'RAGService',['service.py, knowledge.py','retrieval.py, grounding.py','Query + retained context'])
    d.box(405,565,310,126,'Atlas Lab',['atlas_lab.py','Versions, artifacts, events','Derived reporting projection'],True)
    d.box(780,565,270,126,'Simulated provider',['provider.py','Independent payload-bound','sim: receipts; no employer I/O'])
    d.arrow([(405,420),(373,420),(373,625),(340,625)])
    d.arrow([(560,462),(560,565)])
    d.arrow([(915,462),(915,565)])
    d.text(70,736,'Local MVP: SQLite/journal. Legacy Postgres workflow is separate; Atlas artifact parity is not assumed.',13,MUTED)
    d.note(800,['Tests/configuration support the runtime; learner scoring is a separate learning path.','Imported private snapshots stay untracked. Indexes and projections derive from eligible source evidence.'])
    d.save()


def request():
    d=Diagram('request-sequence','One request, visible boundaries','The shared application service coordinates this journey; arrows do not grant approval.',1200)
    rows=[
      ('01','CLI / API entry','Job + goal','cli.py / web_api.py'),
      ('02','Validate and identify','Strict Job + canonical target','contracts.py'),
      ('03','Prepare from evidence','Eligible knowledge -> RAG -> claims/gaps','ApplicationService + RAGService'),
      ('04','Write real local drafts','Application brief + outreach draft + hashes','materials.PendingMaterials.write'),
      ('05','Validate and bind proposals','Fixture/live planner; executor owns authority','ApplicationService._bound_calls'),
      ('06','Owner review checkpoint','Exact target/actions/artifacts/payload/policy','Changed content requires fresh review'),
      ('07','Store reviewed bytes','Immutable digest before dependent submit','Local artifact + evidence binding'),
      ('08','Simulate distinct effects','Application AND separate outreach receipts','FakeProvider: simulation only'),
      ('09','Record and verify reporting','Event commit -> projection revision/membership','Storage success is not delivery proof'),
      ('10','Return state and evidence','Gates, gaps, artifacts, trace, recovery ID','Inspect/draft completion != full unit')]
    for i,(number,title,body,module) in enumerate(rows):
        y=128+i*98
        d.text(65,y+31,number,18,TEAL,True)
        d.box(118,y,642,82,title,[body],accent=i==5)
        d.text(790,y+31,module,13,MUTED)
        if i<9:d.arrow([(440,y+82),(440,y+98)])
    d.save()


def rag():
    d=Diagram('rag-index-query','RAG: indexing time and query time','Semantic retrieval and model generation are independent adapter choices.',1060)
    d.text(48,127,'INDEXING TIME - REFRESH FROM ELIGIBLE KNOWLEDGE',12,TEAL,True)
    d.box(48,150,300,130,'Knowledge versions',['Latest version -> approval filter','Native source hash retained','Generated/eval/learning data excluded'])
    d.box(410,150,300,130,'Provenance chunks',['select_records / chunk_records','Stable IDs + record/version','Text hash != native hash'],True)
    d.box(772,150,300,130,'Embed and rebuild index',['FastEmbed semantic OR hash double','Qdrant local; model/dimension','Remove superseded/revoked sources'])
    d.arrow([(348,215),(410,215)]);d.arrow([(710,215),(772,215)])
    d.text(48,343,'QUERY TIME - USE ONLY CONTEXT THAT ACTUALLY FITS',12,TEAL,True)
    d.box(48,368,300,116,'Query and search',['Query embedding -> vector query','Metadata filter, score rule, top-k','rank_hits: not a truth score'])
    d.box(410,368,300,116,'Bound retained context',['build_context: whole chunks','Keep IDs; evidence is untrusted','Character budget != token count'],True)
    d.box(772,368,300,116,'Generate structured answer',['Extractive OR real model adapter','Claims + evidence IDs + gaps','Output headroom in model budget'])
    d.arrow([(922,280),(922,316),(27,316),(27,426),(48,426)])
    d.arrow([(348,426),(410,426)]);d.arrow([(710,426),(772,426)])
    d.box(410,577,300,142,'Validate and review',['validate_answer against retained IDs','Exact quotes; conflict -> review','Unknown evidence -> gap/abstain','Structural validity != entailment'],True)
    d.arrow([(922,484),(922,648),(710,648)])
    d.box(48,787,470,126,'System evaluation - separate collection',['Held-out queries and expected IDs are not indexed.','Recall, citations, labelled support, abstention','Agreement with labels is not open-ended truth.'])
    d.box(592,787,480,126,'Source / mode boundaries',['Private Atlas import is read-only, not live sync.','Live generation is not proven by embedding tests.','All employer effects remain simulated.'])
    d.save()


def recovery():
    d=Diagram('state-recovery','State and recovery','Persist intent before effects; preserve reviewed payloads during retries and reconciliation.',1010)
    d.box(48,142,300,108,'Prepared drafts',['Evidence + artifacts + action plan','Await exact owner review'])
    d.box(410,142,300,108,'Reviewed material',['Approve exact binding OR reject','No model-supplied approval'],True)
    d.box(772,142,300,108,'Running',['Persist intent, then provider call','Validate output before acceptance'])
    d.arrow([(348,196),(410,196)]);d.arrow([(710,196),(772,196)])
    d.box(48,360,300,134,'Known pre-effect failure',['Declared transient -> bounded retry','Permanent/validation -> blocked','Budget stays finite'])
    d.box(410,360,300,134,'Unknown outcome / pending',['Effect may already exist','Reserve work; do not repeat','Journal failure follows same path'],True)
    d.box(772,360,300,134,'Verified provider receipt',['Gate + action identity + payload','Same receipt survives restart','No duplicate employer simulation'])
    d.arrow([(922,250),(922,300),(198,300),(198,360)])
    d.arrow([(922,250),(922,320),(560,320),(560,360)])
    d.arrow([(48,420),(26,420),(26,280),(950,280),(950,250)],(62,272,'declared transient + budget: retry'))
    d.arrow([(710,427),(772,427)],(716,412,'reconcile'))
    d.box(48,609,300,130,'Blocked / rejected',['No automatic effect repetition','Fix cause and obtain fresh review','Preserve known receipt evidence'])
    d.box(410,609,300,130,'Ledger / projection pending',['Repair event logging or projection','Do not repeat application/outreach','Verify revision and membership'],True)
    d.box(772,609,300,130,'Plan finished',['Inspect/draft may validly finish','Full unit needs all verified gates','Pending delivery != full completion'])
    d.arrow([(198,494),(198,609)])
    d.arrow([(922,494),(922,548),(560,548),(560,609)])
    d.arrow([(710,674),(772,674)],(716,659,'verified'))
    d.note(832,['Restart reconstructs state from durable evidence, not an in-memory RAG cache.','A stable hash alone does not ensure exactly-once behavior; provider uniqueness and payload checks matter.'])
    d.save()


def learning():
    d=Diagram('learning-map','Learning map: one component at a time','The complete product is available; optional experiments do not gate application startup.',940)
    entries=[
      ('01 / VISUAL','Locate the boundary','System/sequence diagram + lesson ID'),
      ('02 / SOURCE','Read exact symbols','Current branch/commit + linked tests'),
      ('03 / EXECUTION','Trace one input','Accepted path + one rejected boundary'),
      ('04 / EXPERIMENT','Change one isolated thing','Copied fixture or temporary test; safe reset'),
      ('05 / VERIFY','Run the targeted check','Record actual result and limitation'),
      ('06 / EXPLAIN','Discuss mechanism and trade-off','L1 implementation / L2 design preparation')]
    for i,(number,title,line) in enumerate(entries):
        x=48 if i%2==0 else 592;y=145+(i//2)*190
        d.box(x,y,480,130,title,[number,line],accent=i in (0,3))
    d.arrow([(528,210),(592,210)])
    d.arrow([(832,275),(832,310),(288,310),(288,335)])
    d.arrow([(528,400),(592,400)])
    d.arrow([(832,465),(832,500),(288,500),(288,525)])
    d.arrow([(528,590),(592,590)])
    d.note(758,['Learning evidence is separate from system evaluation and recruitment outcome.','No graded attempts = N/A. Reference exposure is allowed; independent mastery needs fresh observed transfer.'])
    d.save()


if __name__=='__main__':
    for make in (system,request,rag,recovery,learning): make()
    print('Generated five SVG diagrams and optional PNG previews from one editable layout source.')
