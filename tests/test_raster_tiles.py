from pathlib import Path
from PIL import Image,ImageChops
from lessonweave import pipeline
from raster_tiles import prepare_tiles


def test_tiles_keep_every_pixel_and_original_coordinates(tmp_path):
    source=Image.new('RGB',(79,113))
    source.putdata([(x%256,(x//79)%256,(x*3)%256) for x in range(79*113)])
    source.save(tmp_path/'page.png');before=(tmp_path/'page.png').read_bytes()
    page={'image':'/page.png','width':39.5,'height':56.5}
    manifest={'pages':{'page':page}}
    report=prepare_tiles(tmp_path,manifest,pixel_budget=100,tile_edge=32)
    restored=Image.new('RGB',source.size)
    for tile in page['tiles']:
        left,top,right,bottom=[round(x*2) for x in tile['bbox']]
        with Image.open(tmp_path/tile['image'].lstrip('/')) as fragment:
            assert fragment.size==(right-left,bottom-top)
            restored.paste(fragment,(left,top))
    assert ImageChops.difference(source,restored).getbbox() is None
    assert before==(tmp_path/'page.png').read_bytes()
    assert page['width']==39.5 and page['height']==56.5 and report[0]['tiles']==12


def test_small_original_needs_no_tiles(tmp_path):
    Image.new('RGB',(40,30),'white').save(tmp_path/'page.png')
    page={'image':'/page.png','width':40,'height':30}
    assert prepare_tiles(tmp_path,{'pages':{'p':page}})==[] and 'tiles' not in page
