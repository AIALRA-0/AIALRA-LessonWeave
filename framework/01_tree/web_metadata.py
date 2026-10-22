"""从原页读取署名、时间和链接，保留字段值与实际出处"""
import json
import re


META_FIELDS = {
    'author': 'author', 'article:author': 'author', 'dc.creator': 'author', 'citation_author': 'author',
    'article:published_time': 'published_time', 'datepublished': 'published_time', 'citation_publication_date': 'published_time',
    'article:modified_time': 'modified_time', 'datemodified': 'modified_time', 'last-modified': 'modified_time',
    'og:site_name': 'publisher', 'application-name': 'publisher', 'citation_journal_title': 'publisher',
    'og:title': 'title', 'twitter:title': 'title', 'citation_title': 'title',
    'og:url': 'url', 'citation_doi': 'identifier', 'dc.identifier': 'identifier',
    'description': 'description', 'og:description': 'description', 'keywords': 'keywords',
}


def metadata_fields(soup):
    rows = []
    def add(field, value, element):
        if isinstance(value, list):
            for item in value: add(field, item, element)
        elif isinstance(value, dict):
            add(field, value.get('name') or value.get('value') or value.get('@id') or value.get('url'), element)
        elif value is not None and str(value).strip():
            rows.append({'field': field, 'value': str(value).strip(), 'element': element})
    for element in soup.select('[rel~=author],[itemprop=author]'):
        add('author', element.get_text(' ', strip=True), element)
    for element in soup.find_all('meta'):
        name = (element.get('name') or element.get('property') or element.get('itemprop') or '').casefold()
        if name in META_FIELDS: add(META_FIELDS[name], element.get('content'), element)
    for element in soup.select('link[rel~=canonical]'): add('canonical_url', element.get('href'), element)
    for element in soup.select('script[type="application/ld+json"]'):
        try: value = json.loads(element.get_text())
        except (ValueError, TypeError): continue
        def visit(item):
            if isinstance(item, list):
                for child in item: visit(child)
            elif isinstance(item, dict):
                types = item.get('@type', [])
                types = [types] if isinstance(types, str) else types
                if any(str(t).split('/')[-1] in {'Article','NewsArticle','BlogPosting','TechArticle','ScholarlyArticle','Report'} for t in types):
                    for key, field in {'headline':'title','author':'author','datePublished':'published_time','dateModified':'modified_time',
                                       'publisher':'publisher','url':'url','identifier':'identifier','license':'license'}.items():
                        add(field, item.get(key), element)
                if '@graph' in item: visit(item['@graph'])
        visit(value)
    for row in list(rows):
        if soup.body is not None and row['field']in {'author','title','publisher'}:
            visible=soup.body.find(string=lambda text:str(text).strip()==row['value'])
            if visible is not None:rows.append({**row,'element':visible.parent})
    return rows


def hidden_control_frame(element):
    return (getattr(element,'name',None)=='iframe'
            and all(str(element.get(k,'')).strip() in {'0','0px'} for k in ['width','height'])
            and not any(str(element.get(k,'')).strip() for k in ['title','aria-label','aria-labelledby'])
            and not element.get_text(strip=True))


def reading_role(element, body):
    if hidden_control_frame(element):return 'hidden_control'
    ancestors = [element, *element.parents]
    signature = ' '.join(' '.join(p.get('class', [])) + ' ' + str(p.get('itemprop', '')) for p in ancestors if getattr(p, 'get', None))
    if re.search(r'byline|author|publish|post-date', signature, re.I): return 'metadata'
    if body in ancestors or element is body: return 'body'
    if any(getattr(p, 'name', None) in {'nav','footer','header','button','form'} or getattr(p, 'get', lambda *_: '')('role') == 'navigation' for p in ancestors):
        return 'structure'
    return 'unclassified'
