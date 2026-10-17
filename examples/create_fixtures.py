"""生成可公开的小型材料，三个例子分别讨论展品、观察记录和代码数据流"""
from pathlib import Path
import json
import zipfile
import fitz

ROOT = Path(__file__).resolve().parent


def create():
    web = ROOT / 'web'
    web.mkdir(exist_ok=True)
    (web/'index.html').write_text('''<!doctype html><html><head><title>A painted sign on loan</title></head><body><main><h1>A painted sign on loan</h1><p>A museum lends a painted wooden sign for eight weeks. Keep the transport crate closed for the first 24 hours so the object can adjust gradually.</p><h2>Light and inspection</h2><p>Keep display lighting at 50 lux for six hours a day. Over 56 days, this uses 16,800 lux-hours of the 20,000 lux-hour allowance, leaving 3,200 lux-hours.</p><p>If a new crack appears, stop the display, photograph the crack and contact the lender before moving the sign.</p></main></body></html>''', 'utf-8')
    pdf = fitz.open()
    page = pdf.new_page(width=595,height=700)
    page.insert_text((45,55),'Bird counts on a fixed route',fontsize=20)
    text = ('Both surveys used the same 600 m route at 07:00 for 30 minutes.\n'
            'In week 1, observers counted 12 mallards, 5 moorhens and 8 coots.\n'
            'In week 2, they counted 9 mallards, 5 moorhens and 6 coots.\n'
            'The total fell from 25 to 20. Moorhen count stayed at 5, while its share rose\n'
            'from 20% to 25% because the total became smaller.\n\n'
            'Week 2 was windy. Wind can change how many birds observers detect.\n'
            'Two counts alone do not establish a population decline or a cause.\n'
            'Count each bird once; repeated sightings on the same route are not new birds.')
    page.insert_text((45,105),text,fontsize=11)
    page.insert_text((45,300),'Mallards observed',fontsize=12)
    for x,height,label in [(80,120,'Week 1: 12'),(240,90,'Week 2: 9')]:
        page.draw_rect(fitz.Rect(x,475-height,x+90,475),color=(.2,.4,.6),fill=(.3,.55,.7))
        page.insert_text((x,495),label,fontsize=12)
    page.insert_text((45,530),'Bar height shows observed count, not detection probability.',fontsize=11)
    pdf.save(ROOT/'bird-counts.pdf')
    source=ROOT/'code'
    source.mkdir(exist_ok=True)
    (source/'README.md').write_text('# Temperature report\n\nThe CLI reads a CSV file with station,value,unit headers, converts C/F readings to Celsius and prints sorted station means\nEmpty valid input produces no report rows\n','utf-8')
    (source/'report.py').write_text('''import csv
import math


def readings(path):
    with open(path, newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not {"station", "value", "unit"}.issubset(reader.fieldnames or []):
            raise ValueError("missing headers")
        for row in reader:
            station = row["station"].strip()
            unit = row["unit"].strip().upper()
            value = float(row["value"])
            if not station or not math.isfinite(value) or unit not in {"C", "F"}:
                raise ValueError("invalid reading")
            yield station, value if unit == "C" else (value - 32) * 5 / 9


def means(rows):
    groups = {}
    for station, value in rows:
        groups.setdefault(station, []).append(value)
    return [(station, sum(values) / len(values)) for station, values in sorted(groups.items())]
''','utf-8')
    (source/'main.py').write_text('''import sys
from report import readings, means

if __name__ == "__main__":
    for station, value in means(readings(sys.argv[1])):
        print(f"{station}: {value:.1f} C")
''','utf-8')
    with zipfile.ZipFile(ROOT/'temperature-report.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in source.iterdir():
            archive.write(path,'temperature-report/'+path.name)
    prompt='请围绕完整材料生成中文学习读本，小材料安排一章一节和二至三个递进问题，每个信息点都在正文实际解释，保留原文译文、图像、源码、来源和独立审查，作者中文省略中文句号'
    for name,kind,material in [('web','url','http://127.0.0.1:8969/index.html'),('pdf','file','bird-counts.pdf'),('code','repository','temperature-report.zip')]:
        (ROOT/(name+'.input.json')).write_text(json.dumps({'kind':kind,'material':material,'mode':'one_shot','system_prompt':prompt},ensure_ascii=False,indent=2),'utf-8')


if __name__=='__main__':
    create()
