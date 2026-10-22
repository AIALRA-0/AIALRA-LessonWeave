"""把大幅静态原页分成无损小图，原图与来源坐标保持原样"""
from pathlib import Path
from PIL import Image


def prepare_tiles(root,manifest,pixel_budget=16_777_216,tile_edge=1024):
    root=Path(root).resolve();records=[]
    for key,page in manifest.get('pages',{}).items():
        raw=page.get('image','')
        image=(root/raw.lstrip('/')).resolve()
        if not image.is_relative_to(root) or not image.is_file() or image.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.bmp'}:continue
        # 原页可能比 Pillow 的默认像素提示更大，分块不会删掉原页或限制材料大小
        previous=Image.MAX_IMAGE_PIXELS;Image.MAX_IMAGE_PIXELS=None
        try:
            with Image.open(image) as source:
                width,height=source.size
                if width*height<=pixel_budget or getattr(source,'n_frames',1)>1:continue
                if source.mode not in {'RGB','RGBA','L','LA','P'}:continue
                if source.getexif().get(274,1)!=1:continue
                folder=image.with_name(image.stem+'-tiles');folder.mkdir(exist_ok=True)
                tiles=[]
                for top in range(0,height,tile_edge):
                    for left in range(0,width,tile_edge):
                        right,bottom=min(width,left+tile_edge),min(height,top+tile_edge)
                        target=folder/f'{top//tile_edge:04d}-{left//tile_edge:04d}.png'
                        if not target.is_file():source.crop((left,top,right,bottom)).save(target)
                        tiles.append({'image':'/'+target.relative_to(root).as_posix(),
                                      'bbox':[left/width*page['width'],top/height*page['height'],
                                              right/width*page['width'],bottom/height*page['height']]})
                page['tiles']=tiles
                if manifest.get('web',{}).get('image')==raw:manifest['web']['tiles']=tiles
                records.append({'page':key,'width':width,'height':height,'tiles':len(tiles),'original_preserved':True})
        finally:Image.MAX_IMAGE_PIXELS=previous
    return records
