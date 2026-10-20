/* 每个问题完整讲完后提供一个笔记框，原材料与覆盖记录按当前样稿版本读取 */
(() => {
  const get = id => document.getElementById(id);
  // 标题已经带编号时直接显示，旧数据则由页面补齐编号后的点
  const numberedTitle = (number, title) => /^\d+(?:\.\d+)*\.\s/.test(title)
    ? title : String(number).replace(/\.+$/, '') + '. ' + title;
  const internalTitle = title => String(title);
  const make = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  let data;
  let sourcePack = null;
  let explanationCoverage = null;
  let activeQuestion = null;
  let sourcePreview = null;
  let glossaryPreview = null;
  let sourceTimer;
  let glossaryTimer;
  let glossaryRestoreTimer;
  let sourceRestoreTimer;
  let sourceLanguage = 'both';
  let originalSourcePack = null;
  let documentPath = '/05_writing/demo.json';
  let isPreview = false;
  let readerReady = false;
  let sourceLinks = {};
  let readerRepairs = {};
  const noteAliases = new Map();

  const readingState = () => ({ doc: data, sourcePack: originalSourcePack, coverage: explanationCoverage,
    document_path: documentPath, source_pack_path: data?.grounding?.source_pack_path,
    preview: isPreview, ready: readerReady, selection: currentSourceSelection() });
  window.ReaderSourceBridge = { getState: readingState };

  function currentSourceSelection() {
    if (!sourcePack) return null;
    return { refs: sourcePreview ? sourceLinks[sourcePreview.blockId] || [] : selectedSources(activeQuestion).map(source => ({ source_id: source.id })),
      block_id: sourcePreview?.blockId || null, question_id: activeQuestion };
  }

  function emitSourceSelection() {
    const selection = currentSourceSelection();
    if (selection) document.dispatchEvent(new CustomEvent('reading:source-selection', { detail: selection }));
  }

  function sourceScrollPane() { return get('source-text-scroll') || get('demo-original'); }

  // 临时对照结束后恢复原节点、展开状态与滚动位置，阅读进度随当前浏览器保留
  function restoreScroll(pane, top) {
    if (pane) pane.scrollTo({ top, behavior: 'instant' });
  }

  function showDebug(enabled) {
    document.body.classList.toggle('show-debug', enabled);
    if (!enabled) {
      document.body.classList.remove('show-writing-roles');
      if (get('show-roles')) get('show-roles').checked = false;
    }
    if (sourcePack && activeQuestion) {
      const current = activeQuestion;
      const preview = sourcePreview && { blockId: sourcePreview.blockId, pinned: sourcePreview.pinned, focusActive: sourcePreview.focusActive };
      const scroll = sourceScrollPane().scrollTop;
      restoreSources();
      activeQuestion = null;
      chooseQuestion(current, true);
      if (preview) previewSources(preview.blockId, preview.pinned, preview.focusActive);
      else restoreScroll(sourceScrollPane(), scroll);
    }
  }

  function setSourceLanguage(value) {
    sourceLanguage = ['zh', 'en', 'both'].includes(value) ? value : 'both';
    if (get('demo-original')) get('demo-original').dataset.language = sourceLanguage;
    if (get('source-language-select')) get('source-language-select').value = sourceLanguage;
    try { localStorage.setItem('infiniteqa:source-language', sourceLanguage); } catch (error) { console.debug(error); }
  }

  function imageRegion(sourceId, regionId) {
    const regions = sourcePack?.image_regions?.[sourceId];
    if (!regions || !regionId) return null;
    const id = regions[regionId] ? regionId : String(regionId).split('.')[0];
    return regions[id] ? { ...regions[id], id } : null;
  }

  function sourceImage(asset, caption, region) {
    const link = make('a', undefined, region ? 'source-region-image' : 'source-full-image');
    link.href = projectPath(asset);
    link.target = '_blank';
    link.rel = 'noopener';
    link.setAttribute('aria-label', '打开完整原图');
    if (region?.bbox?.length === 4 && region?.image_size?.length === 2) {
      const [x, y, width, height] = region.bbox;
      const [imageWidth, imageHeight] = region.image_size;
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', `${x} ${y} ${width} ${height}`);
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', caption || region.label || '原图的对应区域');
      const image = document.createElementNS('http://www.w3.org/2000/svg', 'image');
      image.setAttribute('href', projectPath(asset));
      image.setAttribute('width', imageWidth);
      image.setAttribute('height', imageHeight);
      svg.append(image);
      link.append(svg);
    } else {
      const image = make('img');
      image.src = projectPath(asset);
      image.alt = caption || '原材料中的图片';
      image.loading = 'lazy';
      link.append(image);
    }
    return link;
  }

  const projectPath = value => window.LWPath ? window.LWPath(value) : '/' + String(value).replace(/^\/+/, '');

  function openPane(name) {
    window.ReaderUI?.openPane(name);
    document.body.dataset.activePane = name;
    document.querySelectorAll('[data-open-pane]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.openPane === name));
    });
  }

  function focusBlock(id) {
    const target = get('block-' + id);
    if (!target) return;
    const unit = target.closest('[data-unit-question]');
    if (unit) chooseQuestion(unit.dataset.unitQuestion, true);
    openPane('lesson');
    target.tabIndex = -1;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.classList.add('writing-block-highlight');
    setTimeout(() => target.classList.remove('writing-block-highlight'), 2500);
  }

  function sourceIds(source) {
    return new Set([source.id, ...(source.source_ids || [])]);
  }

  // 原图、图容器与图注共用一个阅读视图，各自的来源 ID 和原始文字仍然保留
  function mergeSourceViews(sources) {
    const groups = [];
    for (const source of sources) {
      const ids = sourceIds(source);
      const related = groups.filter(group => [...sourceIds(group)].some(id => ids.has(id)));
      if (!related.length) {
        groups.push({ ...source, source_ids: [...ids], sentences: [...(source.sentences || [])], scope_notes: source.scope_note ? [source.scope_note] : [] });
        continue;
      }
      const group = related[0];
      const members = [...related.slice(1), source];
      for (const member of members) {
        group.source_ids = [...new Set([...group.source_ids, ...sourceIds(member)])];
        for (const sentence of member.sentences || []) {
          if (!group.sentences.some(existing => existing.id === sentence.id)) group.sentences.push(sentence);
        }
        group.original_texts = { ...(group.original_texts || {}), ...(member.original_texts || {}) };
        group.scope_notes = [...new Set([...group.scope_notes, ...(member.scope_notes || []), ...(member.scope_note ? [member.scope_note] : [])])];
        if (!group.asset && member.asset) group.asset = member.asset;
        if (!group.caption && member.caption) group.caption = member.caption;
        if (!group.chart_data && member.chart_data) group.chart_data = member.chart_data;
        if (member.type === 'figure') {
          group.id = member.id;
          group.type = member.type;
        }
      }
      for (const duplicate of related.slice(1)) groups.splice(groups.indexOf(duplicate), 1);
    }
    return groups;
  }

  function hasReadingMaterial(source, selection = null) {
    if (source.asset) return true;
    const sentences = source.sentences || [];
    if (!sentences.length) return !selection && Object.values(source.original_texts || {}).some(text => String(text).trim());
    return sentences.some(sentence => sentence.evidence_kind !== 'material_index' && sentence.original?.trim() &&
      (!selection || selection.sentenceIds.has(sentence.id) || [...selection.regionIds].some(id => sentence.region === id || sentence.region?.startsWith(id + '.'))));
  }

  function selectedSources(questionId) {
    const unit = data.units.find(item => item.question_id === questionId);
    const wanted = new Set(unit?.source_nodes || []);
    if (isPreview && unit) {
      for (const block of [unit.problem, ...unit.explanation, unit.synthesis]) {
        for (const reference of sourceLinks[block.id] || []) wanted.add(reference.source_id);
      }
    }
    for (const item of explanationCoverage?.items || []) {
      if (item.points.some(point => point.question_id === questionId)) wanted.add(item.source_id);
    }
    const backgroundIds = new Set((explanationCoverage?.items || []).filter(item => item.role === 'context').map(item => item.source_id));
    return sourcePack.sources.filter(source => [...sourceIds(source)].some(id => wanted.has(id)))
      .filter(source => hasReadingMaterial(source) || document.body.classList.contains('show-debug'))
      .sort((a, b) => Number(backgroundIds.has(a.id)) - Number(backgroundIds.has(b.id)));
  }

  function sourceLocation(source) {
    const location = source.source || {};
    const labels = [];
    if (location.page !== undefined) labels.push('第 ' + location.page + ' 页');
    if (location.line_start !== undefined) {
      labels.push('第 ' + location.line_start + (location.line_end && location.line_end !== location.line_start ? '—' + location.line_end : '') + ' 行');
    }
    if (location.path) labels.push(location.path);
    return labels.join(' · ');
  }

  function sentencePair(source, sentence, highlighted = false) {
    const pair = make('div', undefined, 'source-sentence-pair' + (highlighted ? ' source-sentence-highlight' : '') +
      (sentence.evidence_kind === 'material_index' ? ' debug-only' : ''));
    pair.dataset.sentenceId = sentence.id;
    pair.tabIndex = 0;
    pair.setAttribute('aria-label', '定位原句 ' + sentence.id);
    pair.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); pair.click(); }
    });
    const literalCode = source.type === 'code' || source.verbatim_code || sentence.verbatim_code;
    const generatedIndex = sentence.evidence_kind === 'material_index';
    const english = !literalCode && !generatedIndex && typeof sentence.english === 'string' && sentence.english.trim() ? sentence.english : null;
    const chineseOriginal = /[\u4e00-\u9fff]/u.test(sentence.original);
    pair.dataset.readingLanguage = literalCode ? 'code' : chineseOriginal ? 'zh' : 'other';
    const singleOriginal = literalCode || generatedIndex || (!english && (chineseOriginal || !sentence.translation));
    const chinese = chineseOriginal ? sentence.original : sentence.translation || null;
    if (chinese && !singleOriginal) {
      const translation = make('div', undefined, 'source-translation');
      translation.append(make('span', chinese === sentence.original ? '原文' : '译文', 'source-text-label'), make('p', chinese));
      pair.append(translation);
    }
    const original = make('div', undefined, 'source-original' + (literalCode ? ' source-code' : '') + (singleOriginal ? ' source-single-language' : ''));
    original.append(make('span', english ? '英文译文' : '原文', 'source-text-label'));
    original.append(make(literalCode || generatedIndex ? 'pre' : 'p', english || sentence.original));
    pair.append(original);
    return pair;
  }

  function renderSourceCard(source, selection = null) {
    const card = make('section', undefined, 'demo-source-card');
    if (!hasReadingMaterial(source, selection)) card.classList.add('debug-only');
    card.id = 'source-' + source.id;
    card.dataset.sourceId = source.id;
    const location = sourceLocation(source);
    if (location) card.append(make('p', location, 'help debug-only'));
    const relatedCoverage = (explanationCoverage?.items || []).filter(item => sourceIds(source).has(item.source_id));
    const scopeNotes = [...new Set([...(source.scope_notes || []), ...relatedCoverage.map(item => item.scope_note).filter(Boolean)])];
    if (scopeNotes.length) {
      const scope = make('details', undefined, 'source-scope debug-only');
      scope.append(make('summary', '本节负责讲清哪些内容'));
      for (const text of scopeNotes) scope.append(make('p', text, 'help'));
      card.append(scope);
    }
    const imageAsset = source.asset && /\.(?:png|jpe?g|gif|webp|svg|bmp|avif|ico)(?:[?#]|$)/i.test(source.asset);
    if (imageAsset) {
      const figure = make('figure', undefined, 'demo-source-figure');
      const ids = [...sourceIds(source)];
      const wantedRegions = [...(selection?.regionIds || [])];
      const regionEntries = wantedRegions.map(id => ids.map(sourceId => imageRegion(sourceId, id)).find(Boolean)).filter(Boolean);
      const uniqueRegions = regionEntries.filter((region, index) => regionEntries.findIndex(other => JSON.stringify(other.bbox) === JSON.stringify(region.bbox)) === index);
      if (uniqueRegions.length) uniqueRegions.forEach(region => {
        const part = make('div', undefined, 'source-image-region');
        part.append(sourceImage(source.asset, '原图的对应区域', region));
        figure.append(part);
      });
      else figure.append(sourceImage(source.asset, '原图'));
      const full = make('a', '打开完整原图', 'text-action');
      full.href = projectPath(source.asset);
      full.target = '_blank'; full.rel = 'noopener';
      figure.append(full);
      card.append(figure);
    } else if (source.asset) {
      // 附件沿用原文件名和原文件链接，字体、PDF 等资源保留完整索引原句
      const attachment = make('p', undefined, 'source-attachment');
      const filename = String(source.asset).split(/[?#]/)[0].split('/').pop();
      const link = make('a', filename, 'text-action');
      link.href = projectPath(source.asset);
      link.target = '_blank'; link.rel = 'noopener';
      link.setAttribute('aria-label', '打开原文件：' + filename);
      attachment.append(link);
      card.append(attachment);
    }
    let imageLabels = null;
    const sentences = source.sentences || [];
    if (imageAsset && sentences.some(sentence => sentence.region)) {
      imageLabels = make('details', undefined, 'source-image-labels debug-only');
      imageLabels.append(make('summary', '查看图中文字与逐项译文（' + sentences.filter(sentence => sentence.region).length + ' 项）'));
    }
    const selectedRegions = selection?.regionIds || new Set();
    const selectedSentences = selection?.sentenceIds || new Set();
    for (const sentence of sentences) {
      const selected = selectedSentences.has(sentence.id) || [...selectedRegions].some(id => sentence.region === id || sentence.region?.startsWith(id + '.'));
      if (sentence.region && imageLabels) {
        imageLabels.append(sentencePair(source, sentence));
        if (selection && selected) card.append(sentencePair(source, sentence, true));
        else if (!selection && /\.(title|subtitle|metric)$/.test(sentence.region)) card.append(sentencePair(source, sentence));
      } else if (!selection || selected) card.append(sentencePair(source, sentence, !!selection));
    }
    if (imageLabels) card.append(imageLabels);
    const readable = sentences.filter(sentence => sentence.evidence_kind !== 'material_index');
    const hasChineseReading = readable.some(sentence => !source.verbatim_code && source.type !== 'code' && !sentence.verbatim_code &&
      (/[\u4e00-\u9fff]/u.test(sentence.original) || sentence.translation?.trim()));
    if (!hasChineseReading && readable.length) {
      const code = source.type === 'code' || source.verbatim_code || readable.some(sentence => sentence.verbatim_code);
      card.append(make('p', code ? '这段源码保留原样，上方可按行号查看' : '这份材料暂无对应译文，上方保留原件', 'source-translation-empty help'));
    }
    if (!sentences.length && !source.asset) {
      for (const text of Object.values(source.original_texts || {})) {
        card.append(make('p', text, 'source-original'));
      }
    }
    if (explanationCoverage) {
      const items = explanationCoverage.items.filter(item => sourceIds(source).has(item.source_id));
      const details = make('details', undefined, 'source-coverage debug-only');
      const points = items.flatMap(item => item.points).filter((point, index, all) =>
        point.question_id === activeQuestion && all.findIndex(other => other.id === point.id) === index);
      if (points.length) {
        details.append(make('summary', '这些材料在哪里讲清楚'));
        for (const point of points) details.append(pointRow(point));
        card.append(details);
      }
    }
    return card;
  }

  function chooseQuestion(questionId, explicit = false) {
    if (!sourcePack || (sourcePreview && !explicit) || activeQuestion === questionId) return;
    if (explicit && sourcePreview) restoreSources();
    activeQuestion = questionId;
    const select = get('source-unit-select');
    select.value = questionId;
    const unit = data.units.find(item => item.question_id === questionId);
    const sources = selectedSources(questionId);
    get('source-context').textContent = sources.length ? (unit?.number || '') + ' · ' + sources.length + ' 组对应材料' : '';
    get('source-cards').replaceChildren(...sources.map(source => renderSourceCard(source)));
    document.querySelectorAll('[data-outline-question]').forEach(button => {
      const active = button.dataset.outlineQuestion === questionId;
      if (active) button.setAttribute('aria-current', 'true');
      else button.removeAttribute('aria-current');
    });
    document.querySelectorAll('[data-unit-question]').forEach(unitNode => {
      unitNode.classList.toggle('active-writing-unit', unitNode.dataset.unitQuestion === questionId);
    });
    emitSourceSelection();
  }

  function focusSource(sourceId, questionId) {
    if (!sourcePack) return;
    if (!questionId) {
      questionId = explanationCoverage.items.find(item => item.source_id === sourceId)?.points[0]?.question_id;
    }
    restoreSources();
    if (questionId) chooseQuestion(questionId, true);
    let target = get('source-' + sourceId);
    if (!target) {
      const source = sourcePack.sources.find(item => sourceIds(item).has(sourceId));
      if (source) target = get('source-' + source.id);
    }
    openPane('source');
    if (!target) return;
    document.dispatchEvent(new CustomEvent('reading:source-focus', { detail: { source_id: sourceId } }));
    target.tabIndex = -1;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function restoreSources() {
    clearTimeout(sourceTimer);
    clearTimeout(sourceRestoreTimer);
    if (!sourcePreview) return;
    const snapshot = sourcePreview;
    sourcePreview = null;
    get('source-cards').replaceChildren(...snapshot.cards);
    get('source-context').textContent = snapshot.context;
    get('source-preview-controls').hidden = true;
    document.querySelectorAll('.source-marker[aria-pressed="true"]').forEach(button => button.setAttribute('aria-pressed', 'false'));
    restoreScroll(sourceScrollPane(), snapshot.scroll);
    emitSourceSelection();
  }

  function previewSources(blockId, pinned = false, fromFocus = false) {
    clearTimeout(sourceTimer);
    clearTimeout(sourceRestoreTimer);
    const references = sourceLinks[blockId];
    if (!references?.length) return;
    const pane = sourceScrollPane();
    if (!sourcePreview) sourcePreview = {
      cards: [...get('source-cards').childNodes],
      scroll: pane.scrollTop,
      context: get('source-context').textContent,
      pinned: false
    };
    sourcePreview.blockId = blockId;
    sourcePreview.focusActive = fromFocus;
    sourcePreview.pinned = pinned || sourcePreview.pinned;
    const groups = new Map();
    for (const reference of references) {
      const source = sourcePack.sources.find(item => sourceIds(item).has(reference.source_id));
      if (!source) continue;
      if (!groups.has(source.id)) groups.set(source.id, { source, sentenceIds: new Set(), regionIds: new Set() });
      const group = groups.get(source.id);
      (reference.sentence_ids || []).forEach(id => group.sentenceIds.add(id));
      (reference.region_ids || []).forEach(id => group.regionIds.add(id));
    }
    if (!document.body.classList.contains('show-debug')) {
      for (const [id, group] of groups) if (!hasReadingMaterial(group.source, group)) groups.delete(id);
    }
    if (!groups.size) { restoreSources(); return; }
    get('source-cards').replaceChildren(...[...groups.values()].map(group => renderSourceCard(group.source, group)));
    get('source-context').textContent = '当前讲解段落对应的材料';
    get('source-preview-caption').textContent = sourcePreview.pinned ? '已保持段落对照' : '正在对照这个段落';
    get('source-preview-controls').hidden = false;
    document.querySelectorAll('.source-marker').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.sourceBlock === blockId)));
    restoreScroll(pane, 0);
    emitSourceSelection();
    if (pinned) openPane('source');
  }

  function deferRestoreSources() {
    clearTimeout(sourceRestoreTimer);
    sourceRestoreTimer = setTimeout(() => {
      const focused = document.activeElement;
      const keyboardFocus = sourcePreview?.focusActive && focused?.matches(':focus-visible') && (get('demo-original').contains(focused) || focused.classList.contains('source-marker'));
      if (sourcePreview && !sourcePreview.pinned && !get('demo-original').matches(':hover') && !keyboardFocus) restoreSources();
    }, 180);
  }

  document.addEventListener('reading:clear-preview', event => {
    if (event.detail.pane === 'source') restoreSources();
    if (event.detail.pane === 'glossary') restoreGlossary();
  });

  function attachSourceMarkers() {
    for (const [blockId, references] of Object.entries(sourceLinks)) {
      const target = get('block-' + blockId);
      if (!target || !references.length) continue;
      const button = make('button', '↗', 'source-marker');
      button.type = 'button';
      button.dataset.sourceBlock = blockId;
      if (!references.some(reference => {
        const source = sourcePack.sources.find(item => sourceIds(item).has(reference.source_id));
        return source && hasReadingMaterial(source, { sentenceIds: new Set(reference.sentence_ids || []), regionIds: new Set(reference.region_ids || []) });
      })) button.classList.add('debug-only');
      const pending = isPreview && Boolean(data.preview_source_links?.[blockId]?.length);
      button.dataset.sourceReview = pending ? 'pending' : 'reviewed';
      button.setAttribute('aria-label', pending ? '对照这个段落的原文片段，来源对应待审' : '对照这个段落的原文片段');
      button.setAttribute('aria-controls', 'source-cards');
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('pointerenter', () => {
        clearTimeout(sourceRestoreTimer);
        clearTimeout(sourceTimer);
        sourceTimer = setTimeout(() => previewSources(blockId), 90);
      });
      button.addEventListener('pointerleave', () => { clearTimeout(sourceTimer); deferRestoreSources(); });
      button.addEventListener('focus', () => previewSources(blockId, false, true));
      button.addEventListener('blur', deferRestoreSources);
      button.addEventListener('click', event => { event.stopPropagation(); previewSources(blockId, true); });
      target.prepend(button);
      target.classList.add('has-source-marker');
    }
    const pane = get('demo-original');
    pane.addEventListener('pointerenter', () => clearTimeout(sourceRestoreTimer));
    pane.addEventListener('pointerleave', deferRestoreSources);
    pane.addEventListener('focusin', () => { if (sourcePreview) sourcePreview.focusActive = true; });
    pane.addEventListener('focusout', deferRestoreSources);
    get('source-preview-back').onclick = restoreSources;
  }

  function pointRow(point) {
    const row = make('div', undefined, 'coverage-point');
    const state = make('span', point.explained ? '✓ 本节负责内容已讲解' : '本节内容待讲清', 'coverage-point-state');
    row.append(state, make('p', point.description));
    if (point.block_ids?.length) {
      const links = make('div', undefined, 'coverage-block-links');
      point.block_ids.forEach((id, index) => {
        const button = make('button', point.block_ids.length === 1 ? '查看讲解' : '讲解 ' + (index + 1), 'text-action');
        button.type = 'button';
        button.dataset.targetBlock = id;
        button.onclick = () => focusBlock(id);
        links.append(button);
      });
      row.append(links);
    }
    return row;
  }

  function renderCoverage() {
    const coverage = explanationCoverage;
    get('coverage-details').hidden = false;
    get('coverage-summary').textContent = `本节讲解覆盖 ${coverage.percentage}% · ${coverage.explained_points}/${coverage.total_points} 个信息点`;
    const list = get('coverage-items');
    for (const item of coverage.items) {
      const details = make('details', undefined, 'coverage-source');
      details.dataset.coverageSource = item.source_id;
      details.append(make('summary', item.source_id));
      details.append(make('p', item.explained ? '✓ 本节负责内容已讲解' : '本节内容待讲清', 'coverage-point-state'));
      if (item.scope_note) details.append(make('p', item.scope_note, 'coverage-scope-note'));
      const sourceLink = make('button', '定位原材料', 'text-action');
      sourceLink.type = 'button';
      sourceLink.onclick = () => focusSource(item.source_id);
      details.append(sourceLink);
      for (const point of item.points) details.append(pointRow(point));
      list.append(details);
    }
  }

  function renderLocalNotations(article) {
    if (!data.local_notations?.length) return;
    const details = make('details', undefined, 'debug-only');
    details.id = 'local-notations-debug';
    details.append(make('summary', '局部符号怎样在正文中定义和使用'));
    const record = make('pre', JSON.stringify(data.local_notations, null, 2));
    details.append(record);
    article.append(details);
  }

  function renderOutline() {
    const toc = get('demo-outline');
    if (!toc) return;
    get('demo-directory').hidden = false;
    const opening = make('button', '承上启下', 'demo-outline-section');
    opening.type = 'button';
    opening.onclick = () => focusBlock(data.opening.id);
    const core = make('button', '核心问题', 'demo-outline-section');
    core.type = 'button';
    core.onclick = () => get('writing-core-questions')?.scrollIntoView({behavior:'smooth', block:'start'});
    toc.append(opening, core);
    for (const unit of data.units) {
      const button = make('button', numberedTitle(unit.number, unit.title), 'demo-outline-question');
      button.type = 'button';
      button.dataset.outlineQuestion = unit.question_id;
      button.onclick = () => {
        chooseQuestion(unit.question_id, true);
        focusBlock(unit.problem.id);
      };
      toc.append(button);
      const unitNode = document.querySelector('[data-unit-question="' + CSS.escape(unit.question_id) + '"]');
      const counters = new Map(); let groupNumber = unit.number.replace(/\.$/,'');
      const headings=[...unitNode?.querySelectorAll('h4,h5,h6,.lw-media>.lw-media-figure>figcaption') || []];
      for (const heading of headings) {
        if (heading.closest('.writing-note')) continue;
        if (heading.closest('.debug-only')) continue;
        const media = heading.closest('.lw-media');
        const segment = heading.closest('.lw-media-code-segment');
        const caption=heading.tagName==='FIGCAPTION';
        let depth = media ? (caption ? 2 : segment && heading.tagName === 'H6' ? 4 : 3) : 1;
        const plain = heading.textContent.replace(/^(?:\d+\.)+\s*/, '');
        if (depth === 1) groupNumber = heading.textContent.match(/^(?:\d+\.)+/)?.[0]?.replace(/\.$/,'') || unit.number.replace(/\.$/,'') + '.' + ((counters.get('groups')||0)+1);
        let prefix = groupNumber;
        if(media && !caption){
          const parent=depth===4 ? segment.dataset.readerNumber : media.dataset.mediaNumber;
          const count=(counters.get(parent)||0)+1;counters.set(parent,count);prefix=parent+'.'+count;
          if(segment && depth===3)segment.dataset.readerNumber=prefix;
        }
        if (depth === 1) counters.set('groups',(counters.get('groups')||0)+1);
        // 编号来自当前页面的父子关系，只改变显示，保留正文块和来源 ID
        if(!caption)heading.textContent=prefix+'. '+plain;
        heading.dataset.readerDepth=depth;
        if (!heading.id) heading.id = 'heading-' + unit.question_id + '-' + headings.indexOf(heading);
        const link = make('button', heading.textContent, 'demo-outline-detail'); link.type='button';
        link.dataset.readerDepth=depth;link.style.setProperty('--outline-depth',depth);
        link.dataset.headingId = heading.id;
        link.onclick = () => {openPane('lesson');chooseQuestion(unit.question_id,true);history.replaceState(null,'','#'+heading.id);(caption?media:heading).scrollIntoView({block:'start',behavior:'smooth'});};
        toc.append(link);
      }
    }
    for (const [title, id] of [['内容总结', 'writing-summary'], ['易错点', 'writing-pitfalls'], ['问答', 'writing-quiz']]) {
      const button = make('button', title, 'demo-outline-section');
      button.type = 'button';
      button.onclick = () => { openPane('lesson'); get(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
      toc.append(button);
    }
  }

  async function loadGrounding() {
    if (!get('demo-directory')) return;
    renderOutline();
    if (!data.grounding) {
      document.body.classList.add('legacy-demo');
      return;
    }
    try {
      const responses = await Promise.all([
        fetch(projectPath(data.grounding.source_pack_path), { cache: 'no-store' }),
        fetch(projectPath(data.grounding.coverage_path), { cache: 'no-store' })
      ]);
      if (responses.some(response => !response.ok)) throw new Error('材料版本正在准备');
      [sourcePack, explanationCoverage] = await Promise.all(responses.map(response => response.json()));
      for(const source of sourcePack.sources||[])for(const sentence of source.sentences||[]){
        const repair=readerRepairs.translations?.[sentence.id];
        if(repair?.original===sentence.original){sentence.translation=repair.row.chinese;sentence.english=repair.row.english;sentence.translation_status=repair.status;}
      }
      if (!Array.isArray(sourcePack.sources) || !Array.isArray(explanationCoverage.items)) throw new Error('材料版本正在准备');
      originalSourcePack = sourcePack;
      sourcePack = { ...sourcePack, sources: mergeSourceViews(sourcePack.sources) };
      sourceLinks = structuredClone(explanationCoverage.block_sources || {});
      if (isPreview) {
        for (const [blockId, references] of Object.entries(data.preview_source_links || {})) {
          if (!Array.isArray(references)) continue;
          const combined = [...(sourceLinks[blockId] || []), ...references];
          sourceLinks[blockId] = combined.filter((reference, index) => combined.findIndex(other =>
            other.source_id === reference.source_id &&
            JSON.stringify(other.sentence_ids || []) === JSON.stringify(reference.sentence_ids || []) &&
            JSON.stringify(other.region_ids || []) === JSON.stringify(reference.region_ids || [])) === index);
        }
      }
      // 用清单中的实际引文补充精确对照，覆盖记录与审查快照保持原样
      try {
        const [inventory,bindings]=await Promise.all([data.grounding.inventory_path,data.grounding.bindings_path].map(async path=>{
          if(!path)return null;const response=await fetch(projectPath(path),{cache:'no-store'});return response.ok?response.json():null;
        }));
        if(inventory&&bindings){
          const responsibilities=new Map(bindings.points.map(row=>[row.point_id,row.block_ids]));
          for(const point of inventory.points)for(const blockId of responsibilities.get(point.id)||[]){
            for(const quote of point.source_quotes){
              const source=originalSourcePack.sources.find(item=>item.id===quote.source_id);
              const reference=(sourceLinks[blockId]||[]).find(ref=>ref.source_id===quote.source_id);
              if(!source||!reference)continue;
              const normal=text=>text.replace(/\s+/g,' ').trim().toLocaleLowerCase();
              for(const sentence of source.sentences||[]){
                if(reference.sentence_ids?.length&&!reference.sentence_ids.includes(sentence.id))continue;
                if(quote.sentence_ids?.length&&!quote.sentence_ids.includes(sentence.id))continue;
                if(normal(sentence.original).includes(normal(quote.quote))){
                  reference.quotes||=[];
                  if(!reference.quotes.some(row=>row.sentence_id===sentence.id&&row.text===quote.quote))reference.quotes.push({sentence_id:sentence.id,text:quote.quote});
                }
              }
            }
          }
        }
      }catch(error){console.debug('当前清单的精确引文尚未载入',error);}
      document.body.classList.add('grounded-demo');
      get('demo-original').hidden = false;
      get('demo-pane-tabs').hidden = false;
      openPane('lesson');
      document.querySelectorAll('[data-open-pane]').forEach(button => {
        button.onclick = () => openPane(button.dataset.openPane);
      });
      const select = get('source-unit-select');
      for (const unit of data.units) {
        const option = make('option', numberedTitle(unit.number, unit.title));
        option.value = unit.question_id;
        select.append(option);
        const node = document.querySelector('[data-unit-question="' + unit.question_id + '"]');
        const sourceButton = make('button', '对照这一问的原材料', 'text-action unit-source-button debug-only');
        sourceButton.type = 'button';
        sourceButton.onclick = () => { chooseQuestion(unit.question_id, true); openPane('source'); };
        node.querySelector('h3').after(sourceButton);
        node.addEventListener('click', () => chooseQuestion(unit.question_id));
      }
      select.onchange = () => { restoreSources(); chooseQuestion(select.value, true); };
      renderCoverage();
      chooseQuestion(data.units[0].question_id);
      attachSourceMarkers();
      for (const unit of data.units) {
        for (const item of unit.explanation) {
          if (item.kind === 'image') {
            const surface = get('block-' + item.id)?.querySelector('.lw-media-surface');
            if (item.guide && surface) surface.replaceChildren(sourceImage(item.asset, item.alt || item.caption, imageRegion(item.source_id, item.source_region)));
            const figure = get('block-' + item.id)?.querySelector('.writing-source-figure');
            if (figure) figure.replaceWith(renderWritingImage(item));
          }
        }
      }
      const observer = new IntersectionObserver(entries => {
        const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible.length && document.body.dataset.activePane === 'lesson') chooseQuestion(visible[0].target.dataset.unitQuestion);
      }, { root: document.querySelector('.demo-explanation'), threshold: [0.1, 0.4, 0.7] });
      document.querySelectorAll('[data-unit-question]').forEach(unit => observer.observe(unit));
    } catch (error) {
      console.debug(error);
      sourcePack = null;
      explanationCoverage = null;
      document.body.classList.add('legacy-demo');
    }
  }

  // 标签引出完整解释时，解释另起一行并缩进，不依赖屏幕能否放下文字
  function labeled(label, content) {
    const box = make('div', undefined, 'writing-labeled');
    const body = make('div', undefined, 'writing-indent');
    body.append(content);
    box.append(make('span', label + '：', 'writing-label'), body);
    return box;
  }

  async function loadNoteAliases(isBook) {
    const prefix = 'infiniteqa:note:' + data.transitions_path + ':' + data.section_id + ':';
    const addAlias = (primary, alias) => {
      if (primary === alias) return;
      const aliases = noteAliases.get(primary) || [];
      if (!aliases.includes(alias)) aliases.push(alias);
      noteAliases.set(primary, aliases);
    };
    for (const unit of data.units) {
      const primary = prefix + (unit.note_block_id || unit.synthesis.id);
      addAlias(primary, prefix + unit.synthesis.id);
      for (const alias of data.preview_note_aliases || []) {
        if (alias.question_id === unit.question_id && alias.current_block_id === unit.synthesis.id && alias.previous_block_id) {
          addAlias(primary, prefix + alias.previous_block_id);
        }
      }
    }
    if (!isBook || (window.LESSONWEAVE && !window.LESSONWEAVE.legacy)) return;
    try {
      const response = await fetch('/05_writing/demo.json', { cache: 'no-store' });
      if (!response.ok) return;
      const previous = await response.json();
      if (!previous.validation?.passed || previous.section_id !== data.section_id ||
          previous.transitions_path !== data.transitions_path || previous.transition_run !== data.transition_run) return;
      for (const unit of data.units) {
        const matches = (previous.units || []).filter(old => old.question_id === unit.question_id);
        if (matches.length !== 1 || !matches[0].synthesis?.id) continue;
        const primary = prefix + (unit.note_block_id || unit.synthesis.id);
        const alias = prefix + (matches[0].note_block_id || matches[0].synthesis.id);
        addAlias(primary, alias);
      }
    } catch (error) { console.debug(error); }
  }

  function note(id, number) {
    const box = make('section', undefined, 'writing-note');
    box.dataset.noteId = id;
    box.append(make('h4', '写下这一段的理解'));
    const label = make('label');
    const input = make('textarea');
    input.rows = 3;
    input.setAttribute('aria-label', number + ' 的理解');
    label.append(input);
    const owner = data.units.find(unit => (unit.note_block_id || unit.synthesis.id) === id);
    const key = data.note_storage_prefix && owner ? data.note_storage_prefix + owner.question_id : (window.LESSONWEAVE && !window.LESSONWEAVE.legacy ? 'lessonweave:' + window.LESSONWEAVE.project_id + ':' : '') + 'infiniteqa:note:' + data.transitions_path + ':' + data.section_id + ':' + id;
    let saved = null;
    try {
      saved = localStorage.getItem(key);
      if (saved === null) {
        for (const alias of noteAliases.get(key) || []) {
          const value = localStorage.getItem(alias);
          if (value !== null) { saved = value; break; }
        }
      }
    } catch (error) { console.debug(error); }
    input.value = saved || '';
    const status = make('span', saved === null ? '' : '已保存到当前浏览器', 'help');
    const save = make('button', '保存笔记', 'small secondary');
    input.oninput = () => { status.textContent = '尚未保存'; };
    save.onclick = () => {
      try {
        localStorage.setItem(key, input.value);
        status.textContent = '已保存到当前浏览器';
      } catch (error) {
        status.textContent = '这次没有保存成功，请重试';
        console.error(error);
      }
    };
    box.append(label, save, status);
    return box;
  }

  function renderWritingImage(b) {
    const figure = make('figure', undefined, 'writing-source-figure');
    if (b.source_id) figure.dataset.sourceId = b.source_id;
    if (b.source_region) figure.dataset.sourceRegion = b.source_region;
    const region = imageRegion(b.source_id, b.source_region);
    figure.append(sourceImage(b.asset, b.caption, region));
    if (b.caption) figure.append(make('figcaption', b.caption));
    const full = make('a', '打开完整原图', 'text-action');
    full.href = projectPath(b.asset); full.target = '_blank'; full.rel = 'noopener';
    figure.append(full);
    return figure;
  }

  function mediaPlacement(resource) {
    const owner = data?.units?.find(u => u.explanation?.some(item => item.id === resource.id));
    const sequence = owner?.explanation || [resource], at = sequence.findIndex(item => item.id === resource.id);
    let start = 0, prefix = String(owner?.number || data?.section_number || '1').replace(/\.+$/, '');
    for (let i = 0; i < at; i++) if (sequence[i].kind === 'heading') {
      start = i + 1;
      const match = sequence[i].text.match(/^([1-9]\d*(?:\.[1-9]\d*)*)\./);
      if (match) prefix = match[1];
    }
    const family=kind=>window.LessonMedia?.label(kind)||kind;
    const index = sequence.slice(start, at + 1).filter(item => family(item.kind) === family(resource.kind)).length;
    return {prefix, index: Math.max(1, index)};
  }

  function readingParagraph(text, blockId) {
    const paragraph = make('p'), pattern = /\{\{media:([^}]+)\}\}/g;
    const symbols = (data.local_notations || []).filter(n => n.scope_block_ids?.includes(blockId)).map(n => n.symbol);
    const append = part => window.ReaderText ? ReaderText.rich(paragraph, part, symbols) : paragraph.append(document.createTextNode(part));
    let at = 0;
    for (const match of String(text).matchAll(pattern)) {
      append(text.slice(at, match.index));
      const resource = data?.units?.flatMap(unit => unit.explanation).find(item => item.id === match[1]);
      if (resource) {
        const place = mediaPlacement(resource), label = window.LessonMedia?.label(resource.kind) || '素材';
        const link = make('a', label + ' ' + place.prefix + '-' + place.index);
        link.href = '#block-' + resource.id;
        link.onclick = event => { event.preventDefault(); get('block-' + resource.id)?.scrollIntoView({block:'center',behavior:'smooth'}); };
        paragraph.append(link);
      } else paragraph.append(document.createTextNode(match[0]));
      at = match.index + match[0].length;
    }
    append(text.slice(at));
    return paragraph;
  }

  function block(b, role) {
    const box = make('div', undefined, 'writing-block');
    box.dataset.blockId = b.id;
    box.id = 'block-' + b.id;
    if (role) box.append(make('span', role, 'writing-role'));
    if (b.guide && window.LessonMedia) {
      const placement = mediaPlacement(b);
      box.append(window.LessonMedia.render(b, {
        prefix: placement.prefix, index: placement.index, path: projectPath,
        image: item => sourceImage(item.asset, item.alt || item.caption, imageRegion(item.source_id, item.source_region))
      }));
      return box;
    }
    if (b.kind === 'heading') { box.append(make('h4', internalTitle(b.text), 'writing-detail-title')); return box; }
    if (b.kind === 'paragraph') {
      const parts = window.ReaderText ? ReaderText.paragraphs(b.text) : [b.text];
      parts.forEach(text => box.append(readingParagraph(text, b.id)));
    } else if (b.kind === 'table') {
      const scroll = make('div', undefined, 'table-scroll');
      const table = make('table');
      const head = make('tr');
      b.headers.forEach(h => head.append(make('th', h)));
      table.append(head);
      for (const row of b.rows) {
        const tr = make('tr');
        row.forEach(cell => tr.append(make('td', cell)));
        table.append(tr);
      }
      scroll.append(table);
      box.append(scroll);
    } else if (b.kind === 'list') {
      const list = make('ul');
      b.items.forEach(item => list.append(make('li', item)));
      box.append(list);
    } else if (b.kind === 'image') {
      box.append(renderWritingImage(b));
    } else {
      box.append(make('pre', b.text), make('p', b.caption || ''));
    }
    if (b.lead_in) {
      const content = make('div');
      while (box.lastChild && !box.lastChild.classList?.contains('writing-role')) content.prepend(box.lastChild);
      box.append(labeled(b.lead_in, content));
    }
    return box;
  }

  function quiz(q, index) {
    const card = make('section', undefined, 'quiz-card');
    card.dataset.quizId = q.id;
    card.append(make('h3', `${index + 1} · ${q.kind === 'single_choice' ? '单选' : '简答'}`), block(q.prompt));
    let selected = null;
    if (q.kind === 'single_choice') {
      const list = make('div', undefined, 'quiz-options');
      q.options.forEach((option, i) => {
        const label = make('label');
        const radio = make('input');
        radio.type = 'radio';
        radio.name = q.id;
        radio.value = i;
        radio.onchange = () => { selected = i; answer.hidden = true; list.querySelectorAll('label').forEach(el => {el.classList.remove('is-correct','is-wrong');el.querySelector('.quiz-verdict').textContent='';}); };
        label.append(radio, make('span', String.fromCharCode(65 + i) + ' · ' + option, 'quiz-option-text'), make('span','','quiz-verdict'));
        list.append(label);
      });
      card.append(list);
    } else {
      const input = make('textarea');
      input.rows = 4;
      input.setAttribute('aria-label', '简答 ' + q.id);
      input.placeholder = '先用自己的话解释，再查看参考答案';
      card.append(input);
    }
    const check = make('button', q.kind === 'single_choice' ? '核对答案' : '查看参考答案', 'small secondary');
    const answer = make('div', undefined, 'quiz-answer');
    answer.hidden = true;
    check.onclick = () => {
      answer.replaceChildren();
      if (q.kind === 'single_choice') {
        if (selected === null) {
          answer.append(make('p', '先选一项，再核对自己的判断'));
          answer.hidden = false;
          return;
        }
        card.querySelectorAll('.quiz-options label').forEach((label,i) => {
          label.classList.toggle('is-correct',i===q.answer); label.classList.toggle('is-wrong',i===selected&&i!==q.answer);
          label.querySelector('.quiz-verdict').textContent = i===q.answer?'✅ 正确':i===selected?'❌ 错误':'';
        });
        answer.setAttribute('role','status');
        answer.append(make('p', selected === q.answer ? '✅ 回答正确' : '❌ 本次选择有误，正确选项是 ' + String.fromCharCode(65 + q.answer)));
      } else {
        answer.append(labeled('参考答案', make('p', q.reference_answer)));
        const list = make('ul');
        q.rubric.forEach(point => list.append(make('li', point)));
        answer.append(labeled('回答时应说明', list));
      }
      answer.append(labeled('为什么这样回答', block(q.explanation)));
      answer.hidden = false;
    };
    card.append(check, answer);
    return card;
  }

  function renderGlossary() {
    const list = get('glossary-list');
    list.replaceChildren();
    for (const term of data.glossary) {
      const card = make('details', undefined, 'glossary-entry');
      card.dataset.termId = term.id;
      card.id = 'term-' + term.id;
      card.append(make('summary', term.display));
      const prose = make('div', undefined, 'glossary-prose');
      prose.append(readingParagraph(term.definition));
      term.explanation.forEach(text => prose.append(readingParagraph(text)));
      card.append(prose);
      list.append(card);
    }
    filterGlossary();
  }

  function filterGlossary() {
    restoreGlossary();
    const query = get('glossary-search').value.trim().toLowerCase();
    for (const card of get('glossary-list').children) {
      const term = data.glossary.find(item => item.id === card.dataset.termId);
      card.hidden = !!query && !JSON.stringify(term).toLowerCase().includes(query);
    }
  }

  function restoreGlossary() {
    clearTimeout(glossaryTimer);
    clearTimeout(glossaryRestoreTimer);
    if (!glossaryPreview) return;
    const snapshot = glossaryPreview;
    glossaryPreview = null;
    for (const { card, open, hidden } of snapshot.cards) { card.open = open; card.hidden = hidden; }
    get('glossary-search').value = snapshot.query;
    if (get('glossary-preview-controls')) get('glossary-preview-controls').hidden = true;
    get('glossary-count').textContent = snapshot.count;
    document.querySelectorAll('.inline-term.is-term-active').forEach(span => span.classList.remove('is-term-active'));
    restoreScroll(get('glossary-result'), snapshot.scroll);
  }

  function previewGlossary(termId, pinned = false, fromFocus = false) {
    clearTimeout(glossaryTimer);
    clearTimeout(glossaryRestoreTimer);
    const list = get('glossary-list');
    const selected = [...list.children].find(card => card.dataset.termId === termId);
    if (!selected) return;
    if (!glossaryPreview) glossaryPreview = {
      cards: [...list.children].map(card => ({ card, open: card.open, hidden: card.hidden })),
      query: get('glossary-search').value,
      count: get('glossary-count').textContent,
      scroll: get('glossary-result').scrollTop,
      pinned: false
    };
    glossaryPreview.termId = termId;
    glossaryPreview.focusActive = fromFocus;
    glossaryPreview.pinned = pinned || glossaryPreview.pinned;
    for (const card of list.children) { card.hidden = card !== selected; if (card === selected) card.open = true; }
    get('glossary-count').textContent = '正在查看正文中的术语';
    if (get('glossary-preview-controls')) {
      get('glossary-preview-controls').hidden = false;
      get('glossary-preview-caption').textContent = selected.querySelector('summary').textContent;
    }
    document.querySelectorAll('.inline-term').forEach(span => span.classList.toggle('is-term-active', span.dataset.termId === termId));
    restoreScroll(get('glossary-result'), 0);
    if (pinned) openPane('glossary');
  }

  function deferRestoreGlossary() {
    clearTimeout(glossaryRestoreTimer);
    glossaryRestoreTimer = setTimeout(() => {
      const focused = document.activeElement;
      const keyboardFocus = glossaryPreview?.focusActive && focused?.matches(':focus-visible') && (get('glossary-result').contains(focused) || focused.classList.contains('inline-term'));
      if (glossaryPreview && !glossaryPreview.pinned && !get('glossary-result').matches(':hover') && !keyboardFocus) restoreGlossary();
    }, 180);
  }

  function markInlineTerms() {
    const localSymbols = new Map();
    for (const notation of data.local_notations || []) {
      for (const blockId of notation.scope_block_ids || []) {
        if (!localSymbols.has(blockId)) localSymbols.set(blockId, new Set());
        localSymbols.get(blockId).add(notation.symbol);
      }
    }
    const localPatterns = new Map([...localSymbols].map(([blockId, symbols]) => [blockId,
      new RegExp('(?<![A-Za-z0-9])(?:' + [...symbols].sort((a, b) => b.length - a.length)
        .map(symbol => symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')(?![A-Za-z0-9])', 'gu')]));
    const aliases = new Map();
    const ambiguous = new Set();
    for (const term of data.glossary) {
      for (const alias of new Set([term.chinese, term.english, term.abbreviation, ...(term.aliases || [])].filter(Boolean))) {
        const key = alias.toLocaleLowerCase();
        if (aliases.has(key) && aliases.get(key).id !== term.id) ambiguous.add(key);
        else aliases.set(key, { id: term.id, alias });
      }
    }
    const sorted = [...aliases.values()].filter(item => !ambiguous.has(item.alias.toLocaleLowerCase())).sort((a, b) => b.alias.length - a.alias.length);
    if (!sorted.length) return;
    const pattern = new RegExp(sorted.map(item => item.alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'giu');
    const walker = document.createTreeWalker(get('demo-content'), NodeFilter.SHOW_TEXT, {
      acceptNode: node => node.parentElement.closest('a,button,pre,code,svg,math,input,textarea,.writing-role,.writing-note,.inline-term,.reader-math,.katex,.lw-media-mermaid,.lw-media-math') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const text = node.nodeValue;
      const blockId = node.parentElement.closest('[data-block-id]')?.dataset.blockId;
      const localPattern = localPatterns.get(blockId);
      // 局部符号只在登记的正文块和精确跨度内保持原样，同名专业术语在其他位置继续联动
      const localSpans = localPattern ? [...text.matchAll(localPattern)].map(match => [match.index, match.index + match[0].length]) : [];
      const fragment = document.createDocumentFragment();
      let end = 0;
      pattern.lastIndex = 0;
      for (const match of text.matchAll(pattern)) {
        const value = match[0];
        const start = match.index;
        const after = start + value.length;
        if (/^[A-Za-z0-9_]/.test(value) && /[A-Za-z0-9_]/.test(text[start - 1] || '')) continue;
        if (/[A-Za-z0-9_]$/.test(value) && /[A-Za-z0-9_]/.test(text[after] || '')) continue;
        if (localSpans.some(([left, right]) => start < right && after > left)) continue;
        const term = aliases.get(value.toLocaleLowerCase());
        if (!term) continue;
        fragment.append(document.createTextNode(text.slice(end, start)));
        const span = make('span', value, 'inline-term');
        span.dataset.termId = term.id;
        span.tabIndex = 0;
        span.setAttribute('role', 'button');
        span.setAttribute('aria-label', '查看术语：' + value);
        span.setAttribute('aria-controls', 'glossary-list');
        span.addEventListener('pointerenter', () => {
          clearTimeout(glossaryRestoreTimer);
          clearTimeout(glossaryTimer);
          glossaryTimer = setTimeout(() => previewGlossary(term.id), 90);
        });
        span.addEventListener('pointerleave', () => { clearTimeout(glossaryTimer); deferRestoreGlossary(); });
        span.addEventListener('focus', () => previewGlossary(term.id, false, true));
        span.addEventListener('blur', deferRestoreGlossary);
        span.addEventListener('click', event => { event.stopPropagation(); previewGlossary(term.id, true); });
        span.addEventListener('keydown', event => {
          if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); previewGlossary(term.id, true); }
          if (event.key === 'Escape') { restoreGlossary(); span.blur(); }
        });
        fragment.append(span);
        end = after;
      }
      if (end) { fragment.append(document.createTextNode(text.slice(end))); node.replaceWith(fragment); }
    }
    const pane = get('glossary-result');
    pane.addEventListener('pointerenter', () => clearTimeout(glossaryRestoreTimer));
    pane.addEventListener('pointerleave', deferRestoreGlossary);
    pane.addEventListener('focusin', () => { if (glossaryPreview) glossaryPreview.focusActive = true; });
    pane.addEventListener('focusout', deferRestoreGlossary);
    if (get('glossary-preview-back')) get('glossary-preview-back').onclick = restoreGlossary;
  }

  async function load() {
    try {
      if (get('show-debug')) {
        get('show-debug').checked = false;
        get('show-debug').onchange = event => showDebug(event.target.checked);
        showDebug(false);
      }
      if (get('source-language-select')) {
        let savedLanguage = 'both';
        try { savedLanguage = localStorage.getItem('infiniteqa:source-language') || 'both'; } catch (error) { console.debug(error); }
        setSourceLanguage(savedLanguage);
        get('source-language-select').onchange = event => setSourceLanguage(event.target.value);
      }
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') { restoreSources(); restoreGlossary(); }
      });
      let sectionPath = '/05_writing/demo.json';
      let book = null;
      let navigationSuffix = '';
      if (location.pathname.endsWith('book.html') || window.LESSONWEAVE?.book) {
        const parameters = new URLSearchParams(location.search);
        const published = parameters.get('published') === '1' || parameters.get('preview') === 'false';
        let bookResponse = await fetch(published ? '/05_writing/book.json' : '/05_writing/preview-book.json', { cache: 'no-store' });
        if (!published && bookResponse.status === 404) bookResponse = await fetch('/05_writing/book.json', { cache: 'no-store' });
        if (!bookResponse.ok) throw new Error('正文正在生成');
        book = await bookResponse.json();
        isPreview = book.preview === true;
        if (!book.validation?.passed && !isPreview) throw new Error('正文正在检查');
        navigationSuffix = isPreview ? '&preview=true' : '&published=1';
        const sections = book.chapters.flatMap(c => c.sections);
        const chosen = new URLSearchParams(location.search).get('section') || sections[0].id;
        const entry = sections.find(s => s.id === chosen);
        if (!entry) throw new Error('找不到这个小节');
        sectionPath = '/' + entry.path;
        const toc = get('book-toc');
        for (const chapter of book.chapters) {
          const group = make('details');
          group.open = chapter.sections.some(s => s.id === chosen);
          group.append(make('summary', numberedTitle(chapter.number, chapter.title)));
          const list = make('ul');
          for (const section of chapter.sections) {
            const item = make('li');
            const link = make('a', numberedTitle(section.number, section.title));
            link.href = projectPath('book.html?section=' + section.id + navigationSuffix);
            if (section.id === chosen) link.setAttribute('aria-current', 'page');
            item.append(link); list.append(item);
          }
          group.append(list); toc.append(group);
        }
        get('book-title').textContent = book.title;
        if (get('book-grounding-report') && book.grounding_report_path) {
          get('book-grounding-report').href = projectPath(book.grounding_report_path);
          get('book-grounding-report').hidden = false;
        }
        const index = sections.findIndex(s => s.id === chosen);
        const nav = get('book-navigation');
        for (const [label, target] of [['上一节', sections[index - 1]], ['下一节', sections[index + 1]]]) {
          if (target) { const link = make('a', label + ' ' + target.number); link.href = projectPath('book.html?section=' + target.id + navigationSuffix); nav.append(link); }
        }
      }
      const response = await fetch(sectionPath, { cache: 'no-store' });
      if (response.status === 404) {
        get('demo-status').textContent = '本案例尚未生成写作样稿';
        return;
      }
      data = await response.json();
      // 仅恢复原始回执中可逐字核对的换行，原始数据、块编号和来源映射保持原样
      try {
        const restored = await fetch('/05_writing/reader-whitespace.json');
        if (restored.ok) {
          const overlay=await restored.json();const replacements = overlay.replacements || {};
          if(overlay.reader_repairs_path){const fixed=await fetch(projectPath(overlay.reader_repairs_path));if(fixed.ok)readerRepairs=await fixed.json();}
          const visit = value => {if(Array.isArray(value))value.forEach(visit);else if(value&&typeof value==='object'){
            if(['code','formula','mermaid'].includes(value.kind))return;
            for(const [key,child] of Object.entries(value)){
              if(['grounding','coverage','bindings','source_quotes','source_links','preview_provenance'].includes(key))continue;
              if(typeof child==='string'&&replacements[child])value[key]=replacements[child];else if(child&&typeof child==='object')visit(child);
            }
          }};visit(data);
          for(const unit of data.units||[])for(let i=0;i<(unit.explanation||[]).length;i++){
            const block=unit.explanation[i],repair=readerRepairs.attachments?.[block.id];
            if(block.kind==='file'&&repair?.status==='resolved'){
              unit.explanation[i]={...repair.projection,attachment_asset:repair.asset,attachment_role:repair.role};
            }
          }
        }
      } catch (error) {console.debug(error);}
      documentPath = sectionPath;
      isPreview = isPreview || data.preview === true;
      if (!data.validation?.passed && !isPreview) throw new Error('样稿尚未通过检查');
      document.body.classList.toggle('draft-preview', isPreview);
      const previewStatus = get('delivery-status');
      if (previewStatus) {
        previewStatus.hidden = !isPreview;
        previewStatus.textContent = '完整稿预览 · ' + (data.validation?.passed ? (data.validation_scope === 'format_and_references' ? '本节格式与引用检查通过' : '本节检查通过') : data.validation?.passed === false ? '本节检查未通过' : '审查待完成');
      }
      await loadNoteAliases(!!book);
      if (book) {
        // 书与章的整体回答保留在检查区，正常正文从承上启下开始
        if (data.book_introduction) get('book-overview').append(make('p', data.book_introduction));
        for (const goal of data.context_goals || []) {
          const box = make('details');
          box.append(make('summary', goal.text), make('p', goal.answer));
          get('book-overview').append(box);
        }
      }
      get('demo-title').textContent = numberedTitle(data.section_number, data.title);
      get('demo-status').textContent = `${isPreview ? '完整稿预览' : book ? '05 完整正文' : '05 最小样稿'} · ${data.core_questions.length} 个核心问题 · ${data.quiz.length} 道练习 · ${data.glossary.length} 个术语`;
      const article = get('demo-content');
      article.replaceChildren();
      const opening = make('section', undefined, 'writing-opening');
      const openingHeading = make('h2', undefined, 'writing-opening-title');
      openingHeading.textContent = '承上启下';
      opening.append(openingHeading);
      if (data.opening_title) opening.append(make('p', data.opening_title, 'writing-opening-question'));
      opening.append(block(data.opening, '承上段'));
      if (data.opening_forward) opening.append(block(data.opening_forward, '启下段'));
      article.append(opening);
      const cores = make('ul', undefined, 'writing-core-questions');
      cores.setAttribute('aria-label', '本节核心问题');
      data.core_questions.forEach(q => cores.append(make('li', q.text)));
      const coreHeading = make('h2', '核心问题');
      coreHeading.id = 'writing-core-questions';
      article.append(coreHeading, cores, make('h2', '内容讲解'));
      data.units.forEach(u => {
        const unit = make('section', undefined, 'writing-unit');
        unit.dataset.unitQuestion = u.question_id;
        unit.append(make('h3', numberedTitle(u.number, u.title), 'writing-unit-title'));
        if (u.problem_heading) unit.append(make('h4', internalTitle(u.problem_heading), 'writing-detail-title'));
        unit.append(block(u.problem, '问题段'));
        u.explanation.forEach(b => unit.append(block(b, '讲解段')));
        if (u.summary_heading) unit.append(make('h4', internalTitle(u.summary_heading), 'writing-detail-title'));
        unit.append(block(u.synthesis, '升华段'), note(u.note_block_id || u.synthesis.id, u.number));
        article.append(unit);
      });
      const summaryHeading = make('h2', '内容总结');
      summaryHeading.id = 'writing-summary';
      article.append(summaryHeading);
      for (const row of data.summary) {
        const q = data.core_questions.find(q => q.question_id === row.question_id);
        const part = make('section', undefined, 'summary-answer');
        part.dataset.summaryQuestion = row.question_id;
        part.append(make('h3', q.text, 'summary-question'), block(row.answer));
        article.append(part);
      }
      const pitfallsHeading = make('h2', '易错点');
      pitfallsHeading.id = 'writing-pitfalls';
      article.append(pitfallsHeading);
      for (const p of data.pitfalls) {
        const part = make('section', undefined, 'writing-pitfall');
        part.append(make('h3', p.premise.replace(/[，,；;？?\s]+$/, '') + '，' + p.question), block(p.body));
        article.append(part);
      }
      const quizHeading = make('h2', '问答');
      quizHeading.id = 'writing-quiz';
      article.append(quizHeading);
      data.quiz.forEach((q, i) => article.append(quiz(q, i)));
      renderLocalNotations(article);
      if (isPreview) {
        const diagnostics = make('details', undefined, 'debug-only');
        diagnostics.id = 'preview-diagnostics';
        diagnostics.append(make('summary', '当前稿采用了哪些内容和检查结果'), make('pre', JSON.stringify({
          preview_status: data.preview_status, preview_provenance: data.preview_provenance,
          validation: data.validation, preview_source_links: data.preview_source_links
        }, null, 2)));
        article.append(diagnostics);
      }
      get('glossary-result').hidden = false;
      get('glossary-count').textContent = `${data.glossary.length} 个术语，展开名称可查看解释`;
      renderGlossary();
      get('glossary-search').oninput = () => {
        const query = get('glossary-search').value;
        restoreGlossary();
        get('glossary-search').value = query;
        filterGlossary();
      };
      if (get('glossary-preview-controls')) markInlineTerms();
      if (data.coverage?.report) get('term-report').href = projectPath(data.coverage.report);
      else get('term-report').hidden = true;
      if (book) get('demo-json').href = sectionPath;
      get('writing-plan').href = `/?transition=${data.section_id}#transitions`;
      get('show-roles').onchange = () => document.body.classList.toggle('show-writing-roles', get('show-roles').checked);
      const next = make('a', data.next_title);
      next.href = book ? projectPath(`book.html?section=${data.next_section_id}${navigationSuffix}`) : `/?chapter=${data.next_section_id}#chapters`;
      if (data.next_section_id) get('next-section').replaceChildren(next);
      await loadGrounding();
      readerReady = true;
      document.dispatchEvent(new CustomEvent('reading:document-ready', { detail: readingState() }));
    } catch (error) {
      console.error(error);
      get('demo-status').textContent = '样稿正在准备';
      if (get('ui-status')) get('ui-status').textContent = '正文正在准备';
    }
  }
  load();
})();
