const STYLES=".lw-reader-root{font-family:\"Segoe UI\",\"Microsoft YaHei\",sans-serif;color:#263c34;background:#f2f4ef;line-height:1.65;--green:#285b45;--line:#d8e0d7;--muted:#66776c}*{box-sizing:border-box}.lw-reader-root{margin:0}main{max-width:1720px;margin:auto;padding:30px 32px 60px}header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}h1{font-size:29px;margin:5px 0}h2{font-size:20px;margin:0 0 8px;overflow-wrap:anywhere}h3{font-size:14px;margin:0 0 12px}p{margin:8px 0}a{color:var(--green);text-underline-offset:3px}nav{display:flex;gap:8px;flex-shrink:0}nav a{padding:8px 16px;border:1px solid var(--line);border-radius:20px;text-decoration:none;background:white}nav a.current{background:var(--green);color:white}.eyebrow{font-size:11px;letter-spacing:.1em;color:var(--muted);margin:0}.muted,.help{color:var(--muted)}.help{font-size:12px}.path{font:12px/1.7 Consolas,\"Microsoft YaHei\",monospace;overflow-wrap:anywhere}.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:22px;margin:16px 0}details>summary{cursor:pointer;font-weight:600}details[open]>summary{margin-bottom:14px}.compact,.reader-heading{display:flex;gap:20px;align-items:center;justify-content:space-between}.compact h2{font-size:15px}.compact p{margin:0}.compact button{flex-shrink:0}.input-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.field{margin:12px 0}label{display:block;font-weight:600;margin:8px 0}input,select,textarea,button{font:inherit;color:inherit}input,select,textarea{width:100%;padding:9px 11px;border:1px solid #bfcfc2;border-radius:6px;background:white}textarea{min-height:240px;font-size:13px;line-height:1.8;resize:vertical}button{border:0;border-radius:6px;background:var(--green);color:white;padding:10px 16px;cursor:pointer;font-weight:600}button.secondary{background:#edf2e9;color:var(--green)}button.small{padding:6px 9px;font-size:12px}button:disabled{opacity:.5;cursor:wait}.actions{display:flex;gap:14px;align-items:center;margin-top:18px}.status{font-size:12px;background:#eaf2e6;color:#315a36;padding:6px 12px;border-radius:20px;white-space:nowrap}.status.review{background:#fff2d4;color:#855a16}.status.error,#error,#parse-error{color:#993e30;background:#fceee8}pre{font:12px/1.65 Consolas,\"Microsoft YaHei\",monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f1;padding:14px;border-radius:6px;overflow:auto;max-height:440px}.downloads{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:12px;margin:14px 0 22px}.reader-grid{display:grid;grid-template-columns:minmax(240px,.8fr) minmax(280px,1.1fr) minmax(320px,1.4fr);gap:20px;border-top:1px solid var(--line);padding-top:20px;align-items:start}.tree-pane,.node-pane,.source-pane{min-width:0}.tree-pane{border-right:1px solid var(--line);padding-right:15px}.tree-tools{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}#tree{max-height:690px;overflow:auto;padding:2px 0 14px}.tree-row{display:flex;align-items:stretch;gap:0;min-height:35px;border-radius:5px;margin:2px 0}.tree-row.selected{background:#e5eee2;box-shadow:inset 3px 0 #3e714c}.tree-row:hover{background:#f0f4ed}.tree-row button{background:none;color:inherit;border:0;border-radius:0;padding:7px 3px;font-weight:400;text-align:left;line-height:1.5;font-size:12px}.tree-row button.expander{width:22px;flex-shrink:0;text-align:center;color:#6c7e6d}.tree-row button.node-link{min-width:0;flex:1;display:flex;gap:7px}.tree-type{color:#6e806f;font-size:10px;flex-shrink:0;min-width:21px;padding-top:1px}.tree-name{overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.tree-row small{color:#829080;font-size:10px;white-space:nowrap;padding:9px 2px}.tree-row.unknown .tree-type{color:#9b5e13}.search-result{border-bottom:1px solid #edf0e9;padding-bottom:6px}.search-path{font-size:10px;color:var(--muted);overflow-wrap:anywhere;padding-left:25px}.breadcrumbs{font-size:11px;color:var(--muted);margin-bottom:12px;overflow-wrap:anywhere}.breadcrumbs button{background:none;color:var(--muted);padding:0 2px;font:inherit;text-decoration:underline}.node-title{display:flex;gap:10px;align-items:center;margin-bottom:14px}.type-badge{font:11px Consolas,monospace;background:#edf2e9;padding:4px 8px;border-radius:4px}.node-id{font:11px Consolas,monospace;color:var(--muted)}.node-text{font-size:15px;line-height:1.85;white-space:pre-wrap;overflow-wrap:anywhere}.node-pane{max-height:820px;overflow:auto;padding-right:5px}.node-pane img{display:block;width:auto;max-width:100%;height:auto;margin:12px auto;border:1px solid #e6e9e1}.node-pane figure{margin:10px 0}.node-pane figcaption{font-size:13px;line-height:1.8;white-space:pre-wrap}.node-pane details{margin:12px 0;font-size:12px}.node-pane details pre{font-size:11px}.child-link{display:block;width:100%;text-align:left;background:#f2f5ef;color:#365541;margin:6px 0;padding:9px;font-size:12px;overflow-wrap:anywhere}.issue{border-left:3px solid #b97e29;background:#fff7e6;padding:12px;font-size:13px;overflow-wrap:anywhere}.table-scroll{overflow:auto;margin:12px 0}table{border-collapse:collapse;font-size:11px;line-height:1.6;width:100%;min-width:300px}td,th{border:1px solid var(--line);padding:7px;vertical-align:top;white-space:pre-wrap}td[data-source]{cursor:pointer}td[data-source]:hover{background:#fff0c9}.source-heading{display:flex;justify-content:space-between;gap:15px;align-items:center}.source-heading select{width:auto;font-size:12px;padding:5px}.source-heading h3{margin-bottom:0}#source-location{min-height:20px}#source-link{font-size:12px}#source-view{max-height:670px;overflow:auto;border:1px solid var(--line);background:#f7f8f4;margin-top:12px;scroll-behavior:smooth}#source-image-wrap{position:relative}#source-image{display:block;width:100%;height:auto}#source-highlights{position:absolute;inset:0;pointer-events:none}.source-highlight{position:absolute;border:2px solid #b38519;background:#f3c3392b}#source-code{margin:0;border-radius:0;max-height:none;font-size:11px;white-space:pre;overflow:visible;min-width:max-content;background:#f6f8f3}.code-line{display:block;padding:0 8px}.code-line.marked{background:#f4e7b1}.line-number{display:inline-block;width:44px;color:#86907f;user-select:none}#source-empty{padding:18px;font-size:13px}#source-choices{font-size:11px;margin-top:12px}#source-choices button{background:#f1f4ed;color:#456246;font-size:11px;padding:5px 8px;margin:3px 4px 3px 0}.process{border-top:1px solid var(--line);margin-top:24px;padding-top:16px;font-size:13px}.process ul{padding-left:20px}.notes{font-size:13px}.notes h2{font-size:16px;margin-top:20px}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,textarea:focus-visible{outline:3px solid #b99b46;outline-offset:2px}[hidden]{display:none!important}@media(min-width:1600px){.reader-grid{grid-template-columns:320px minmax(350px,1fr) minmax(440px,1.2fr)}}@media(max-width:1100px){main{padding:22px 18px}.reader-grid{grid-template-columns:240px minmax(0,1fr)}.source-pane{grid-column:2}.node-pane{max-height:600px}.tree-pane{grid-row:1/3}#tree{max-height:1050px}}@media(max-width:700px){main{padding:18px 12px}header{display:block}h1{font-size:24px}nav{margin-top:18px}nav a{font-size:12px}.panel{padding:16px}.compact,.reader-heading{align-items:flex-start;flex-direction:column;gap:10px}.input-grid,.reader-grid{grid-template-columns:minmax(0,1fr)}.tree-pane{grid-row:auto;border-right:0;border-bottom:1px solid var(--line);padding:0 0 16px}.source-pane{grid-column:auto}#tree{max-height:320px}.node-pane{max-height:650px}.downloads{gap:8px 16px}.status{white-space:normal}#source-view{max-height:560px}}\n\n.question-panel{scroll-margin-top:16px}.question-goal{padding:12px 15px;background:#eef4e9;border-left:3px solid #557d4b}.question-branches{list-style:none;margin:12px 0 0;padding-left:22px;border-left:1px solid #cbdac6}.question-panel>#question-result>#question-tree{padding-left:0;border-left:0}.question-item{margin:8px 0;padding:9px 12px;border:1px solid #dfe6da;border-radius:7px;background:#fcfdfb}.question-item>details>summary{display:list-item;font-size:14px;line-height:1.8;overflow-wrap:anywhere}.question-item>details[open]>summary{margin-bottom:8px}.question-id{display:inline-block;font:11px Consolas,monospace;color:#637a62;margin-right:9px}.question-intent{font-size:13px;color:#425f46}.question-before,.question-sources{font-size:12px;color:#66776c}.question-sources{display:flex;gap:10px;flex-wrap:wrap}.question-dependency{display:inline;background:none;color:#285b45;padding:0 5px;font-size:12px;text-decoration:underline;text-align:left}.question-order{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:16px}.question-order-link{font:12px Consolas,monospace;padding:6px 10px;background:#edf3e8;color:#285b45}.question-selected{box-shadow:inset 3px 0 #3e714c;background:#f0f5e9}.question-entry{font-weight:700}@media(max-width:700px){.question-branches{padding-left:10px}.question-item{padding:8px}.question-item>details>summary{font-size:13px}}\n\n.question-statement{display:inline-block;vertical-align:top;max-width:calc(100% - 85px)}.question-premise{display:block;color:#344b3b;font-size:14px;line-height:1.8;font-weight:400;margin-bottom:0}.question-text{display:block;color:#344b3b;font-size:14px;line-height:1.8;font-weight:600}.question-id{min-width:56px}.question-controls{display:flex;gap:8px;align-items:end;flex-wrap:wrap;margin:16px 0}.question-controls label{flex:1;min-width:190px}.question-controls select{max-width:100%;font-size:13px}.question-metrics{display:flex;gap:8px 24px;flex-wrap:wrap;border-block:1px solid #dfe6da;padding:10px 0}.question-metrics p{margin:0;font-size:13px;color:#315a36}.question-sources{display:block;margin:10px 0}.question-source-list{display:grid;gap:7px;margin:10px 0}.question-source-list a{overflow-wrap:anywhere}.question-mapping-row{border-bottom:1px solid #dfe6da;padding:8px 0}.question-mapping-row p{font-size:12px;overflow-wrap:anywhere}.question-mapping-row button{display:block;margin:6px 0}#question-mapping{margin:12px 0}#question-mapping>summary{font-size:14px}#question-mapping input{margin-top:10px}.question-item>details>summary{list-style-position:outside;margin-left:14px}.question-body{margin-left:4px}@media(max-width:700px){.question-statement{max-width:100%}.question-id{display:block}.question-controls{align-items:stretch}.question-controls label{flex-basis:100%}}\n\n/* 标题保持一行，较窄的窗口可以在标题内横向滚动查看全文 */\n.question-statement{white-space:nowrap;overflow-x:auto}.question-premise,.question-text{display:inline;font-size:14px;line-height:1.8}.question-text{font-weight:600}.chapter-panel{scroll-margin-top:16px}.chapter-branches{list-style:none;margin:10px 0;padding-left:20px;border-left:1px solid #dce5d7}#chapter-tree{padding-left:0;border-left:0}.chapter-item{margin:7px 0}.chapter-item>details>summary{display:flex;align-items:center;gap:9px;padding:10px 8px;border-radius:5px;background:#f4f7f0;cursor:pointer;min-width:0}.chapter-item>details>summary:before{content:'▸';font-size:11px;color:#60745c;flex-shrink:0}.chapter-item>details[open]>summary:before{content:'▾'}.chapter-number{font-size:12px;color:#617a59;flex-shrink:0;min-width:46px}.chapter-title-text{font-size:14px;line-height:1.8;white-space:nowrap;overflow-x:auto;display:block;min-width:0;flex:1}.chapter-selected>details>summary{background:#e9f1e3;box-shadow:inset 3px 0 #53754a}.chapter-assignments{font-size:12px;margin:8px 8px 10px 28px}.chapter-assignments>summary{color:#6d7a65;cursor:pointer}.chapter-question{border-bottom:1px solid #e5eadd;margin:10px 0;padding:8px 0;overflow-wrap:anywhere}.chapter-question a{font-size:12px}.chapter-question details{font-size:11px;margin:8px 0}.chapter-before{font-size:12px}.chapter-before button{display:block;margin:6px 0}#chapter-question-mapping{margin-top:16px}#chapter-question-mapping input{margin-top:12px}@media(max-width:700px){.chapter-branches{padding-left:9px}.chapter-number{min-width:36px;font-size:11px}.chapter-title-text{font-size:13px}.chapter-item>details>summary{gap:5px;padding:8px 4px}.chapter-assignments{margin-left:12px}}\n\n\n.writing-page main{max-width:980px;padding:30px 28px}.writing-page h1{font-size:25px;line-height:1.65}.writing-page h2{margin:34px 0 18px;font-size:21px}.writing-page h3{line-height:1.8;font-size:17px}.writing-page p,.writing-page li{font-size:16px;line-height:1.95}.writing-block{margin:18px 0}.writing-block p{margin:0 0 7px}.writing-role{display:none;color:#8e7139;font-size:11px}.show-writing-roles .writing-role{display:block}.role-toggle{font-size:12px;display:flex;gap:8px;align-items:center}.role-toggle input{width:auto}.writing-note{border:1px solid #e1e7db;border-radius:5px;padding:7px 10px;margin:8px 0 20px;background:#f8faf5;font-size:12px}.writing-note summary{cursor:pointer;color:#74806e;font-size:12px}.writing-note label{font-size:12px;margin-top:10px}.writing-note textarea{font-size:14px;min-height:88px}.writing-note button{margin:8px 10px 0 0}.writing-core-questions{padding:16px 20px 16px 38px;background:#f0f5e9;border-left:3px solid #597750;border-radius:4px}.writing-core-questions li{font-size:14px;line-height:1.85;margin:10px 0}.writing-unit{padding:6px 0 15px;border-bottom:1px solid #e3e8dc}.summary-question{font-size:14px!important;font-weight:600;color:#315239}.writing-pitfall{padding:12px 16px;border-left:3px solid #b58f45;background:#fffaf0;margin:14px 0}.writing-pitfall h3{margin:0}.quiz-card{border:1px solid #dce5d6;border-radius:6px;padding:16px;margin:18px 0}.quiz-options{display:grid;gap:8px;margin:12px 0}.quiz-options label{display:flex;gap:10px;align-items:flex-start;font-weight:400;padding:9px;background:#f5f8f1;font-size:14px;line-height:1.8}.quiz-options input{width:auto;margin-top:6px}.quiz-card textarea{font-size:15px}.quiz-answer{margin-top:14px;background:#f0f5e9;padding:12px}.glossary-entry{border-bottom:1px solid #dce5d6;padding:12px 0}.glossary-entry summary{font-size:15px;line-height:1.8;cursor:pointer}.glossary-entry p{font-size:14px;margin:9px 0}.writing-page .table-scroll td,.writing-page .table-scroll th{font-size:13px}.writing-page #next-section{margin:35px 0;font-size:14px}@media(max-width:700px){.writing-page main{padding:20px 15px}.writing-page h1{font-size:21px}.writing-page p,.writing-page li{font-size:15px}.quiz-card{padding:12px}}\n\n.writing-label{display:block;font-weight:600}\n.writing-indent{display:block;margin:7px 0 14px 1.5em}\n.writing-indent>.writing-block:first-child,.writing-indent>div>.writing-block:first-child{margin-top:0}\n.writing-indent>p:first-child,.writing-indent>ul:first-child{margin-top:0}\n.writing-opening-title .writing-label{font-size:15px;color:#597750}\n.writing-opening-title .writing-indent{font-size:19px;line-height:1.85;margin-top:9px}\n.writing-unit-title{color:#315239;margin:23px 0 18px}\n.summary-answer{padding:5px 0 18px;border-bottom:1px solid #e3e8dc}\n.summary-answer .writing-label{font-size:13px;color:#597750}\n.glossary-prose{margin:12px 0 16px}\n.glossary-entry[open]>summary{color:#315239;font-weight:600}\n.glossary-prose p{line-height:2;margin:12px 0}\n.glossary-entry .writing-label{font-size:13px;color:#597750}\n.glossary-components{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px 24px;padding-left:20px}\n.glossary-components li{font-size:14px}\n.writing-page footer#next-section{margin:35px 0;font-size:14px}\n@media(max-width:700px){.writing-opening-title .writing-indent{font-size:17px;margin-left:1em}.writing-indent{margin-left:1em}.glossary-components{grid-template-columns:1fr}}\n\n.writing-page p,.writing-page li{font-size:16px}\n.writing-page h1{font-size:28px;font-weight:750;line-height:1.6}\n.writing-page h2,.writing-page h2.writing-opening-title{font-size:23px;font-weight:750;line-height:1.75}\n.writing-page h3,.writing-page h3.summary-question{font-size:19px!important;font-weight:700;line-height:1.8}\n.writing-label{font-weight:400}\n.glossary-entry summary{font-size:18px;font-weight:700}\n.glossary-entry[open]>summary{font-weight:700}\n.book-shell{display:grid;grid-template-columns:300px minmax(0,980px);gap:30px;max-width:1360px;margin:auto}\n.book-shell>main{width:100%;min-width:0;box-sizing:border-box}\n.book-sidebar{position:sticky;top:0;max-height:100vh;overflow:auto;padding:25px 16px;box-sizing:border-box}\n.book-sidebar h2{font-size:20px;font-weight:700;line-height:1.7}\n.book-sidebar summary{font-size:15px;font-weight:700;line-height:1.8;cursor:pointer}\n.book-sidebar li{font-size:13px;line-height:1.8;margin:10px 0}\n.book-sidebar ul{padding-left:20px}\n.book-sidebar a[aria-current]{font-weight:700;color:#315239}\n#book-navigation{display:flex;justify-content:space-between;gap:20px;margin:20px 0}\n#book-overview details{margin:12px 0}\n@media(max-width:900px){.book-shell{display:block}.book-sidebar{position:static;max-height:40vh}.writing-page h1{font-size:25px}.writing-page h2,.writing-page h2.writing-opening-title{font-size:22px}.writing-page h3,.writing-page h3.summary-question{font-size:18px!important}.writing-page p,.writing-page li{font-size:15px}}\n\n.writing-block img{max-width:100%;height:auto;display:block;margin:16px auto}\n\n#book-toc{display:block}#book-toc>details{display:block;margin:14px 0}#book-toc summary{font-size:17px}#book-toc a{display:inline;padding:0;border:0;border-radius:0;background:transparent}#book-toc li{display:list-item}#book-overview summary{font-size:18px;font-weight:700;line-height:1.8}\n\n/* 四栏各自滚动，原材料和术语保持在正文两侧，窄屏按面板切换 */\n.writing-core-questions{background:none;border:0;border-radius:0;padding:0 0 0 1.4em}\n.writing-core-questions li{font-size:16px;line-height:1.95}\n.demo-page{background:#f4f5f1}\n.demo-masthead{margin:0;padding:16px 26px;border-bottom:1px solid var(--line);background:#fff;min-height:116px}\n.demo-masthead h1{font-size:23px;line-height:1.55;margin:2px 0}\n.demo-masthead .help{font-size:12px;margin:4px 0 0}\n.demo-home{font-size:13px;white-space:nowrap}\n.demo-shell{margin:0 auto;max-width:1100px}\n.demo-page .demo-explanation{max-width:980px;padding:20px 32px 50px;min-width:0}\n.demo-page .demo-directory,.demo-page .demo-terms{margin:auto;max-width:980px;padding:22px 28px}\n.demo-page .demo-directory h2,.demo-page .demo-original h2,.demo-page .demo-terms h2{font-size:21px;line-height:1.6;margin:0 0 14px}\n.demo-page .demo-directory nav{display:block}\n.demo-page .text-action{background:none;border:0;border-radius:0;padding:2px 0;color:var(--green);text-align:left;font-size:12px;font-weight:500;text-decoration:underline;text-underline-offset:3px;line-height:1.7}\n.demo-outline-section,.demo-outline-question{display:block;width:100%;text-align:left;background:none;color:#37523f;border:0;border-radius:3px;padding:9px 10px;line-height:1.8}\n.demo-outline-section{font-size:14px;font-weight:700;margin:6px 0}\n.demo-outline-label{font-size:14px!important;font-weight:700;padding:0 10px;margin-top:16px}\n.demo-outline-question{font-size:13px;font-weight:400;margin:3px 0}\n.demo-outline-question[aria-current]{background:#e8eee5;box-shadow:inset 3px 0 #557b57;font-weight:600}\n.demo-tools{margin:22px 0;font-size:12px;line-height:1.8}\n.demo-tools>summary{font-size:13px}\n.demo-tools .downloads{display:grid;gap:10px;margin:12px 0}\n.demo-directory>.help{font-size:12px;line-height:1.8}\n.demo-page .writing-opening h2{margin-top:4px}\n.demo-page .writing-unit{scroll-margin-top:20px}\n.demo-page .unit-source-button{display:block;margin:-10px 0 16px}\n.writing-block{scroll-margin-top:30px;transition:background-color .25s}\n.writing-block-highlight{background:#fff2ca;outline:2px solid #b99b46;outline-offset:7px;border-radius:2px}\n.coverage-details{border-top:1px solid var(--line);margin-top:22px;padding-top:18px;font-size:12px}\n.coverage-details>summary{font-size:13px;line-height:1.9}\n.coverage-details .help{font-size:12px;line-height:1.8}\n.coverage-source{border-bottom:1px solid var(--line);padding:12px 0}\n.coverage-source>summary{font-size:12px;line-height:1.85;overflow-wrap:anywhere}\n.coverage-point{padding:10px 0;border-bottom:1px solid #e7ece3}\n.coverage-point:last-child{border-bottom:0}\n.demo-page .coverage-point p{font-size:12px;line-height:1.8;margin:3px 0}\n.coverage-point-state{font-size:11px;color:#597750}\n.coverage-block-links{display:flex;gap:12px;flex-wrap:wrap}\n.demo-source-label{font-size:12px;font-weight:400;margin:0 0 8px}\n#source-unit-select{font-size:12px;line-height:1.7;padding:8px;min-width:0}\n.demo-source-card{border-bottom:1px solid var(--line);padding:16px 0 22px;scroll-margin-top:18px;overflow-wrap:anywhere}\n.demo-page .demo-source-card h3{font-size:18px!important;line-height:1.7;margin:0 0 7px}\n.demo-source-card>.help{font-size:11px;line-height:1.7}\n.source-sentence-pair{margin:18px 0 23px}\n.demo-page .source-translation p{font-size:15px;line-height:1.95;margin:5px 0}\n.demo-page .source-original p{font-size:13px;line-height:1.9;color:#657268;margin:5px 0}\n.source-original{margin-top:9px}\n.source-text-label{font-size:10px;letter-spacing:.08em;color:#73816d}\n.demo-source-figure{margin:14px 0}\n.demo-source-figure img{display:block;max-width:100%;height:auto;background:white}\n.demo-source-figure figcaption{font-size:12px;line-height:1.8;margin:9px 0;color:#66776c}\n.source-coverage{font-size:12px;margin-top:14px}\n.source-coverage>summary{font-size:12px;line-height:1.8}\n.source-scope,.source-image-labels{margin:14px 0;font-size:12px}\n.source-scope>summary,.source-image-labels>summary{font-size:12px;line-height:1.85}\n.demo-page .source-scope p,.demo-page .coverage-scope-note{font-size:12px;line-height:1.9;color:#66776c}\n.source-image-labels>.source-sentence-pair{border-bottom:1px solid #e7ece3;padding-bottom:14px}\n.demo-page .demo-terms #glossary-count{font-size:12px;line-height:1.85}\n.demo-page .demo-terms #glossary-search{font-size:13px}\n.demo-page .demo-terms .glossary-entry summary{font-size:17px;line-height:1.8}\n.demo-page .demo-terms .glossary-entry p{font-size:14px;line-height:1.95}\n.grounded-demo{height:100dvh;overflow:hidden;display:flex;flex-direction:column}\n.grounded-demo .demo-masthead{flex:0 0 auto;min-height:0;padding:12px 22px}\n.grounded-demo .demo-masthead h1{font-size:22px}\n.grounded-demo .demo-shell{display:grid;grid-template-columns:minmax(190px,.75fr) minmax(300px,1.25fr) minmax(410px,1.8fr) minmax(270px,1.05fr);width:100%;max-width:none;flex:1;min-height:0;margin:0;overflow:hidden}\n.grounded-demo .demo-reading-pane{height:100%;min-height:0;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable;scroll-behavior:smooth;background:#fff;border-right:1px solid var(--line);padding:22px 20px 50px;max-width:none;margin:0}\n.grounded-demo .demo-directory{background:#f4f6f0;padding:22px 14px 50px}\n.grounded-demo .demo-explanation{padding:22px 32px 70px}\n.grounded-demo .demo-terms{border-right:0;background:#fafbf8}\n.grounded-demo .demo-original{background:#fbfcf9}\n.grounded-demo .demo-pane-tabs{display:none}\n@media(min-width:1900px){.grounded-demo .demo-shell{grid-template-columns:minmax(230px,.7fr) minmax(380px,1.15fr) minmax(650px,2fr) minmax(320px,1fr)}}\n@media(max-width:1199px){\n  .grounded-demo .demo-masthead{padding:12px 16px;display:flex;align-items:flex-start;gap:12px}\n  .grounded-demo .demo-masthead h1{font-size:19px}\n  .grounded-demo .demo-home{font-size:12px}\n  .grounded-demo .demo-pane-tabs{display:flex;gap:4px;padding:8px 12px;flex:0 0 auto;background:#f4f6f0;border-bottom:1px solid var(--line)}\n  .grounded-demo .demo-pane-tabs button{flex:1;min-width:0;padding:8px 5px;border-radius:4px;background:none;color:#52694e;font-size:13px}\n  .grounded-demo .demo-pane-tabs button[aria-pressed=true]{background:#e3ebdd;color:#2a4e37;box-shadow:inset 0 -2px #557b57}\n  .grounded-demo .demo-shell{display:block;min-height:0}\n  .grounded-demo .demo-reading-pane{display:none;width:100%;padding:22px 24px 65px;border:0}\n  .grounded-demo[data-active-pane=directory] [data-pane=directory],.grounded-demo[data-active-pane=source] [data-pane=source],.grounded-demo[data-active-pane=lesson] [data-pane=lesson],.grounded-demo[data-active-pane=glossary] [data-pane=glossary]{display:block}\n  .grounded-demo .demo-explanation article{max-width:760px;margin:auto}\n  .grounded-demo .demo-original #source-cards{max-width:760px;margin:auto}\n}\n@media(max-width:700px){\n  .demo-masthead{padding:14px 16px;display:block}\n  .demo-masthead h1{font-size:21px}\n  .grounded-demo .demo-home{display:none}\n  .grounded-demo .demo-reading-pane{padding:20px 17px 55px}\n  .grounded-demo .demo-masthead h1{font-size:18px;line-height:1.6}\n  .grounded-demo .demo-masthead .help{font-size:11px}\n  .grounded-demo .demo-masthead .eyebrow{display:none}\n  .demo-page .demo-explanation{padding:20px 17px 55px}\n  .demo-page .demo-directory,.demo-page .demo-terms{padding:20px 17px}\n}\n\n/* 正常阅读只保留原材料与教学内容，检查记录通过 Debug 开关显示 */\n.writing-page .debug-only{display:none!important}\n.writing-page.show-debug .debug-only:not([hidden]){display:revert!important}\n.demo-page:not(.show-debug) .writing-role{display:none!important}\n.demo-header-actions{display:flex;align-items:center;gap:18px;flex:none}\n.debug-toggle{display:flex;align-items:center;gap:6px;white-space:nowrap;font-size:12px;font-weight:400;margin:0}\n.debug-toggle input{width:auto;margin:0}\n.writing-note h4{font-size:14px;font-weight:700;line-height:1.8;margin:0 0 10px;color:#52694d}\n.writing-note label{display:block;font-size:12px;font-weight:400}\n.writing-note textarea{display:block;width:100%;box-sizing:border-box;margin-top:8px;resize:vertical}\n.source-language-modes{display:flex;gap:5px;margin:0 0 18px}\n.source-language-modes button{flex:1;font-size:12px;padding:7px 5px;border:1px solid #d8e0d2;background:transparent;color:#52694e;white-space:nowrap}\n.source-language-modes button[aria-pressed=true]{background:#e8eee3;border-color:#799171;color:#2d5139;font-weight:600}\n.demo-original[data-language=zh] .source-original:not(.source-code):not(.source-single-language){display:none}\n.demo-original[data-language=en] .source-translation{display:none}\n.demo-original[data-language=en] .source-original{margin-top:0}\n.source-sentence-highlight{background:#fff3cc;border-left:3px solid #b89b4b;padding:10px 12px;border-radius:2px}\n.source-sentence-highlight .source-original p{color:#4a574c}\n#source-preview-controls,#glossary-preview-controls{padding:10px 0 14px;border-bottom:1px solid var(--line);margin-bottom:14px}\n#source-preview-controls[hidden],#glossary-preview-controls[hidden]{display:none}\n.source-region-image{display:block;overflow:hidden;background:#fff}\n.source-region-image svg{display:block;width:100%;height:auto;overflow:hidden}\n.source-region-caption{margin:8px 0}\n.demo-page .source-region-caption p{font-size:12px;line-height:1.8;margin:4px 0}\n.writing-source-figure{margin:18px 0}\n.writing-source-figure figcaption{font-size:13px;line-height:1.85;color:#5f6e61;margin:10px 0}\n.writing-source-figure>a.text-action{display:inline-block;margin-top:5px}\n.source-image-region{margin:0 0 16px}\n.inline-term{border-bottom:1px dotted #8b9e7b;cursor:help;border-radius:2px}\n.inline-term:hover,.inline-term:focus-visible,.inline-term.is-term-active{background:#e9efdc;color:#274c34;outline:0;border-bottom-color:#52794e}\n.inline-term:focus-visible{box-shadow:0 0 0 2px #88a078}\n.has-source-marker{position:relative;padding-left:23px}\n.writing-page button.source-marker{position:absolute;left:-6px;top:3px;width:25px;min-height:28px;padding:1px 3px;border:0;background:none;border-radius:3px;font-size:17px;font-weight:500;line-height:1.5;color:#6d8168;cursor:help}\n.writing-page button.source-marker:hover,.writing-page button.source-marker:focus-visible,.writing-page button.source-marker[aria-pressed=true]{color:#2e553a;background:#edf0df;outline:1px solid #b9c5ac}\n.demo-page .glossary-entry[hidden]{display:none}\n.writing-note{background:#f7f9f3;padding:14px 16px;border-color:#e0e6d8}\n@media(max-width:700px){.demo-header-actions{gap:8px}.debug-toggle{font-size:11px}.has-source-marker{padding-left:21px}.writing-page button.source-marker{left:-5px}}\n\n.lw-reader-root{--app:#eeeeec;--surface:#f7f7f5;--canvas:#fff;--raised:#fff;--hover:#e9e9e6;--selected:#dededb;--line:#d4d4d0;--input-line:#777774;--text:#232321;--secondary:#545451;--muted:#61615d;--focus:#323230;--green:var(--text);--body-size:17px;--body-line:1.95;--panel-gap:16px;--radius:8px;color-scheme:light}\n.lw-reader-root[data-theme=dark]{color-scheme:dark}\n*{box-sizing:border-box}\n.lw-reader-root,.lw-reader-root{height:100%;margin:0}\n.lw-reader-root.reader-ui{height:100dvh;display:flex;flex-direction:column;overflow:hidden;background:var(--app);color:var(--text);font-family:\"Segoe UI Variable\",\"Segoe UI\",\"PingFang SC\",\"Microsoft YaHei\",sans-serif;font-size:14px}\nbutton,input,select,textarea{font:inherit;color:var(--text)}\nbutton{background:var(--text);color:var(--canvas);border:1px solid transparent;border-radius:6px;min-height:36px;padding:7px 12px;cursor:pointer;line-height:1.5}\nbutton.secondary{background:var(--hover);color:var(--text);border-color:var(--line)}\nbutton:hover{filter:none}\na{color:var(--text);text-underline-offset:4px}\ninput,select,textarea{background:var(--canvas);border:1px solid var(--input-line);border-radius:6px;padding:8px 10px}\nbutton:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--focus);outline-offset:3px}\ninput[type=checkbox],input[type=radio],input[type=range]{accent-color:var(--text)}\ninput[type=range]{padding:0}\n.skip-link{position:fixed;left:12px;top:-100px;z-index:200;background:var(--canvas);padding:10px}\n.skip-link:focus{top:8px}\n.reader-ui .demo-masthead{height:68px;min-height:68px;flex:none;display:flex;align-items:center;justify-content:space-between;gap:24px;margin:0;padding:8px 20px;background:var(--surface);border:0}\n.document-heading{display:flex;gap:14px;align-items:center;min-width:0}\n.book-symbol{display:flex;flex:none;width:28px;height:28px;color:var(--text)}\n.book-symbol svg{width:24px;height:24px}\n.document-name{min-width:0}\n.reader-ui .document-name .eyebrow{font-size:11px;line-height:1.5;color:var(--secondary);letter-spacing:.02em;margin:0 0 2px}\n.edition-label{border-left:1px solid var(--line);padding-left:8px;margin-left:8px}\n.reader-ui .demo-masthead h1{font-size:15px;font-weight:650;line-height:1.6;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.demo-header-actions{gap:16px;display:flex;align-items:center}\n.control-group{display:flex;gap:4px;align-items:center}\n.control-group+.control-group{padding-left:12px;border-left:1px solid var(--line)}\n.icon-button{width:36px;height:36px;min-height:36px;display:inline-flex;align-items:center;justify-content:center;flex:none;border:0;background:transparent;color:var(--secondary);padding:8px;border-radius:6px}\n.icon-button svg{display:block;width:20px;height:20px;flex:none}\n.icon-button:hover,.icon-button[aria-pressed=true]{background:var(--hover);color:var(--text)}\n.icon-button:active{background:var(--selected)}\n.reader-ui #demo-pane-tabs{display:none!important}\n.reader-ui .demo-shell{position:relative;display:grid;grid-template-columns:var(--columns,minmax(0,1fr));gap:var(--panel-gap);flex:1;min-height:0;max-width:none;width:auto;margin:0 16px;overflow:visible}\n.reader-ui .demo-reading-pane{position:relative;display:block!important;min-width:0;width:auto;height:100%;max-height:none;margin:0;padding:0;border:1px solid var(--line);border-radius:var(--radius);background:var(--canvas);color:var(--text);overflow:auto;scrollbar-width:thin;scrollbar-color:var(--line) transparent;scrollbar-gutter:stable;overscroll-behavior:contain;scroll-padding-top:108px}\n.reader-ui .demo-reading-pane[data-ui-visible=false]{display:none!important}\n.reader-ui .demo-directory,.reader-ui .demo-terms{background:var(--surface)}\n.pane-head{position:sticky;top:0;z-index:5;height:48px;min-height:48px;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 12px 6px 16px;background:var(--surface);border-bottom:1px solid var(--line)}\n.reader-ui .pane-head h2{font-size:14px;font-weight:650;line-height:1.5;margin:0;color:var(--text)}\n.pane-head .icon-button{width:32px;height:32px;min-height:32px;padding:7px}\n.pane-head .icon-button svg{width:16px;height:16px}\n.lesson-head{background:var(--canvas)}\n#reading-location{color:var(--secondary);font-size:12px;font-variant-numeric:tabular-nums}\n.pane-content{padding:12px 16px 40px}\n.pane-sticky-tools{position:sticky;top:48px;z-index:4;background:var(--surface);padding:10px 14px;border-bottom:1px solid var(--line)}\n.reader-ui .source-language-modes{margin:0;gap:2px;background:var(--app);padding:3px;border-radius:6px}\n.reader-ui .source-language-modes button{min-height:30px;font-size:12px;padding:4px 6px;background:transparent;border:0;color:var(--secondary);border-radius:4px}\n.reader-ui .source-language-modes button[aria-pressed=true]{background:var(--canvas);color:var(--text);font-weight:650;box-shadow:0 1px 2px #0000000d}\n.reader-ui .demo-source-label{font-size:12px;color:var(--secondary);margin:0 0 6px}\n.reader-ui #source-unit-select{min-height:36px;font-size:12px;padding:7px;width:100%;color:var(--text)}\n.reader-ui #source-context{font-size:12px;line-height:1.8;color:var(--secondary);margin:12px 0}\n.reader-ui .demo-source-card{border-color:var(--line);padding:16px 0 24px}\n.reader-ui .source-translation p{font-size:15px;line-height:1.95;color:var(--text)}\n.reader-ui .source-original p{font-size:13px;line-height:1.9;color:var(--secondary)}\n.reader-ui .source-text-label,.reader-ui .help{color:var(--secondary)}\n.reader-ui .source-sentence-highlight{background:transparent;border-color:transparent}\n.reader-ui .source-sentence-highlight .source-original p{color:var(--secondary)}\n.reader-ui .source-sentence-pair{scroll-margin-top:110px}\n.reader-ui .text-action{font-size:12px;background:transparent;min-height:28px;color:var(--text);border:0;padding:3px 0}\n.directory-context{padding:20px 16px 16px;border-bottom:1px solid var(--line)}\n.directory-context span{font-size:11px;color:var(--secondary)}\n.reader-ui .directory-context p{font-size:14px;line-height:1.8;font-weight:600;margin:4px 0 0}\n.reader-ui #demo-outline{display:block;padding:12px 8px}\n.reader-ui .demo-outline-section,.reader-ui .demo-outline-question{display:block;max-width:100%;color:var(--text);background:transparent;border:0;border-radius:4px;min-height:36px;padding:8px 9px;text-align:left;line-height:1.6}\n.reader-ui .demo-outline-section{font-weight:600;font-size:13px;margin:2px 0}\n.reader-ui .demo-outline-question{font-size:12px;font-weight:400;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-left:18px;margin:2px 0;color:var(--secondary)}\n.reader-ui .demo-outline-label{font-size:12px!important;color:var(--secondary);margin:12px 0 0;padding-left:9px}\n.reader-ui .demo-outline-section:hover,.reader-ui .demo-outline-question:hover{background:var(--hover)}\n.reader-ui #demo-outline [aria-current],.reader-ui #demo-outline .is-reading-current{background:var(--selected);color:var(--text);box-shadow:inset 2px 0 var(--text)}\n.reader-ui .directory-footnote{font-size:12px;line-height:1.8;color:var(--secondary);margin:8px 16px 24px}\n.reader-ui .lesson-content{max-width:760px;margin:auto;padding:24px 32px 56px}\n.reader-ui .lesson-content p,.reader-ui .lesson-content li{font-size:var(--body-size);line-height:var(--body-line);color:var(--text)}\n.reader-ui .lesson-content h2,.reader-ui .lesson-content h2.writing-opening-title{font-size:calc(var(--body-size) + 6px);line-height:1.7;font-weight:700;margin:34px 0 16px;color:var(--text)}\n.reader-ui .lesson-content h3,.reader-ui .lesson-content h3.summary-question{font-size:calc(var(--body-size) + 3px)!important;line-height:1.8;font-weight:650;margin:24px 0 14px;color:var(--text)}\n.reader-ui .writing-opening h2:first-child{margin-top:0}\n.reader-ui .writing-block{margin:18px 0}\n.reader-ui .writing-block p{margin:0 0 8px}\n.reader-ui .writing-core-questions{border:0;background:transparent;border-radius:0;padding:0 0 0 24px;margin:14px 0 32px}\n.reader-ui .writing-core-questions li{margin:10px 0;padding-left:3px}\n.reader-ui .writing-unit{border-color:var(--line);padding-bottom:24px;scroll-margin-top:68px}\n.reader-ui .writing-note{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:16px;margin:24px 0 16px}\n.reader-ui .writing-note h4{color:var(--text);font-size:14px;font-weight:600}\n.reader-ui .writing-note textarea{background:var(--canvas);font-size:15px;min-height:88px;line-height:1.8;border-color:var(--line)}\n.reader-ui .writing-note button{font-size:12px;min-height:32px;padding:5px 10px}\n.reader-ui .writing-note label,.reader-ui .writing-note .help{color:var(--secondary);font-size:12px}\n.reader-ui .writing-pitfall{border-color:var(--line);background:transparent;padding:0 0 0 16px;margin:24px 0}\n.reader-ui .quiz-card{border-color:var(--line);border-radius:8px;padding:18px;background:transparent}\n.reader-ui .quiz-options label{background:var(--surface);color:var(--text);border:1px solid transparent;border-radius:4px;line-height:1.8;font-size:15px}\n.reader-ui .quiz-options label:has(input:checked){border-color:var(--text);background:var(--hover)}\n.reader-ui .quiz-answer{background:var(--surface);color:var(--text)}\n.reader-ui .quiz-card input{flex:none}\n.reader-ui .inline-term{border-color:var(--secondary);color:inherit}\n.reader-ui .inline-term:hover,.reader-ui .inline-term:focus-visible,.reader-ui .inline-term.is-term-active{background:var(--selected);color:var(--text);border-color:var(--text)}\n.reader-ui .source-marker{color:var(--secondary)!important}\n.reader-ui .source-marker:hover,.reader-ui .source-marker[aria-pressed=true]{color:var(--text)!important;background:var(--hover)!important;outline-color:var(--line)!important}\n.reader-ui .writing-source-figure{margin:22px 0}\n.reader-ui .writing-source-figure img,.reader-ui .demo-source-figure img,.reader-ui .source-region-image{border-radius:4px;cursor:zoom-in;background:#fff}\n.reader-ui .writing-source-figure figcaption{font-size:13px;line-height:1.85;color:var(--secondary)}\n.reader-ui .table-scroll{border-radius:4px;overflow:auto}\n.reader-ui td,.reader-ui th{border-color:var(--line);font-size:14px!important;color:var(--text)}\n.reader-ui th{background:var(--surface);font-weight:600}\n.reader-ui pre{background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:4px}\n.glossary-search-wrap{display:flex;align-items:center;gap:8px}\n.glossary-search-wrap>span{display:flex;width:16px;height:16px;flex:none;color:var(--secondary)}\n.glossary-search-wrap input{min-width:0;font-size:13px!important;height:32px;min-height:32px;border:0;background:transparent;padding:3px 0;outline-offset:2px}\n.reader-ui .demo-terms #glossary-count{font-size:12px;color:var(--secondary);margin:0 0 12px}\n.reader-ui .glossary-entry{border-color:var(--line);padding:14px 0}\n.reader-ui .demo-terms .glossary-entry summary{font-size:14px;line-height:1.85;font-weight:600;color:var(--text)}\n.reader-ui .demo-terms .glossary-entry p{font-size:14px;line-height:1.95;color:var(--text);margin:12px 0}\n.reader-ui .glossary-entry[open]{padding-bottom:20px}\n.reader-ui .demo-tools,.reader-ui .coverage-details{margin:16px;color:var(--secondary)}\n.reader-ui .coverage-source,.reader-ui .coverage-point{border-color:var(--line);background:var(--surface);color:var(--text)}\n.reader-ui .workspace-footer{display:flex;align-items:center;gap:16px;height:36px;min-height:36px;flex:none;margin:0;padding:0 20px;font-size:11px;line-height:1.5;color:var(--secondary);background:var(--app)}\n#ui-status{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n#layout-status{white-space:nowrap}\n.workspace-footer .debug-toggle{font-size:11px;gap:5px;margin:0;color:var(--secondary)}\n.resizer{position:absolute;top:0;bottom:0;width:12px;cursor:col-resize;z-index:6;border-radius:3px;touch-action:none}\n.resizer::after{content:\"\";position:absolute;left:5px;top:calc(50% - 18px);height:36px;width:2px;border-radius:1px;background:var(--line)}\n.resizer:hover::after,.resizer:focus-visible::after{background:var(--text)}\n.lw-reader-root.is-resizing,.lw-reader-root.is-resizing *{cursor:col-resize!important;user-select:none!important}\n#drawer-backdrop{position:fixed;inset:68px 0 36px;background:#0004;z-index:15}\n.reader-ui .demo-reading-pane.ui-drawer{position:fixed;top:76px;bottom:44px;left:16px;z-index:20;display:block!important;width:min(440px,calc(100vw - 32px));height:auto;box-shadow:0 14px 50px #0003;border:1px solid var(--input-line)}\n.reader-ui .demo-reading-pane.ui-drawer[data-pane=glossary]{left:auto;right:16px;width:min(380px,calc(100vw - 32px))}\n.reader-ui dialog{border:1px solid var(--line);background:var(--raised);color:var(--text);border-radius:12px;padding:0;max-height:calc(100dvh - 32px);width:min(430px,calc(100vw - 32px));box-shadow:0 20px 80px #0004}\ndialog::backdrop{background:#0006}\n.reader-ui dialog header,.reader-ui dialog footer{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0;padding:14px 18px;border-bottom:1px solid var(--line)}\n.reader-ui dialog header h2{font-size:17px;margin:0;font-weight:650}\n.reader-ui dialog footer{border-top:1px solid var(--line);border-bottom:0}\n.settings-content{padding:18px 20px;max-height:calc(100dvh - 220px);overflow:auto}\n.settings-content label{font-weight:500;font-size:14px;display:flex;justify-content:space-between;margin:4px 0 14px}\n.settings-content input{margin-bottom:24px}\n.reader-ui .settings-content p{font-size:13px;line-height:1.8;color:var(--secondary)}\n.settings-content a{font-size:13px}\n.reader-ui #image-viewer{width:calc(100vw - 40px);max-width:1500px;height:calc(100dvh - 40px);max-height:none;padding:44px 16px 16px;background:var(--surface)}\n.image-close{position:absolute;right:8px;top:4px}\n#image-stage{height:100%;overflow:auto;display:flex;align-items:flex-start;justify-content:center}\n#image-stage img{max-width:100%;height:auto;object-fit:contain;display:block;background:#fff}\n#ui-tooltip{position:fixed;z-index:100;max-width:min(440px,calc(100vw - 24px));background:var(--raised);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:8px 10px;font-size:12px;line-height:1.7;box-shadow:0 3px 12px #0002;pointer-events:auto}\n[hidden]{display:none!important}\n@media(max-width:899px){.reader-ui .demo-masthead{height:60px;min-height:60px;gap:8px;padding:8px 12px}.book-symbol{display:none}.document-heading{flex:1}.document-name .eyebrow{display:none}.reader-ui .demo-masthead h1{font-size:13px}.demo-header-actions{gap:4px}.control-group{gap:0}.control-group+.control-group{padding-left:4px;border-left:0}.icon-button{width:36px;height:40px;min-height:40px}.reader-ui .demo-shell{margin:0 8px}.reader-ui .lesson-content{padding:22px 22px 40px}.reader-ui .workspace-footer{height:32px;min-height:32px;padding:0 12px;gap:8px}#layout-status{display:none}.reader-ui .demo-reading-pane.ui-drawer{top:68px;bottom:40px;left:8px;width:calc(100vw - 16px);max-width:440px}.reader-ui .demo-reading-pane.ui-drawer[data-pane=glossary]{right:8px;max-width:380px}#drawer-backdrop{inset:60px 0 32px}.resizer{display:none!important}.edition-label{display:none}}\n@media(max-width:500px){.reader-ui .demo-masthead h1{font-size:12px}.control-group+.control-group{padding-left:0}.icon-button{width:32px;padding:7px}.control-group .icon-button svg{width:18px}.reader-ui .lesson-content{padding:20px 18px 40px}.reader-ui .lesson-content h2{font-size:calc(var(--body-size) + 4px)!important}.reader-ui .lesson-content h3{font-size:calc(var(--body-size) + 2px)!important}.reader-ui .quiz-card{padding:12px}.document-name{max-width:100%}.demo-header-actions{gap:0}}\n@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}\n@media(max-width:899px){#focus-reading{display:none}}\n@media(pointer:coarse){.icon-button{width:44px;height:44px;min-height:44px}.pane-head{padding:2px 8px 2px 16px}.pane-head .icon-button{width:44px;height:44px;min-height:44px}.reader-ui .source-language-modes button{min-height:44px}.reader-ui .has-source-marker{padding-left:40px}.reader-ui button.source-marker{width:44px!important;min-height:44px;left:-4px}.reader-ui .demo-outline-section,.reader-ui .demo-outline-question{min-height:44px}}\n@media(forced-colors:active){.icon-button[aria-pressed=true]{outline:1px solid Highlight}.pane-head,.demo-reading-pane{border-color:CanvasText!important}.resizer::after{background:CanvasText}}\n\n/* 原文与译文在上方独立滚动，原页定位在下方持续可见 */\n.reader-ui #demo-original[data-ui-visible=true],.reader-ui #demo-original.ui-drawer{display:flex!important;flex-direction:column;overflow:hidden;scrollbar-gutter:auto}\n#demo-original>.pane-head,#demo-original>.pane-sticky-tools{position:static;flex:none}\n.source-content{display:grid;grid-template-rows:auto minmax(80px,var(--source-upper-fr,1fr)) 12px minmax(270px,1fr);min-height:470px;flex:1;padding:12px 0 0}\n.source-question-choice{padding:0 16px 10px;flex:none}\n#source-text-scroll{min-height:80px;flex:1;overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:0 16px;scroll-padding-top:12px}\n.reader-ui #source-text-scroll .source-sentence-pair{scroll-margin-top:14px}\n#source-locator{display:flex;flex-direction:column;border-top:1px solid var(--line);background:var(--canvas);padding:0;min-width:0;min-height:270px;overflow:hidden}\n#demo-original .locator-heading{position:static;flex:none;border-top:0}\n.reader-ui #demo-original .pane-head h2{font-size:14px;font-weight:650;line-height:1.5;margin:0;color:var(--text)}\n.locator-body{min-height:0;display:flex;flex-direction:column;flex:1;padding:6px 12px}\n.locator-sources{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0 6px;min-height:26px}\n.locator-sources button,.locator-toolbar button[data-locator-mode]{background:transparent;color:var(--secondary);min-height:26px;padding:2px 6px;font-size:11px;border:1px solid transparent;white-space:nowrap}\n.locator-sources button[aria-pressed=true],.locator-toolbar button[aria-pressed=true]{background:var(--canvas);color:var(--text);border-color:var(--line);font-weight:600}\n.locator-toolbar{display:flex;align-items:center;justify-content:space-between;gap:4px;margin:0 0 6px}\n.locator-toolbar>div{display:flex;gap:2px}\n.locator-surface{flex:1;min-height:100px;border:1px solid var(--line);border-radius:4px;overflow:hidden;background:white}\n.locator-viewport{height:100%;width:100%;overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;position:relative;scroll-behavior:auto}\n.locator-page{position:relative;min-width:0;margin-inline:auto;line-height:0}\n#locator-image{display:block;width:100%;height:auto;max-width:none;background:white}\n#locator-highlights{position:absolute;inset:0;pointer-events:none}\n.locator-highlight{position:absolute;display:block;border:2px solid #a96b0d;background:#efad362a;box-shadow:0 0 0 2px #fff9}\n#locator-dom{border:0;width:100%;height:100%;display:block;background:white}\n.reader-ui #locator-status{font-size:11px;line-height:1.6;color:var(--secondary);margin:6px 0 0}\n.reader-ui .source-sentence-pair.is-locator-selected{box-shadow:none;border-left-color:transparent;background:transparent}\n.reader-ui .source-sentence-pair.is-locator-selected .source-translation,\n.reader-ui .source-sentence-pair.is-locator-selected[data-reading-language=zh] .source-original.source-single-language{background:var(--selected);box-shadow:0 0 0 5px var(--selected);border-radius:2px}\n.reader-ui #source-text-scroll .source-sentence-pair{margin:10px 0 14px}\n.reader-ui #source-text-scroll .source-translation p{line-height:1.85;margin:4px 0}\n.reader-ui .source-sentence-pair{cursor:pointer}\n.locator-sentence-navigation{display:flex;align-items:center;justify-content:space-between;gap:4px;flex:none;margin:0 0 4px;font-size:11px;color:var(--secondary)}\n.locator-sentence-navigation button{font-size:11px;min-height:24px}\n.locator-sentence-navigation button:disabled{opacity:.35;cursor:default}\n.source-splitter{position:relative;cursor:row-resize;touch-action:none;background:var(--surface);border-block:1px solid var(--line)}\n.source-splitter::after{content:\"\";position:absolute;left:calc(50% - 18px);top:4px;width:36px;height:2px;border-radius:1px;background:var(--input-line)}\n.source-splitter:hover::after,.source-splitter:focus-visible::after{background:var(--text)}\n.is-source-resizing,.is-source-resizing *{cursor:row-resize!important;user-select:none!important}\n.is-source-resizing iframe{pointer-events:none}\n.reader-ui #locator-dialog{width:min(1100px,calc(100vw - 32px));max-width:none;height:calc(100dvh - 48px)}\n#locator-dialog-content{height:calc(100% - 66px);padding:16px}\n#locator-dialog-content .locator-surface{height:100%;width:100%}\n.reader-ui #demo-original[data-ui-visible=true],.reader-ui #demo-original.ui-drawer{overflow:auto}\n@media(max-height:650px){.locator-sources{margin:2px 0}.source-question-choice{padding-bottom:6px}.source-content{padding-top:6px;min-height:430px}#locator-status{margin-top:2px!important}}\n@media(pointer:coarse){.locator-sources button,.locator-toolbar button[data-locator-mode]{min-height:36px}.source-content{grid-template-rows:auto minmax(80px,var(--source-upper-fr,1fr)) 20px minmax(300px,1fr);min-height:500px}#source-locator{min-height:300px}.source-splitter::after{top:8px}}\n.locator-head-actions,.locator-zoom-controls{display:flex;align-items:center;gap:2px;flex:none}\n.locator-head-actions{gap:4px}\n.locator-heading{gap:4px}\n.locator-zoom-controls .icon-button{width:26px;height:32px;min-height:32px;padding:5px}\n.locator-zoom-controls .icon-button svg{width:16px;height:16px}\n.locator-zoom-controls .zoom-reset{width:42px;min-width:42px;height:32px;min-height:32px;padding:3px 0;background:transparent;color:var(--secondary);border:0;font-size:11px;font-variant-numeric:tabular-nums}\n.locator-zoom-controls button:hover{background:var(--hover);color:var(--text)}\n.locator-zoom-controls button:disabled{opacity:.35;cursor:default}\n.locator-zoom-controls button:disabled:hover{background:transparent}\n#locator-dialog>header h2{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n@media(pointer:coarse){.locator-zoom-controls .icon-button{width:32px;height:44px;min-height:44px}.locator-zoom-controls .zoom-reset{height:44px;min-height:44px}.locator-head-actions{gap:2px}}\n\n.reader-ui .book-directory-title{font-size:14px;font-weight:650;line-height:1.8;margin:16px 16px 8px}\n.reader-ui #book-toc{padding:0 12px 12px;border-bottom:1px solid var(--line)}\n.reader-ui #book-toc>details{margin:8px 0}\n.reader-ui #book-toc summary{font-size:13px;font-weight:600;line-height:1.8;padding:6px 4px;cursor:pointer}\n.reader-ui #book-toc ul{margin:4px 0 8px;padding-left:16px;list-style:none}\n.reader-ui #book-toc li{margin:4px 0}\n.reader-ui #book-toc a{display:block;font-size:12px;line-height:1.8;padding:5px 6px;border-radius:4px;text-decoration:none}\n.reader-ui #book-toc a:hover{background:var(--hover)}\n.reader-ui #book-toc a[aria-current=page]{background:var(--selected);box-shadow:inset 2px 0 var(--text)}\n.reader-ui #book-navigation{font-size:13px;border-top:1px solid var(--line);padding-top:16px}\n.reader-ui #book-navigation:empty{display:none}\n.reader-ui #preview-diagnostics pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}\n.reader-ui .draft-status{font-size:11px;color:var(--secondary)}\n\n#preview-indicator{display:none}\n@media(max-width:899px){#preview-indicator:not([hidden]){display:inline;white-space:nowrap}}\n\n/* 默认让原页在上方、中文译文在下方，原文对照继续使用原来的排布和语言选择 */\n.source-view-actions{display:flex;align-items:center;gap:8px;flex:none}\n.source-view-actions .text-action{font-size:12px;white-space:nowrap}\n.source-translation-empty{display:none}\n#demo-original[data-source-view=page-translation] .source-content{grid-template-rows:auto minmax(270px,var(--source-upper-fr,1fr)) 12px minmax(120px,1fr)}\n#demo-original[data-source-view=page-translation] #source-text-scroll{min-height:120px;padding-top:12px}\n#demo-original[data-source-view=page-translation] .source-question-choice label{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}\n#demo-original[data-source-view=page-translation] .locator-sources{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:thin;flex-shrink:0}\n#demo-original[data-source-view=page-translation] .locator-sources button{flex:none}\n#demo-original[data-source-view=page-translation] .source-original{display:none}\n#demo-original[data-source-view=page-translation] .source-translation{display:block}\n#demo-original[data-source-view=page-translation] [data-reading-language=zh] .source-original.source-single-language{display:block}\n#demo-original[data-source-view=page-translation] .source-text-label,\n#demo-original[data-source-view=page-translation] .demo-source-figure,\n#demo-original[data-source-view=page-translation] .source-attachment{display:none}\n#demo-original[data-source-view=page-translation] .source-translation-empty{display:block}\n@media(pointer:coarse){.source-view-actions .text-action{min-height:44px}#demo-original[data-source-view=page-translation] .source-content{grid-template-rows:auto minmax(300px,var(--source-upper-fr,1fr)) 20px minmax(120px,1fr)}}\n\n/* 将选择与定位工具收成紧凑行，把省出的高度留给原件与译文 */\n.visually-hidden{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip-path:inset(50%)!important;white-space:nowrap!important;border:0!important}\n.reader-ui .demo-masthead{height:56px;min-height:56px;padding-block:4px}\n.reader-ui .pane-head{height:40px;min-height:40px;padding-block:2px}\n.reader-ui .pane-sticky-tools{top:40px;padding-block:6px}\n#demo-original{container-type:inline-size;container-name:material}\n.reader-ui #demo-original .material-heading{height:36px;min-height:36px;gap:6px;padding:2px 8px}\n.material-heading h2{white-space:nowrap;flex:none}\n#demo-original .locator-sources{display:block;min-width:70px;max-width:140px;flex:1;min-height:0;margin:0;overflow:visible}\n.reader-ui #locator-source-select{width:100%;min-width:0;height:26px;min-height:26px;font-size:11px;padding:1px 3px;border-color:var(--line);background:transparent}\n.source-view-actions{gap:3px}\n.reader-ui #demo-original .source-view-actions .icon-button{width:26px;height:28px;min-height:28px;padding:5px}\n.reader-ui #demo-original .source-view-actions .text-action{min-height:28px;font-size:11px}\n.source-question-choice{display:flex;align-items:center;gap:6px;padding:4px 8px}\n.reader-ui #source-unit-select{flex:1;min-width:0;width:0;height:28px;min-height:28px;padding:2px 4px;font-size:11px;border-color:var(--line)}\n#source-language-tools{flex:none}\n.reader-ui #source-language-select{height:28px;min-height:28px;font-size:11px;max-width:90px;padding:2px 3px;border-color:var(--line)}\n#demo-original .source-content{grid-template-rows:auto minmax(80px,var(--source-upper-fr,1fr)) 12px minmax(200px,1fr);padding:0;min-height:350px}\n#demo-original[data-source-view=page-translation] .source-content{grid-template-rows:auto minmax(200px,var(--source-upper-fr,1fr)) 12px minmax(120px,1fr)}\n#demo-original[data-source-view=page-translation] #source-text-scroll{padding-top:4px}\n#demo-original #source-locator{min-height:200px}\n.reader-ui #demo-original .locator-heading{height:34px;min-height:34px;padding:2px 6px;gap:3px;justify-content:flex-start}\n.reader-ui #locator-view-select,.reader-ui #locator-sentence-select{height:26px;min-height:26px;font-size:11px;border-color:transparent;background:transparent;padding:1px 2px}\n.reader-ui #locator-view-select{flex:1;min-width:64px;max-width:100px}\n#demo-original .locator-sentence-navigation{display:flex;gap:0;align-items:center;margin:0;flex:none}\n.reader-ui #locator-sentence-select{width:52px;min-width:52px}\n#demo-original .locator-head-actions{gap:0;margin-left:auto}\n.reader-ui #demo-original .locator-heading .icon-button{width:24px;height:28px;min-height:28px;padding:5px}\n.reader-ui #demo-original .locator-heading .icon-button svg{width:15px;height:15px}\n.reader-ui #demo-original .locator-heading .zoom-reset{width:34px;min-width:34px;height:28px;min-height:28px}\n#demo-original .locator-body{padding:4px 6px;gap:0}\n.reader-ui #source-text-scroll .demo-source-card{padding:6px 0 12px}\n@container material (max-width:380px){.reader-ui #demo-original .locator-heading{flex-wrap:wrap;height:auto}.reader-ui #locator-view-select{max-width:none}#demo-original .locator-head-actions{width:100%;justify-content:flex-end}.material-heading h2{max-width:62px;overflow:hidden;text-overflow:ellipsis}}\n@container material (max-width:300px){.material-heading h2{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}}\n@media(max-width:899px){.reader-ui .demo-masthead{height:52px;min-height:52px}.reader-ui .demo-reading-pane.ui-drawer{top:60px}#drawer-backdrop{inset:52px 0 32px}}\n@media(pointer:coarse){.reader-ui #demo-original .locator-heading .icon-button{width:32px;height:36px;min-height:36px}.reader-ui #demo-original .locator-heading{height:40px;min-height:40px}.reader-ui #demo-original .locator-heading .zoom-reset{height:36px;min-height:36px}.reader-ui #locator-view-select,.reader-ui #locator-sentence-select,.reader-ui #source-unit-select,.reader-ui #source-language-select,.reader-ui #locator-source-select{min-height:32px;height:32px}#demo-original .source-content{grid-template-rows:auto minmax(80px,var(--source-upper-fr,1fr)) 20px minmax(220px,1fr);min-height:380px}#demo-original[data-source-view=page-translation] .source-content{grid-template-rows:auto minmax(220px,var(--source-upper-fr,1fr)) 20px minmax(120px,1fr)}#demo-original #source-locator{min-height:220px}.reader-ui #demo-original .material-heading{height:40px;min-height:40px}}\n@media(pointer:coarse){@container material (max-width:380px){.reader-ui #demo-original .locator-heading{height:auto}}}\n\n/* 原件周围保留拖动空间，缩放使用原件比例，适配按钮只计算一次 */\n.locator-stage{position:relative;box-sizing:content-box;min-height:0}\n.locator-viewport{cursor:grab;touch-action:none}\n.reader-ui .locator-zoom-select{width:58px;min-width:58px;height:28px;min-height:28px;padding:1px 2px;border-color:transparent;background:transparent;font-size:11px}\n@media(pointer:coarse){.reader-ui .locator-zoom-select{height:36px;min-height:36px}@container material (max-width:440px){.reader-ui #demo-original .locator-heading{height:auto;flex-wrap:wrap}#demo-original .locator-head-actions{width:100%;justify-content:flex-end}}}\n";
const TEMPLATE="\n<a class=\"skip-link\" href=\"#demo-content\">直接阅读讲解</a>\n<header class=\"demo-masthead\">\n  <div class=\"document-heading\"><span class=\"book-symbol\" data-icon=\"book\"></span><div class=\"document-name\"><p class=\"eyebrow\">对照原材料阅读 <span id=\"delivery-status\" class=\"edition-label\" hidden>完整稿预览 · 审查待完成</span></p><h1 id=\"demo-title\" tabindex=\"0\">正在读取正文</h1></div></div>\n  <div class=\"demo-header-actions\" aria-label=\"调整阅读布局\">\n    <div class=\"control-group\" role=\"group\" aria-label=\"选择显示的面板\">\n      <button class=\"icon-button\" data-toggle-pane=\"directory\" data-icon=\"directory\" aria-label=\"隐藏目录\" data-tooltip=\"显示或隐藏目录\" aria-pressed=\"true\"></button>\n      <button class=\"icon-button\" data-toggle-pane=\"source\" data-icon=\"source\" aria-label=\"隐藏原文与译文\" data-tooltip=\"显示或隐藏原文\" aria-pressed=\"true\"></button>\n      <button class=\"icon-button\" data-toggle-pane=\"glossary\" data-icon=\"glossary\" aria-label=\"隐藏术语表\" data-tooltip=\"显示或隐藏术语表\" aria-pressed=\"true\"></button>\n    </div>\n    <div class=\"control-group\"><button id=\"focus-reading\" class=\"icon-button\" data-icon=\"focus\" aria-label=\"进入专注阅读\" data-tooltip=\"专注阅读\" aria-pressed=\"false\"></button><button id=\"toggle-theme\" class=\"icon-button\" data-icon=\"moon\" aria-label=\"切换深色主题\" data-tooltip=\"切换明暗主题\"></button><button id=\"open-settings\" class=\"icon-button\" data-icon=\"settings\" aria-label=\"打开阅读设置\" data-tooltip=\"阅读设置\" aria-haspopup=\"dialog\"></button></div>\n  </div>\n</header>\n<nav id=\"demo-pane-tabs\" class=\"demo-pane-tabs\" aria-label=\"选择阅读面板\" hidden><button data-open-pane=\"directory\">目录</button><button data-open-pane=\"source\">原文与译文</button><button data-open-pane=\"lesson\" aria-pressed=\"true\">讲解</button><button data-open-pane=\"glossary\">术语表</button></nav>\n<div class=\"demo-shell\" id=\"reader-shell\">\n  <aside id=\"demo-directory\" class=\"demo-directory demo-reading-pane\" data-pane=\"directory\" aria-labelledby=\"demo-directory-title\" hidden>\n    <div class=\"pane-head\"><h2 id=\"demo-directory-title\">目录</h2><button class=\"icon-button\" data-close-pane=\"directory\" data-icon=\"close\" aria-label=\"收起目录\" data-tooltip=\"收起目录\"></button></div>\n    <div class=\"directory-context\"><span>当前小节</span><p id=\"current-section-context\">正在读取本节目录</p></div>\n    <h3 id=\"book-title\" class=\"book-directory-title\">正在读取全书目录</h3><nav id=\"book-toc\" aria-label=\"全书目录\"></nav><nav id=\"demo-outline\" aria-label=\"本节目录\"></nav>\n    <details id=\"coverage-details\" class=\"coverage-details debug-only\" hidden><summary id=\"coverage-summary\">查看资料讲解覆盖</summary><div id=\"coverage-items\"></div></details>\n    <details class=\"demo-tools debug-only\"><summary>查看数据与检查记录</summary><div class=\"downloads\"><a id=\"writing-plan\" target=\"_blank\">查看本节承接计划</a><a id=\"demo-json\" href=\"/05_writing/demo.json\" target=\"_blank\">查看本节 JSON</a><a href=\"/05_writing/structure.md\" target=\"_blank\">查看写作结构</a><a href=\"/05_writing/terminology.rules.md\" target=\"_blank\">查看术语规则</a></div><details id=\"book-overview\"><summary>查看书与章的整体问题</summary></details><a id=\"book-grounding-report\" target=\"_blank\" hidden>查看全书信息点检查</a><label class=\"role-toggle\"><input type=\"checkbox\" id=\"show-roles\">显示段落角色</label></details>\n    <p class=\"directory-footnote\">读完一个问题后，可以在讲解下方写下自己的理解</p>\n  </aside>\n  <aside id=\"demo-original\" class=\"demo-original demo-reading-pane\" data-pane=\"source\" data-language=\"both\" data-source-view=\"page-translation\" aria-labelledby=\"demo-original-title\" hidden>\n    <div class=\"pane-head material-heading\">\n      <h2 id=\"demo-original-title\">原页与译文</h2>\n      <div id=\"locator-sources\" class=\"locator-sources\"><select id=\"locator-source-select\" aria-label=\"选择要定位的材料\"></select></div>\n      <div class=\"source-view-actions\"><div id=\"source-preview-controls\" hidden><span id=\"source-preview-caption\" class=\"visually-hidden\" role=\"status\"></span><button id=\"source-preview-back\" class=\"icon-button\" data-icon=\"reset\" aria-label=\"返回全部对应材料\" data-tooltip=\"返回全部对应材料\"></button></div><button id=\"source-view-toggle\" class=\"text-action\" aria-pressed=\"true\" aria-label=\"切换到原文与译文对照模式\">原文对照</button><button class=\"icon-button\" data-close-pane=\"source\" data-icon=\"close\" aria-label=\"收起原文与译文\" data-tooltip=\"收起材料栏\"></button></div>\n    </div>\n    <div class=\"pane-content source-content\">\n      <div class=\"source-question-choice\"><label class=\"visually-hidden\" for=\"source-unit-select\">对照哪个问题的材料</label><select id=\"source-unit-select\"></select><div id=\"source-language-tools\" hidden><select id=\"source-language-select\" aria-label=\"选择原文显示语言\"><option value=\"zh\">中文</option><option value=\"en\">英文</option><option value=\"both\">中英对照</option></select></div></div>\n      <div id=\"source-text-scroll\"><p id=\"source-context\" class=\"help debug-only\"></p><div id=\"source-cards\"></div></div>\n      <div id=\"source-splitter\" class=\"source-splitter\" role=\"separator\" aria-label=\"调整原文译文与原文定位的上下比例\" aria-orientation=\"horizontal\" aria-controls=\"source-text-scroll source-locator\" aria-valuemin=\"15\" aria-valuemax=\"75\" aria-valuenow=\"55\" tabindex=\"0\" data-tooltip=\"拖动调整上下比例，双击恢复默认，也可以按上下方向键\"></div>\n      <section id=\"source-locator\" aria-labelledby=\"source-locator-title\">\n        <div class=\"pane-head locator-heading\">\n          <h2 id=\"source-locator-title\" class=\"visually-hidden\">原文定位</h2>\n          <select id=\"locator-view-select\" aria-label=\"选择原件视图\"><option value=\"highlight\">高亮区域</option><option value=\"page\">完整原页</option></select>\n          <div id=\"locator-sentence-navigation\" class=\"locator-sentence-navigation\" hidden><button id=\"locator-previous-sentence\" class=\"icon-button\" data-icon=\"previous\" aria-label=\"定位上一句\" data-tooltip=\"上一句\"></button><select id=\"locator-sentence-select\" aria-label=\"选择要定位的句子\"></select><span id=\"locator-sentence-label\" class=\"visually-hidden\" aria-live=\"polite\"></span><button id=\"locator-next-sentence\" class=\"icon-button\" data-icon=\"next\" aria-label=\"定位下一句\" data-tooltip=\"下一句\"></button></div>\n          <div class=\"locator-head-actions\"><div class=\"locator-zoom-controls\" role=\"group\" aria-label=\"调整原文定位缩放\"><button class=\"icon-button\" data-locator-zoom=\"out\" data-icon=\"minus\" aria-label=\"缩小原文定位\" data-tooltip=\"缩小\"></button><select class=\"locator-zoom-select\" data-locator-zoom-select aria-label=\"设置原件缩放比例\"><option value=\"100\">100%</option></select><button class=\"zoom-reset\" data-locator-fit aria-label=\"适配当前定位范围\" data-tooltip=\"适配一次，随后保留该缩放\">适配</button><button class=\"icon-button\" data-locator-zoom=\"in\" data-icon=\"plus\" aria-label=\"放大原文定位内容\" data-tooltip=\"放大\"></button></div><button id=\"locator-recenter\" class=\"icon-button\" data-icon=\"target\" aria-label=\"回到高亮\" data-tooltip=\"回到高亮\"></button><button id=\"locator-expand\" class=\"icon-button\" data-icon=\"expand\" aria-label=\"放大原文定位\" data-tooltip=\"打开大图查看\"></button></div>\n        </div>\n        <div class=\"locator-body\"><div id=\"locator-surface\" class=\"locator-surface\"><div id=\"locator-viewport\" class=\"locator-viewport\" tabindex=\"0\" aria-label=\"原页中高亮的材料位置\"><div id=\"locator-stage\" class=\"locator-stage\"><div id=\"locator-page\" class=\"locator-page\"><img id=\"locator-image\" alt=\"已保存的原始页面\"><div id=\"locator-highlights\"></div></div></div></div><iframe id=\"locator-dom\" title=\"原网页 DOM 中高亮的材料\" sandbox=\"allow-same-origin\" hidden></iframe></div><p id=\"locator-status\" class=\"debug-only\" role=\"status\">正在读取原页位置</p></div>\n      </section>\n    </div>\n  </aside>\n  <main class=\"demo-explanation demo-reading-pane\" data-pane=\"lesson\" aria-label=\"讲解\">\n    <div class=\"pane-head lesson-head\"><h2>讲解</h2><span id=\"reading-location\"></span></div>\n    <div class=\"lesson-content\"><article id=\"demo-content\"></article><nav id=\"book-navigation\" aria-label=\"前后小节\"></nav><footer id=\"next-section\"></footer></div>\n  </main>\n  <aside id=\"glossary-result\" class=\"demo-terms demo-reading-pane\" data-pane=\"glossary\" aria-labelledby=\"demo-glossary-title\" hidden>\n    <div class=\"pane-head\"><h2 id=\"demo-glossary-title\">术语表</h2><button class=\"icon-button\" data-close-pane=\"glossary\" data-icon=\"close\" aria-label=\"收起术语表\" data-tooltip=\"收起术语表\"></button></div>\n    <div class=\"pane-sticky-tools glossary-search-wrap\"><span data-icon=\"search\"></span><input id=\"glossary-search\" type=\"search\" placeholder=\"搜索术语\" aria-label=\"搜索本节术语\"></div>\n    <div class=\"pane-content\"><p id=\"glossary-count\" class=\"help\"></p><div id=\"glossary-preview-controls\" hidden><p id=\"glossary-preview-caption\" class=\"help\" role=\"status\"></p><button id=\"glossary-preview-back\" class=\"text-action\">返回全部术语</button></div><details class=\"demo-tools debug-only\"><summary>查看术语记录</summary><a id=\"term-report\" target=\"_blank\">查看术语出现位置</a></details><div id=\"glossary-list\"></div></div>\n  </aside>\n  <div class=\"resizer\" data-resize-pane=\"directory\" role=\"separator\" aria-label=\"调整目录宽度\" aria-orientation=\"vertical\" tabindex=\"0\"></div>\n  <div class=\"resizer\" data-resize-pane=\"source\" role=\"separator\" aria-label=\"调整原文宽度\" aria-orientation=\"vertical\" tabindex=\"0\"></div>\n  <div class=\"resizer\" data-resize-pane=\"glossary\" role=\"separator\" aria-label=\"调整术语表宽度\" aria-orientation=\"vertical\" tabindex=\"0\"></div>\n</div>\n<footer class=\"workspace-footer\"><span id=\"ui-status\" role=\"status\">正在读取正文</span><span id=\"layout-status\"></span><span id=\"preview-indicator\" class=\"draft-status\" hidden>待审预览</span><span class=\"debug-only\" id=\"demo-status\" role=\"status\"></span><label class=\"debug-toggle\"><input id=\"show-debug\" type=\"checkbox\">Debug</label></footer>\n<div id=\"drawer-backdrop\" hidden></div>\n<dialog id=\"reading-settings\" aria-labelledby=\"settings-title\">\n  <form method=\"dialog\"><header><h2 id=\"settings-title\">阅读设置</h2><button class=\"icon-button\" value=\"cancel\" data-icon=\"close\" aria-label=\"关闭阅读设置\"></button></header><div class=\"settings-content\"><label for=\"body-size\">正文字号 <output id=\"body-size-value\">17 px</output></label><input id=\"body-size\" type=\"range\" min=\"16\" max=\"21\" step=\"1\"><label for=\"line-height\">正文行距 <output id=\"line-height-value\">1.95</output></label><input id=\"line-height\" type=\"range\" min=\"1.65\" max=\"2.2\" step=\"0.05\"><p>拖动面板之间的分隔条可以调宽，聚焦分隔条后也可以按左右方向键</p><p>设置和笔记保存在当前浏览器，切换页面后仍可读取</p></div><footer><button type=\"button\" id=\"reset-layout\" class=\"secondary\">恢复默认布局</button><button value=\"close\">完成</button></footer></form>\n</dialog>\n<dialog id=\"image-viewer\" aria-label=\"查看完整原图\"><button class=\"icon-button image-close\" data-icon=\"close\" aria-label=\"关闭原图\"></button><div id=\"image-stage\"></div></dialog>\n<dialog id=\"locator-dialog\" aria-labelledby=\"locator-dialog-title\"><header><h2 id=\"locator-dialog-title\">原文定位</h2><div class=\"locator-head-actions\"><div class=\"locator-zoom-controls\" role=\"group\" aria-label=\"调整原文定位缩放\"><button class=\"icon-button\" data-locator-zoom=\"out\" data-icon=\"minus\" aria-label=\"缩小原文定位\" data-tooltip=\"缩小\"></button><select class=\"locator-zoom-select\" data-locator-zoom-select aria-label=\"设置原件缩放比例\"><option value=\"100\">100%</option></select><button class=\"zoom-reset\" data-locator-fit aria-label=\"适配当前定位范围\" data-tooltip=\"适配一次，随后保留该缩放\">适配</button><button class=\"icon-button\" data-locator-zoom=\"in\" data-icon=\"plus\" aria-label=\"放大原文定位内容\" data-tooltip=\"放大\"></button></div><button id=\"locator-dialog-close\" class=\"icon-button\" data-icon=\"close\" aria-label=\"关闭原文定位\"></button></div></header><div id=\"locator-dialog-content\"></div></dialog>\n<div id=\"ui-tooltip\" role=\"tooltip\" hidden></div>\n\n";
// This module mounts one independent reading view per container
export function mountReader(container, options) {
  const shadow = container.shadowRoot || container.attachShadow({mode:'open'});
  const style = globalThis.document.createElement('style');
  const root = globalThis.document.createElement('div');
  root.className = 'lw-reader-root writing-page demo-page reader-ui book-page';
  root.lang='zh-CN'; root.dataset.theme='light';
  style.textContent=STYLES; root.innerHTML=TEMPLATE; shadow.replaceChildren(style,root);
  const abort=new AbortController(), timers=new Set(), frames=new Set(), observers=new Set(); let disposed=false;
  const native=globalThis.window;
  const tracked=kind=>class extends native[kind] {constructor(...args){super(...args);observers.add(this)}disconnect(){super.disconnect();observers.delete(this)}};
  const MutationObserver=tracked('MutationObserver'), ResizeObserver=tracked('ResizeObserver'), IntersectionObserver=tracked('IntersectionObserver');
  const config={project_id:options.projectId,base:options.base,readweave_demo:true,legacy:!!options.legacy};
  const path=value=>{let text=String(value||'');if(/^(https?:|data:|blob:|#)/.test(text))return text;if(text.startsWith(config.base+'/'))return text;if(text.startsWith('/book.html')||text.startsWith('book.html'))text=text.replace('book.html','readweave.html');return config.base+'/'+text.replace(/^\/+/,'')};
  const fetch=(value, init)=>options.fetch?options.fetch(value,init):native.fetch(typeof value==='string'&&/^\/(0[0-5]_)/.test(value)?path(value):value,init);
  const location={pathname:'readweave/book.html',search:options.search||'?preview=true',hash:''};
  const owned={LESSONWEAVE:config,LWPath:path};
  const listen=(target,type,handler,settings={})=>target.addEventListener(type,handler,{...(typeof settings==='boolean'?{capture:settings}:settings),signal:abort.signal});
  const document=new Proxy(native.document,{get(target,key){
    if(key==='body'||key==='documentElement')return root;
    if(key==='getElementById')return id=>root.querySelector('#'+CSS.escape(id));
    if(key==='querySelector'||key==='querySelectorAll')return root[key].bind(root);
    if(key==='addEventListener')return (type,handler,settings)=>listen(root,type,handler,settings);
    if(key==='dispatchEvent')return root.dispatchEvent.bind(root);
    const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});
  const window=new Proxy(native,{get(target,key){
    if(key in owned)return owned[key];if(key==='document')return document;if(key==='location')return location;
    if(key==='innerWidth')return container.clientWidth;if(key==='innerHeight')return container.clientHeight;
    if(key==='addEventListener')return (type,handler,settings)=>listen(target,type,handler,settings);
    const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  },set(target,key,value){owned[key]=value;return true}});
  const setTimeout=(callback,delay,...args)=>{const id=native.setTimeout(()=>{timers.delete(id);if(!disposed)callback(...args)},delay);timers.add(id);return id};
  const clearTimeout=id=>{timers.delete(id);native.clearTimeout(id)};
  const requestAnimationFrame=callback=>{const id=native.requestAnimationFrame(time=>{frames.delete(id);if(!disposed)callback(time)});frames.add(id);return id};
  const cancelAnimationFrame=id=>{frames.delete(id);native.cancelAnimationFrame(id)};
  const setInterval=(callback,delay)=>{const id=native.setInterval(()=>{if(!disposed)callback()},delay);timers.add(id);return id};
  const clearInterval=id=>{timers.delete(id);native.clearInterval(id)};
// 工具栏只使用这一组 24×24 线性图标，颜色与线宽由统一样式控制
const drawings = {
  book: '<path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4z"/><path d="M20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-3h3z"/>',
  directory: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m4-11h4m-4 5h4"/>',
  source: '<path d="M8 4H4v16h4m8-16h4v16h-4M10 9l-3 3 3 3m4-6 3 3-3 3"/>',
  glossary: '<path d="M4 5h8v14H4zM12 5h8v14h-8M7 9h2m-2 4h2m6-4h2m-2 4h2"/>',
  focus: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M8 8h8v8H8z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  moon: '<path d="M20 15a8.5 8.5 0 0 1-11-11 8.5 8.5 0 1 0 11 11Z"/>',
  settings: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  reset: '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
  minus: '<path d="M5 12h14"/>',
  plus: '<path d="M5 12h14M12 5v14"/>',
  expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  previous: '<path d="m14 6-6 6 6 6"/>',
  next: '<path d="m10 6 6 6-6 6"/>',
  target: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>'
};
window.uiIcon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${drawings[name] || drawings.book}</svg>`;

const uiIcon=window.uiIcon;
/* 每个问题完整讲完后提供一个笔记框，原材料与覆盖记录按当前样稿版本读取 */
(() => {
  const get = id => document.getElementById(id);
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
    if (!hasChineseReading) {
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
    toc.append(opening, make('p', '核心问题', 'demo-outline-label'));
    for (const unit of data.units) {
      const button = make('button', unit.number + ' ' + unit.title, 'demo-outline-question');
      button.type = 'button';
      button.dataset.outlineQuestion = unit.question_id;
      button.onclick = () => {
        chooseQuestion(unit.question_id, true);
        focusBlock(unit.problem.id);
      };
      toc.append(button);
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
      if (!Array.isArray(sourcePack.sources) || !Array.isArray(explanationCoverage.items)) throw new Error('材料版本正在准备');
      originalSourcePack = sourcePack;
      sourcePack = { ...sourcePack, sources: mergeSourceViews(sourcePack.sources) };
      sourceLinks = { ...(explanationCoverage.block_sources || {}) };
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
      document.body.classList.add('grounded-demo');
      get('demo-original').hidden = false;
      get('demo-pane-tabs').hidden = false;
      openPane('lesson');
      document.querySelectorAll('[data-open-pane]').forEach(button => {
        button.onclick = () => openPane(button.dataset.openPane);
      });
      const select = get('source-unit-select');
      for (const unit of data.units) {
        const option = make('option', unit.number + ' ' + unit.title);
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
    if (!isBook) return;
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
    const label = make('label', '读完 ' + number + ' 后，我怎样理解这个问题');
    const input = make('textarea');
    input.rows = 3;
    input.setAttribute('aria-label', number + ' 的理解');
    label.append(input);
    const key = (window.LESSONWEAVE && !window.LESSONWEAVE.legacy ? 'lessonweave:' + window.LESSONWEAVE.project_id + ':' : '') + 'infiniteqa:note:' + data.transitions_path + ':' + data.section_id + ':' + id;
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

  function block(b, role) {
    const box = make('div', undefined, 'writing-block');
    box.dataset.blockId = b.id;
    box.id = 'block-' + b.id;
    if (role) box.append(make('span', role, 'writing-role'));
    if (b.kind === 'paragraph') {
      box.append(make('p', b.text));
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
        radio.onchange = () => { selected = i; };
        label.append(radio, document.createTextNode(String.fromCharCode(65 + i) + ' · ' + option));
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
        answer.append(make('p', selected === q.answer ? '回答正确' : '再想一下，正确选项是 ' + String.fromCharCode(65 + q.answer)));
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
      prose.append(make('p', term.definition));
      term.explanation.forEach(text => prose.append(make('p', text)));
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
      acceptNode: node => node.parentElement.closest('a,button,pre,code,input,textarea,.writing-role,.writing-note,.inline-term') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
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
      if (location.pathname.endsWith('book.html')) {
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
          group.append(make('summary', chapter.number + ' ' + chapter.title));
          const list = make('ul');
          for (const section of chapter.sections) {
            const item = make('li');
            const link = make('a', section.number + ' ' + section.title);
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
      documentPath = sectionPath;
      isPreview = isPreview || data.preview === true;
      if (!data.validation?.passed && !isPreview) throw new Error('样稿尚未通过检查');
      document.body.classList.toggle('draft-preview', isPreview);
      const previewStatus = get('delivery-status');
      if (previewStatus) {
        previewStatus.hidden = !isPreview;
        previewStatus.textContent = '完整稿预览 · ' + (data.validation?.passed ? '本节检查通过' : '审查待完成');
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
      get('demo-title').textContent = data.section_number + ' ' + data.title;
      get('demo-status').textContent = `${isPreview ? '完整稿预览' : book ? '05 完整正文' : '05 最小样稿'} · ${data.core_questions.length} 个核心问题 · ${data.quiz.length} 道练习 · ${data.glossary.length} 个术语`;
      const article = get('demo-content');
      article.replaceChildren();
      const opening = make('section', undefined, 'writing-opening');
      const openingHeading = make('h2', undefined, 'writing-opening-title');
      openingHeading.textContent = '承上启下';
      opening.append(openingHeading, make('p', data.opening_title, 'writing-opening-question'), block(data.opening, '承上段'));
      if (data.opening_forward) opening.append(block(data.opening_forward, '启下段'));
      article.append(opening);
      const cores = make('ul', undefined, 'writing-core-questions');
      cores.setAttribute('aria-label', '本节核心问题');
      data.core_questions.forEach(q => cores.append(make('li', q.text)));
      article.append(make('h2', '核心问题'), cores, make('h2', '内容讲解'));
      data.units.forEach(u => {
        const unit = make('section', undefined, 'writing-unit');
        unit.dataset.unitQuestion = u.question_id;
        unit.append(make('h3', u.number + ' ' + u.title, 'writing-unit-title'), block(u.problem, '问题段'));
        u.explanation.forEach(b => unit.append(block(b, '讲解段')));
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
        part.append(make('h3', p.premise + p.question), block(p.body));
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


// 布局和外观沿用已确认的 UI-04，正文、来源和笔记继续读取当前案例
(() => {
  const $ = id => document.getElementById(id);
  const names = {directory:'目录',source:'原文与译文',glossary:'术语表'};
  const panes = Object.fromEntries([...document.querySelectorAll('[data-pane]')].map(el=>[el.dataset.pane,el]));
  const defaults = {version:1,theme:'light',widths:{directory:224,source:420,glossary:272},visible:{directory:true,source:true,glossary:true},body:17,line:1.95,focus:false};
  const key = 'aialra:reader-ui:v1';
  let state = structuredClone(defaults), tokens, current = {}, drawer = null, trigger = null, dragging = null, initialized = false, frame = 0;
  let tooltipTimer, peekOpenTimer, peekCloseTimer, peekTarget = null, pinnedDrawer = false, restoringDrawerFocus=false;
  try { const old=JSON.parse(localStorage.getItem(key)); if(old?.version===1) state={...state,...old,widths:{...state.widths,...old.widths},visible:{...state.visible,...old.visible}}; } catch {}
  for(const name of Object.keys(names)) state.widths[name]=Math.max(180,Math.min(name==='source'?840:560,Number(state.widths[name])||defaults.widths[name]));
  state.body=Math.max(16,Math.min(21,Number(state.body)||17));
  state.line=Math.max(1.65,Math.min(2.2,Number(state.line)||1.95));
  state.focus=false;
  document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=uiIcon(el.dataset.icon));
  function message(text){$('ui-status').textContent=text;}
  function save(){try{localStorage.setItem(key,JSON.stringify(state));message('布局已保存到此浏览器')}catch{message('当前设置保留在本次会话中，浏览器存储写入失败')}}
  function theme(){
    const name=state.theme==='dark'?'dark':'light';document.documentElement.dataset.theme=name;
    for(const [role,value] of Object.entries(tokens?.[name]||{})) document.documentElement.style.setProperty('--'+role.replace(/[A-Z]/g,c=>'-'+c.toLowerCase()),value);
    $('toggle-theme').innerHTML=uiIcon(name==='dark'?'sun':'moon');$('toggle-theme').setAttribute('aria-label',name==='dark'?'切换浅色主题':'切换深色主题');
    document.documentElement.style.setProperty('--body-size',state.body+'px');document.documentElement.style.setProperty('--body-line',state.line);
    $('body-size').value=state.body;$('body-size-value').value=state.body+' px';$('line-height').value=state.line;$('line-height-value').value=state.line.toFixed(2);
  }
  function queueLayout(){cancelAnimationFrame(frame);frame=requestAnimationFrame(layout);}
  function layout(){
    const available=$('reader-shell').clientWidth;current={...state.visible};
    if(state.focus||innerWidth<900) Object.keys(current).forEach(p=>current[p]=false);
    const budget=()=>Object.entries(current).reduce((n,[p,on])=>n+(on?state.widths[p]+16:0),0)+560;
    for(const p of ['directory','glossary','source'])if(budget()>available)current[p]=false;
    const cols=[];
    for(const p of ['directory','source'])if(current[p])cols.push(state.widths[p]+'px');
    cols.push('minmax(0,1fr)');if(current.glossary)cols.push(state.widths.glossary+'px');
    $('reader-shell').style.setProperty('--columns',cols.join(' '));
    for(const [p,el]of Object.entries(panes)) el.dataset.uiVisible=p==='lesson'||!!current[p];
    for(const button of document.querySelectorAll('[data-toggle-pane]')){
      const p=button.dataset.togglePane;const visible=!!current[p]||drawer===p;
      button.setAttribute('aria-pressed',visible);button.setAttribute('aria-label',(visible?'隐藏':'打开')+names[p]);
    }
    $('focus-reading').setAttribute('aria-pressed',state.focus);$('focus-reading').setAttribute('aria-label',state.focus?'恢复对照阅读':'进入专注阅读');
    $('layout-status').textContent=state.focus?'专注阅读':`${1+Object.values(current).filter(Boolean).length} 栏阅读`;
    positionResizers();
  }
  function positionResizers(){
    const base=$('reader-shell').getBoundingClientRect();
    for(const el of document.querySelectorAll('[data-resize-pane]')){
      const p=el.dataset.resizePane;el.hidden=!current[p]||!!drawer;
      if(el.hidden)continue;const r=panes[p].getBoundingClientRect();
      el.style.left=(p==='glossary'?r.left-base.left-14:r.right-base.left+2)+'px';
      el.setAttribute('aria-valuemin',p==='directory'?180:240);el.setAttribute('aria-valuemax',Math.floor(maxWidth(p)));el.setAttribute('aria-valuenow',Math.round(r.width));
    }
  }
  function maxWidth(p){
    const others=Object.entries(current).reduce((n,[name,on])=>n+(on&&name!==p?state.widths[name]+16:0),0);
    return Math.min(p==='source'?840:600,$('reader-shell').clientWidth-others-16-560);
  }
  function closeDrawer(restore=true){
    clearTimeout(peekOpenTimer);clearTimeout(peekCloseTimer);peekTarget=null;
    if(!drawer)return;const p=drawer;panes[p].classList.remove('ui-drawer');panes[p].removeAttribute('role');panes[p].removeAttribute('aria-modal');
    drawer=null;pinnedDrawer=false;$('drawer-backdrop').hidden=true;
    for(const el of [...Object.values(panes),document.querySelector('.demo-masthead')])el.inert=false;
    layout();const returnTo=trigger;trigger=null;if(restore&&returnTo?.isConnected){restoringDrawerFocus=true;returnTo.focus({preventScroll:true});restoringDrawerFocus=false;}
    document.dispatchEvent(new CustomEvent('reading:clear-preview',{detail:{pane:p}}));
  }
  function openDrawer(p,modal=false,source=null){
    if(current[p])return;
    if(drawer&&drawer!==p)closeDrawer(false);
    const wasPinned=drawer===p&&pinnedDrawer;
    drawer=p;pinnedDrawer=modal||wasPinned;trigger=source||trigger;
    panes[p].classList.add('ui-drawer');
    if(modal){
      $('drawer-backdrop').hidden=false;panes[p].setAttribute('role','dialog');panes[p].setAttribute('aria-modal','true');
      for(const [name,el] of Object.entries(panes))el.inert=name!==p;
      document.querySelector('.demo-masthead').inert=true;
      (panes[p].querySelector('button,input,select,a')||panes[p]).focus({preventScroll:true});
    }
    layout();
  }
  document.querySelectorAll('[data-toggle-pane]').forEach(button=>button.addEventListener('click',()=>{
    const p=button.dataset.togglePane;
    if(drawer===p){closeDrawer();return;}
    if(current[p]){state.visible[p]=false;layout();save();return;}
    if(!state.visible[p]){state.visible[p]=true;layout();save();if(current[p])return;}
    openDrawer(p,true,button);
  }));
  document.querySelectorAll('[data-close-pane]').forEach(button=>button.addEventListener('click',()=>{
    const p=button.dataset.closePane;if(drawer===p)closeDrawer();else{state.visible[p]=false;layout();save();}
  }));
  $('drawer-backdrop').onclick=()=>closeDrawer();
  $('focus-reading').onclick=()=>{closeDrawer(false);state.focus=!state.focus;layout();save();};
  $('toggle-theme').onclick=()=>{state.theme=state.theme==='light'?'dark':'light';theme();save();};
  $('open-settings').onclick=()=>{$('ui-tooltip').hidden=true;$('reading-settings').showModal();$('body-size').focus();};
  $('reading-settings').addEventListener('close',()=>{$('open-settings').focus({preventScroll:true});save();});
  $('body-size').oninput=event=>{state.body=Number(event.target.value);theme();};
  $('line-height').oninput=event=>{state.line=Number(event.target.value);theme();};
  $('reset-layout').onclick=()=>{state={...structuredClone(defaults),theme:state.theme};closeDrawer(false);theme();layout();save();};
  // 拖动与方向键使用同一份宽度状态，取消拖动时恢复起点，完成后才保存
  for(const el of document.querySelectorAll('[data-resize-pane]')){
    const p=el.dataset.resizePane;
    el.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;el.setPointerCapture(event.pointerId);dragging={p,el,x:event.clientX,width:state.widths[p],saved:{...state.widths}};document.body.classList.add('is-resizing');event.preventDefault();
    });
    el.addEventListener('pointermove',event=>{if(dragging?.el!==el)return;const change=(event.clientX-dragging.x)*(p==='glossary'?-1:1);state.widths[p]=Math.round(Math.max(p==='directory'?180:240,Math.min(maxWidth(p),dragging.width+change)));queueLayout();});
    const finish=cancel=>{if(dragging?.el!==el)return;if(cancel)state.widths=dragging.saved;dragging=null;document.body.classList.remove('is-resizing');layout();if(!cancel)save();};
    el.addEventListener('pointerup',()=>finish(false));el.addEventListener('pointercancel',()=>finish(true));
    el.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const min=p==='directory'?180:240;let amount=(event.shiftKey?32:16)*(event.key==='ArrowRight'?1:-1)*(p==='glossary'?-1:1);state.widths[p]=event.key==='Home'?min:event.key==='End'?maxWidth(p):Math.max(min,Math.min(maxWidth(p),state.widths[p]+amount));layout();save();});
    el.addEventListener('dblclick',()=>{state.widths[p]=defaults.widths[p];layout();save();});
  }
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){
      if(dragging){state.widths=dragging.saved;dragging=null;document.body.classList.remove('is-resizing');layout();event.preventDefault();event.stopImmediatePropagation();return;}
      if(!$('ui-tooltip').hidden){$('ui-tooltip').hidden=true;event.preventDefault();event.stopImmediatePropagation();return;}
      if(drawer){closeDrawer();event.preventDefault();event.stopImmediatePropagation();}
    }
    if(event.key==='Tab'&&drawer&&pinnedDrawer){
      const els=[...panes[drawer].querySelectorAll('button,a[href],input,select,textarea,summary,[tabindex="0"]')].filter(el=>el.getClientRects().length&&!el.disabled);
      const first=els[0],last=els.at(-1);if(event.shiftKey&&document.activeElement===first){last.focus();event.preventDefault();}else if(!event.shiftKey&&document.activeElement===last){first.focus();event.preventDefault();}
    }
  },true);
  // 临时面板只响应有停留意图的鼠标，关闭计时只在回到对应入口或面板时取消
  const peekEntry=target=>target instanceof Element?target.closest('.inline-term,.source-marker'):null;
  const entryPane=el=>el?.classList.contains('inline-term')?'glossary':'source';
  function schedulePeekClose(){
    clearTimeout(peekCloseTimer);
    peekCloseTimer=setTimeout(()=>{
      if(!drawer||pinnedDrawer)return;
      const hovered=[...document.querySelectorAll('.inline-term:hover,.source-marker:hover')].some(el=>entryPane(el)===drawer);
      const focused=document.activeElement?.matches(':focus-visible')&&(panes[drawer].contains(document.activeElement)||peekEntry(document.activeElement)&&entryPane(document.activeElement)===drawer);
      if(!panes[drawer].matches(':hover')&&!hovered&&!focused)closeDrawer(false);
    },300);
  }
  document.addEventListener('pointerover',event=>{
    if(event.pointerType!=='mouse'||!matchMedia('(hover:hover) and (pointer:fine)').matches)return;
    const entry=peekEntry(event.target);
    if(drawer&&panes[drawer].contains(event.target)){clearTimeout(peekCloseTimer);return;}
    if(!entry)return;
    const p=entryPane(entry);if(current[p])return;
    if(entry.contains(event.relatedTarget))return;
    if(drawer===p)clearTimeout(peekCloseTimer);
    clearTimeout(peekOpenTimer);peekTarget=entry;
    peekOpenTimer=setTimeout(()=>{if(entry===peekTarget&&entry.matches(':hover')&&!pinnedDrawer)openDrawer(p,false,entry);},240);
  });
  document.addEventListener('pointerout',event=>{
    const entry=peekEntry(event.target);
    if(entry&&!entry.contains(event.relatedTarget)){clearTimeout(peekOpenTimer);peekTarget=null;}
    if(drawer)schedulePeekClose();
  });
  document.addEventListener('focusin',event=>{
    const entry=peekEntry(event.target);
    if(!restoringDrawerFocus&&entry&&entry.matches(':focus-visible')){clearTimeout(peekCloseTimer);openDrawer(entryPane(entry),false,entry);}
  });
  document.addEventListener('focusout',()=>{if(drawer)schedulePeekClose();});
  document.addEventListener('click',event=>{
    const entry=peekEntry(event.target);if(!entry)return;
    clearTimeout(peekOpenTimer);
    // 阅读器先更新查询内容，再把点击打开的窄屏面板保持为可明确关闭的对话框
    queueMicrotask(()=>openDrawer(entryPane(entry),true,entry));
  },true);
  const tooltip=$('ui-tooltip');
  function showTooltip(el){
    clearTimeout(tooltipTimer);const text=el.dataset.tooltip;if(!text)return;
    const host=el.closest('dialog[open]')||document.body;if(tooltip.parentElement!==host)host.append(tooltip);
    tooltip.textContent=text;tooltip.hidden=false;const r=el.getBoundingClientRect(),t=tooltip.getBoundingClientRect();
    tooltip.style.left=Math.max(8,Math.min(innerWidth-t.width-8,r.left))+'px';tooltip.style.top=Math.min(innerHeight-t.height-8,r.bottom+7)+'px';el.setAttribute('aria-describedby','ui-tooltip');
  }
  document.addEventListener('pointerover',event=>{const el=event.target.closest('[data-tooltip]');if(el)showTooltip(el);});
  document.addEventListener('focusin',event=>{const el=event.target.closest('[data-tooltip]');if(el&&el.matches(':focus-visible'))showTooltip(el);});
  function hideTooltip(){tooltipTimer=setTimeout(()=>{if(!tooltip.matches(':hover'))tooltip.hidden=true;},120);}
  document.addEventListener('pointerout',event=>{if(event.target.closest('[data-tooltip]'))hideTooltip();});
  document.addEventListener('focusout',hideTooltip);tooltip.onpointerenter=()=>clearTimeout(tooltipTimer);tooltip.onpointerleave=hideTooltip;
  document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('close',()=>{if(dialog.contains(tooltip)){tooltip.hidden=true;document.body.append(tooltip);}}));
  document.addEventListener('click',event=>{
    if(event.target.closest('.icon-button'))tooltip.hidden=true;
    const media=event.target.closest('.writing-source-figure img,.demo-source-figure img,.source-region-image');
    if(!media)return;
    event.preventDefault();event.stopPropagation();const img=media.matches('img')?media:media.querySelector('image');const url=img?.src||img?.getAttribute('href');
    if(!url)return;const full=new Image();full.src=url;full.alt=img.alt||'完整原图';$('image-stage').replaceChildren(full);$('image-viewer').showModal();
  },true);
  $('image-viewer').querySelector('button').onclick=()=>$('image-viewer').close();
  $('image-viewer').addEventListener('click',event=>{if(event.target===$('image-viewer'))$('image-viewer').close();});
  function updateDocumentStatus(detail=window.ReaderSourceBridge?.getState()){
    if(!detail?.doc)return;
    const doc=detail.doc;
    $('current-section-context').textContent=doc.section_number+' · '+doc.core_questions.length+' 个核心问题';
    $('reading-location').textContent=doc.section_number;
    $('preview-indicator').hidden=!detail.preview;
    $('preview-indicator').textContent=doc.validation?.passed?'稿件预览':'待审预览';
    message((detail.preview?'完整稿预览 · ':'')+(doc.validation?.passed?'本节检查通过':'本节审查待完成')+' · '+doc.core_questions.length+' 个核心问题');
  }
  function enhance(){
    if(initialized||!document.querySelector('.writing-unit')||!window.ReaderSourceBridge?.getState()?.ready)return;initialized=true;
    $('demo-title').dataset.tooltip=$('demo-title').textContent;
    
    
    const sourceChoice=$('source-unit-select');
    const describeChoice=()=>{sourceChoice.dataset.tooltip=sourceChoice.selectedOptions[0]?.textContent||'';};
    sourceChoice.addEventListener('change',describeChoice);describeChoice();
    for(const el of document.querySelectorAll('.demo-outline-question,.demo-outline-section'))el.dataset.tooltip=el.textContent;
    const units=[...document.querySelectorAll('.writing-unit')];
    const unitLinks=[...document.querySelectorAll('.demo-outline-question')];
    const observer=new IntersectionObserver(entries=>{
      const active=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top)[0];if(!active)return;
      const index=units.indexOf(active.target);$('reading-location').textContent=active.target.querySelector('h3')?.textContent.split(' ')[0]||'';
      unitLinks.forEach((el,i)=>{el.classList.toggle('is-reading-current',i===index);if(i===index)el.setAttribute('aria-current','location');else el.removeAttribute('aria-current');});
    },{root:panes.lesson,rootMargin:'-55px 0px -60% 0px',threshold:0});units.forEach(el=>observer.observe(el));
    $('demo-outline').addEventListener('click',()=>{if(drawer==='directory')closeDrawer(false);});
    updateDocumentStatus();layout();
  }
  document.addEventListener('reading:document-ready',event=>{enhance();updateDocumentStatus(event.detail);});
  new ResizeObserver(queueLayout).observe($('reader-shell'));
  window.addEventListener('resize',queueLayout);
  fetch('/design-tokens.json').then(r=>r.json()).then(value=>{tokens=value;theme();layout();enhance();}).catch(()=>{theme();layout();message('已使用本地默认样式，设计参数文件读取失败');});
  window.readerUIState=()=>({preferences:structuredClone(state),visible:{...current},drawer});
  window.prototypeState=window.readerUIState;
  window.ReaderUI={openPane:(name,options={})=>{if(name==='lesson'){if(drawer)closeDrawer(false);}else if(panes[name])openDrawer(name,!!options.modal,options.trigger||null);},closeDrawer};
  theme();layout();enhance();
})();


// 当前位置从当前章节的真实材料包读取，原句、译句和原件共用材料版本与句子编号
(() => {
  const $ = id => document.getElementById(id);
  const surface = $('locator-surface'), viewport = $('locator-viewport'), image = $('locator-image'), iframe = $('locator-dom');
  if (!surface || !viewport || !iframe) return;
  image.hidden = true;
  let manifest, sourcePack, pending, selection, selectedId, normalId, normalSentenceId, savedView;
  let mode = 'page', fit = 'highlight', positions = [], currentPage, currentSource, currentRefs = [], currentFile;
  let domLoaded = false, activeSentenceId = null, eligibleSentences = [], hoverTimer, documentGeneration = 0, currentPageId;
  let materialIdentity = null;
  const zoom = { page: 1, dom: 1 };
  const originalDOMWidths = new WeakMap(), panDocuments = new WeakSet();
  const zoomKey = 'aialra:source-zoom:v1';
  try { const saved = Number(localStorage.getItem(zoomKey)); if (saved >= 10 && saved <= 300) zoom.page = zoom.dom = saved / 100; } catch {}
  let recenterFrame = 0, pendingCenter = false, pendingFit = false, pendingAnchor = null, savedDOMView = null;
  let domHighlights = null, domFit = null, domSize = null, navigationKey = '', viewOptionsKey = '';
  // 只有选句、回到高亮或主动适配会居中，加载和尺寸变化保留自由拖动的位置
  function scheduleRecenter(center = true, fitOnce = false, anchor = null) {
    pendingCenter ||= center; pendingFit ||= fitOnce; if (anchor) pendingAnchor = anchor;
    if (!recenterFrame) recenterFrame = requestAnimationFrame(() => {
      recenterFrame = 0;
      const options = { center: pendingCenter, fitOnce: pendingFit, anchor: pendingAnchor };
      pendingCenter = false; pendingFit = false; pendingAnchor = null; recenter(options);
    });
  }
  const make = (tag, text, cls) => { const el = document.createElement(tag); if (text) el.textContent = text; if (cls) el.className = cls; return el; };
  const sourceFor = id => sourcePack?.sources.find(source => source.id === id);
  const locationFor = id => manifest?.sources?.[id];
  const refsFor = id => selection?.refs.filter(ref => ref.source_id === id) || [];
  const setStatus = text => { $('locator-status').textContent = text; $('locator-view-select').title = text; };
  const sentenceFor = () => currentSource?.sentences?.find(sentence => sentence.id === activeSentenceId);
  function sentenceLocation() {
    const sentence = sentenceFor(), result = locationFor(selectedId)?.sentences?.[activeSentenceId];
    // 句子编号相同而原文不同的时候，旧位置保持失效，不会借用旧坐标
    return result && sentence && result.original === sentence.original ? result : null;
  }
  function bounds() {
    const location = locationFor(selectedId);
    if (activeSentenceId) { const sentence = sentenceLocation(); return (sentence?.status === 'exact' ? sentence.rects : []).filter(rect => rect.page_id === currentPageId).map(rect => rect.bbox); }
    const sourceBoxes = (location?.locations || []).filter(item => item.page_id === currentPageId).map(item => item.bbox);
    if (!sourceBoxes.length) return [];
    const requested = new Set(currentRefs.flatMap(ref => ref.region_ids || []).map(id => id.split('.')[0]));
    const regions = sourcePack.image_regions?.[selectedId];
    const childBoxes = [...requested].map(name => regions?.[name]).filter(Boolean);
    if (!childBoxes.length) return sourceBoxes;
    const box = sourceBoxes[0];
    return childBoxes.map(region => {
      const [x, y, width, height] = region.bbox, [iw, ih] = region.image_size;
      return [box[0] + x / iw * (box[2] - box[0]), box[1] + y / ih * (box[3] - box[1]),
        box[0] + (x + width) / iw * (box[2] - box[0]), box[1] + (y + height) / ih * (box[3] - box[1])];
    });
  }
  function validBox(box, page) {
    return box?.length === 4 && box.every(Number.isFinite) && box[2] > box[0] && box[3] > box[1] &&
      box[0] >= 0 && box[1] >= 0 && box[2] <= page.width + 1 && box[3] <= page.height + 1;
  }
  function drawPage() {
    positions = currentPage ? bounds().filter(box => validBox(box, currentPage)) : [];
    $('locator-highlights').replaceChildren(...positions.map(box => {
      const el = make('span', null, 'locator-highlight');
      el.dataset.sourceId = selectedId; if (activeSentenceId) el.dataset.sentenceId = activeSentenceId;
      el.dataset.materialRun = sourcePack.material_run; el.dataset.materialPath = sourcePack.material_path;
      el.dataset.bbox = JSON.stringify(box);
      el.setAttribute('aria-label', (activeSentenceId || selectedId) + ' 在原件中的位置');
      Object.assign(el.style, { left: box[0] / currentPage.width * 100 + '%', top: box[1] / currentPage.height * 100 + '%',
        width: (box[2] - box[0]) / currentPage.width * 100 + '%', height: (box[3] - box[1]) / currentPage.height * 100 + '%' });
      return el;
    }));
    if (currentPage) {
      image.style.aspectRatio = currentPage.width + ' / ' + currentPage.height;
      image.alt = (currentPage.number ? 'PDF 第 ' + currentPage.number + ' 页' : currentPage.kind === 'image' ? '原始图片' : '当前离线网页的原页') + '，来源 ' + selectedId;
      image.onload = () => scheduleRecenter(false);
      const imagePath = window.LWPath ? window.LWPath(currentPage.image) : currentPage.image; if (image.getAttribute('src') !== imagePath) image.src = imagePath;
      image.hidden = false;
    } else { image.removeAttribute('src'); image.hidden = true; }
    scheduleRecenter();
  }
  function union(boxes) {
    return boxes.length ? [Math.min(...boxes.map(box => box[0])), Math.min(...boxes.map(box => box[1])),
      Math.max(...boxes.map(box => box[2])), Math.max(...boxes.map(box => box[3]))] : null;
  }
  function captureView() {
    if (mode === 'dom' || currentFile) {
      const doc = iframe.contentDocument;
      if (!domLoaded || !doc?.body || !iframe.clientWidth) return null;
      const rect = doc.body.getBoundingClientRect(), scale = Number(doc.body.style.zoom) || 1;
      return { kind: 'dom', x: (iframe.clientWidth / 2 - rect.left) / scale, y: (iframe.clientHeight / 2 - rect.top) / scale };
    }
    if (!currentPage || !viewport.clientWidth) return null;
    const page = $('locator-page').getBoundingClientRect(), area = viewport.getBoundingClientRect(), scale = page.width / currentPage.width;
    return scale ? { kind: 'page', x: (area.left + viewport.clientWidth / 2 - page.left) / scale, y: (area.top + viewport.clientHeight / 2 - page.top) / scale } : null;
  }
  function setZoom(percent, schedule = true) {
    if (!Number.isFinite(Number(percent))) return;
    const anchor = schedule ? captureView() : null;
    const value = Math.max(10, Math.min(300, Math.round(Number(percent))));
    zoom.page = zoom.dom = value / 100;
    try { localStorage.setItem(zoomKey, String(value)); } catch {}
    updateZoomUI(); if (schedule) scheduleRecenter(false, false, anchor);
  }
  function recenter(options) {
    const defer = () => { pendingCenter ||= options.center; pendingFit ||= options.fitOnce; if (options.anchor) pendingAnchor = options.anchor; };
    if (mode === 'dom' || currentFile) {
      if (!domLoaded || !iframe.clientWidth || !iframe.clientHeight) { defer(); return; }
      highlightDOM(options); return;
    }
    if (!currentPage || !viewport.clientWidth) { defer(); return; }
    const whole = [0, 0, currentPage.width, currentPage.height], highlight = union(positions);
    const target = fit === 'highlight' && highlight ? highlight : whole;
    const anchor = options.anchor || (!options.center ? captureView() : null);
    if (options.fitOnce) {
      const base = Math.min(Math.max(1, viewport.clientWidth - 24) / (target[2] - target[0]), Math.max(1, viewport.clientHeight - 24) / (target[3] - target[1]));
      setZoom(Math.floor(base * 100), false);
    }
    const scale = zoom.page, page = $('locator-page'), stage = $('locator-stage');
    page.style.width = currentPage.width * scale + 'px';
    stage.style.width = currentPage.width * scale + 'px';
    stage.style.padding = viewport.clientHeight + 'px ' + viewport.clientWidth + 'px';
    const centered = options.fitOnce ? target : highlight || whole;
    const point = options.center ? { x: (centered[0] + centered[2]) / 2, y: (centered[1] + centered[3]) / 2 } : anchor?.kind === 'page' ? anchor : null;
    if (point) {
      const rect = page.getBoundingClientRect(), area = viewport.getBoundingClientRect();
      viewport.scrollTo({ left: viewport.scrollLeft + rect.left - area.left + point.x * scale - viewport.clientWidth / 2,
        top: viewport.scrollTop + rect.top - area.top + point.y * scale - viewport.clientHeight / 2, behavior: 'instant' });
    }
  }
  function fitDOM(nodes, options) {
    const doc = iframe.contentDocument;
    if (!doc?.body || !iframe.clientWidth || !iframe.clientHeight) return;
    const anchor = options.anchor || (!options.center ? captureView() : null);
    const collect = () => { const boxes = []; for (const node of nodes) {
      let rects;
      if (currentFile) {
        const range = doc.createRange(); range.selectNodeContents(node); rects = [...range.getClientRects()];
        const row = node.getBoundingClientRect();
        if (rects.length) rects.push({ left: row.left, right: Math.min(...rects.map(rect => rect.left)), top: row.top, bottom: row.bottom });
      } else rects = [...node.getClientRects()];
      for (const rect of rects) if (rect.right > rect.left && rect.bottom > rect.top) boxes.push([rect.left, rect.top, rect.right, rect.bottom]);
    } return union(boxes); };
    if (options.fitOnce) {
      const width = iframe.clientWidth, height = iframe.clientHeight;
      const reusable = domFit?.doc === doc && domFit.width === width && domFit.height === height &&
        domFit.nodes.length === nodes.length && nodes.every((node, index) => node === domFit.nodes[index]);
      if (!reusable) {
        // 只有点击适配时才测量原始比例，普通选句沿用已有缩放
        doc.body.style.zoom = 1;
        const box = collect(); if (!box) { doc.body.style.zoom = zoom[mode]; return; }
        domFit = { doc, nodes, width, height, base: Math.min(Math.max(1, width - 24) / (box[2] - box[0]), Math.max(1, height - 24) / (box[3] - box[1])) };
      }
      setZoom(Math.floor(domFit.base * 100), false);
    }
    doc.body.style.zoom = zoom[mode];
    if (options.center) {
      const actual = collect(); if (!actual) return;
      iframe.contentWindow.scrollTo({ left: iframe.contentWindow.scrollX + (actual[0] + actual[2] - iframe.clientWidth) / 2,
        top: iframe.contentWindow.scrollY + (actual[1] + actual[3] - iframe.clientHeight) / 2, behavior: 'instant' });
    } else if (anchor?.kind === 'dom') {
      const rect = doc.body.getBoundingClientRect();
      iframe.contentWindow.scrollTo({ left: iframe.contentWindow.scrollX + rect.left + anchor.x * zoom[mode] - iframe.clientWidth / 2,
        top: iframe.contentWindow.scrollY + rect.top + anchor.y * zoom[mode] - iframe.clientHeight / 2, behavior: 'instant' });
    }
  }
  function normalizedMap(text) {
    const chars = [], offsets = []; let index = 0;
    for (const char of text) {
      for (let letter of char.normalize('NFKC').toLowerCase()) {
        letter = letter.replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/[–—−]/g, '-').replace(/\u00ad/g, '');
        if (letter && !/\s/u.test(letter)) { chars.push(letter); offsets.push(index); }
      }
      index += char.length;
    }
    return { text: chars.join(''), offsets };
  }
  // 在实际 DOM 文本节点中逐字找回当前句，链接、强调和原始节点继续保留
  function markSentence(root, sentence, sentenceId) {
    const nodes = [], walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT); let node, raw = '';
    while (node = walker.nextNode()) {
      if (node.parentElement.closest('script,style')) continue;
      nodes.push({ node, start: raw.length }); raw += node.textContent;
    }
    const actual = normalizedMap(raw), needle = normalizedMap(sentence).text, start = actual.text.indexOf(needle);
    if (!needle || start < 0 || actual.text.indexOf(needle, start + 1) >= 0) return false;
    const first = actual.offsets[start], last = actual.offsets[start + needle.length - 1] + 1;
    for (const item of nodes) {
      const a = Math.max(0, first - item.start), b = Math.min(item.node.length, last - item.start);
      if (b <= a) continue;
      const range = root.ownerDocument.createRange(); range.setStart(item.node, a); range.setEnd(item.node, b);
      const mark = root.ownerDocument.createElement('mark'); mark.dataset.locatorMark = 'true'; mark.dataset.sentenceId = sentenceId;
      range.surroundContents(mark);
    }
    return true;
  }
  function highlightDOM(options) {
    if (!domLoaded || !currentSource) return;
    const doc = iframe.contentDocument; if (!doc?.body) return;
    if (!options.center && !options.anchor) options = { ...options, anchor: captureView() };
    const width = iframe.clientWidth, height = iframe.clientHeight;
    if (!originalDOMWidths.has(doc.body)) originalDOMWidths.set(doc.body, doc.body.style.width);
    if (domSize?.doc !== doc || domSize.width !== width || domSize.height !== height) {
      Object.assign(doc.documentElement.style, { width: width + 'px', padding: height + 'px ' + width + 'px', boxSizing: 'content-box' });
      doc.body.style.width = originalDOMWidths.get(doc.body); doc.body.style.zoom = 1;
      doc.body.style.width = getComputedStyle(doc.body).width; doc.body.style.zoom = zoom[mode];
      domHighlights = null; domFit = null;
      domSize = { doc, width, height };
    }
    doc.body.style.position = 'relative';
    const key = JSON.stringify([selectedId, activeSentenceId, currentRefs]);
    if (domHighlights?.doc === doc && domHighlights.key === key && domHighlights.nodes.length && domHighlights.nodes.every(node => node.isConnected)) {
      fitDOM(domHighlights.nodes, options); return;
    }
    domFit = null;
    doc.querySelectorAll('[data-locator-mark]').forEach(el => el.replaceWith(...el.childNodes)); doc.body.normalize();
    doc.querySelectorAll('.location-selected').forEach(el => el.classList.remove('location-selected'));
    doc.querySelectorAll('.dom-image-region').forEach(el => el.remove());
    if (currentFile) {
      const location = sentenceLocation();
      if (location?.status !== 'exact' || location.file_id !== currentFile.id) { describe(); return; }
      for (let line = location.start_line; line <= location.end_line; line++) doc.getElementById('L' + line)?.classList.add('location-selected');
      const nodes = [...doc.querySelectorAll('.location-selected')];
      domHighlights = { doc, key, nodes }; fitDOM(nodes, options);
      describe(); return;
    }
    let target; try { target = doc.querySelector(currentSource.source.dom_path); } catch {}
    if (!target) { setStatus(selectedId + ' · 当前离线 DOM 没有取得对应节点'); return; }
    let found = false;
    if (activeSentenceId) {
      const sentence = sentenceFor();
      const location = sentenceLocation();
      if (sentence && location?.status === 'exact') {
        if (location.method === 'image_ocr_characters') {
          const img = target.tagName === 'IMG' ? target : target.querySelector('img');
          const sourceBox = locationFor(selectedId)?.locations?.find(item => item.page_id === 'web')?.bbox;
          if (img && sourceBox) {
            const r = img.getBoundingClientRect(), origin = doc.body.getBoundingClientRect(), factor = Number(doc.body.style.zoom) || 1;
            for (const rect of location.rects.filter(rect => rect.page_id === 'web')) {
              const box = rect.bbox, el = doc.createElement('div');
              el.className = 'dom-image-region'; el.dataset.sentenceId = activeSentenceId;
              Object.assign(el.style, { position: 'absolute', pointerEvents: 'none', boxSizing: 'border-box', border: '2px solid #b77714', background: '#e9a73c22',
                left: (r.left - origin.left + (box[0] - sourceBox[0]) / (sourceBox[2] - sourceBox[0]) * r.width) / factor + 'px',
                top: (r.top - origin.top + (box[1] - sourceBox[1]) / (sourceBox[3] - sourceBox[1]) * r.height) / factor + 'px',
                width: (box[2] - box[0]) / (sourceBox[2] - sourceBox[0]) * r.width / factor + 'px',
                height: (box[3] - box[1]) / (sourceBox[3] - sourceBox[1]) * r.height / factor + 'px' });
              doc.body.append(el); found = true;
            }
          }
        } else found = markSentence(target, sentence.original, sentence.id);
      }
    } else {
      target.classList.add('location-selected');
      const regionIds = new Set(currentRefs.flatMap(ref => ref.region_ids || []).map(id => id.split('.')[0]));
      const img = target.tagName === 'IMG' ? target : target.querySelector('img');
      if (img && regionIds.size) {
        // 图片边框会随 DOM 缩放，区域坐标除以当前缩放后再放进同一文档
        const r = img.getBoundingClientRect(), origin = doc.body.getBoundingClientRect(), factor = Number(doc.body.style.zoom) || 1;
        for (const name of regionIds) {
          const region = sourcePack.image_regions?.[selectedId]?.[name]; if (!region) continue;
          const [x, y, width, height] = region.bbox, [iw, ih] = region.image_size, el = doc.createElement('div');
          el.className = 'dom-image-region'; el.dataset.region = name;
          Object.assign(el.style, { position: 'absolute', pointerEvents: 'none', boxSizing: 'border-box', border: '2px solid #b77714', background: '#e9a73c22',
            left: (r.left - origin.left + x / iw * r.width) / factor + 'px', top: (r.top - origin.top + y / ih * r.height) / factor + 'px',
            width: width / iw * r.width / factor + 'px', height: height / ih * r.height / factor + 'px' });
          doc.body.append(el);
        }
      }
    }
    const nodes = found ? [...doc.querySelectorAll('[data-locator-mark],.dom-image-region')] : [...doc.querySelectorAll('.location-selected,.dom-image-region')];
    if (!nodes.length) nodes.push(target);
    domHighlights = { doc, key, nodes }; fitDOM(nodes, options);
    if (activeSentenceId) setStatus(activeSentenceId + ' · ' + (found ? '原句已在实际 DOM 中高亮' : '当前句的精确 DOM 位置尚未取得'));
    else setStatus(selectedId + ' · 已定位实际网页节点');
  }
  function loadDOM(path) {
    path = window.LWPath ? window.LWPath(path) : path;
    if (iframe.getAttribute('src') === path) { if (domLoaded) scheduleRecenter(); return; }
    domLoaded = false; iframe.style.visibility = 'hidden'; iframe.src = window.LWPath ? window.LWPath(path) : path;
  }
  function setMode(next) {
    mode = next === 'dom' && manifest?.web ? 'dom' : 'page';
    const showDOM = mode === 'dom' || !!currentFile;
    viewport.hidden = showDOM; iframe.hidden = !showDOM;
    const choices = currentFile ? [['highlight', currentSource?.type === 'code' || currentSource?.verbatim_code ? '源码行号' : '文件行号']] :
      [['highlight', currentPage?.kind === 'pdf' ? 'PDF 高亮' : currentPage?.kind === 'image' ? '原图高亮' : '原页高亮'], ['page', currentPage?.kind === 'pdf' ? 'PDF 整页' : '完整原页']];
    if (manifest?.web) choices.push(['dom', '网页 DOM']);
    const optionsKey = JSON.stringify(choices);
    if (optionsKey !== viewOptionsKey) {
      $('locator-view-select').replaceChildren(...choices.map(([value, label]) => { const option = make('option', label); option.value = value; return option; }));
      viewOptionsKey = optionsKey;
    }
    $('locator-view-select').value = mode === 'dom' ? 'dom' : currentFile ? 'highlight' : fit;
    updateZoomUI();
    if (showDOM) loadDOM(currentFile ? currentFile.dom : manifest.web.dom);
    else { describe(); scheduleRecenter(); }
  }
  function describe() {
    if (!currentSource) return;
    const sourceKind = currentSource.source?.kind;
    const originalKind = sourceKind === 'html' ? '原网页' : sourceKind === 'pdf' || /\.pdf$/i.test(currentSource.source?.path || '') ? 'PDF 原件' : '原件';
    const location = sentenceLocation(), prefix = currentFile ? currentFile.path : currentPage?.number ? 'PDF 第 ' + currentPage.number + ' 页' : currentPage?.kind === 'image' ? '原图' : originalKind;
    if (activeSentenceId) {
      if (currentFile && location?.status === 'exact') setStatus(activeSentenceId + ' · ' + prefix + ' · 第 ' + location.start_line + '–' + location.end_line + ' 行');
      else setStatus(activeSentenceId + ' · ' + prefix + ' · ' + (positions.length ? '仅高亮当前句' : location?.status === 'ambiguous' ? '原句存在多个相同位置，尚未取得唯一句框' : '当前句的精确坐标尚未取得'));
    } else setStatus(selectedId + ' · ' + prefix + (currentPage ? ' · 原材料位置' : ' · 当前材料尚未取得可显示的原件位置'));
  }
  function sentenceOptions(source, refs) {
    const requested = new Set(refs.flatMap(ref => ref.sentence_ids || []));
    return (source.sentences || []).filter(sentence => sentence.evidence_kind !== 'material_index' && (!requested.size || requested.has(sentence.id)));
  }
  function renderSentenceNavigation() {
    $('locator-sentence-navigation').hidden = !eligibleSentences.length || !activeSentenceId;
    $('locator-page-navigation').hidden = true;
    if (!eligibleSentences.length || !activeSentenceId) return;
    const index = eligibleSentences.findIndex(sentence => sentence.id === activeSentenceId);
    const all = currentSource.sentences.filter(sentence => sentence.evidence_kind !== 'material_index');
    const choice = $('locator-sentence-select');
    const key = JSON.stringify([selectedId, eligibleSentences.map(sentence => sentence.id)]);
    if (key !== navigationKey) {
      const indexes = new Map(all.map((sentence, index) => [sentence.id, index + 1]));
      choice.replaceChildren(...eligibleSentences.map(sentence => {
        const option = make('option', indexes.get(sentence.id) + '/' + all.length);
        option.value = sentence.id; option.title = sentence.original; return option;
      }));
      navigationKey = key;
    }
    choice.value = activeSentenceId; choice.title = sentenceFor()?.original || '';
    $('locator-sentence-label').textContent = '第 ' + (all.findIndex(sentence => sentence.id === activeSentenceId) + 1) + ' / ' + all.length + (currentFile ? ' 段原文' : ' 句');
    $('locator-previous-sentence').disabled = index <= 0; $('locator-next-sentence').disabled = index >= eligibleSentences.length - 1;
    const ids = [...new Set((sentenceLocation()?.rects || []).map(rect => rect.page_id))];
    $('locator-page-navigation').hidden = ids.length < 2;
    $('locator-page-label').textContent = ids.length ? '第 ' + (ids.indexOf(currentPageId) + 1) + ' / ' + ids.length + ' 页' : '';
    $('locator-previous-page').disabled = ids.indexOf(currentPageId) <= 0;
    $('locator-next-page').disabled = ids.indexOf(currentPageId) >= ids.length - 1;
  }
  function revealSentence() {
    const pair = activeSentenceId ? $('source-cards').querySelector('[data-sentence-id="' + CSS.escape(activeSentenceId) + '"]') : null;
    if (!pair) return;
    const pane = $('source-text-scroll'), r = pair.getBoundingClientRect(), area = pane.getBoundingClientRect();
    if (r.top < area.top || r.height > area.height) pane.scrollTop += r.top - area.top - 10;
    else if (r.bottom > area.bottom) pane.scrollTop += r.bottom - area.bottom + 10;
  }
  function selectSource(id, refs = refsFor(id), preferredSentence = null) {
    const source = sourceFor(id); if (!source || !manifest) return;
    const previousKey = JSON.stringify([selectedId, activeSentenceId, currentRefs]);
    eligibleSentences = sentenceOptions(source, refs);
    const candidates = eligibleSentences.map(sentence => sentence.id), previous = id === selectedId ? activeSentenceId : null;
    const requestedSentences = refs.some(ref => ref.sentence_ids?.length);
    const regionOnly = refs.some(ref => ref.region_ids?.length) && !requestedSentences;
    const wholeImage = !!source.asset && ['image', 'figure', 'figure_group'].includes(source.type) && !requestedSentences && !preferredSentence;
    activeSentenceId = (regionOnly && !preferredSentence) || wholeImage ? null : [preferredSentence, previous, ...candidates].find(id => candidates.includes(id)) || null;
    selectedId = id; currentSource = source;
    const selectedSentence = sentenceFor();
    currentRefs = activeSentenceId ? [{ source_id: id, sentence_ids: [activeSentenceId], ...(selectedSentence?.region ? { region_ids: [selectedSentence.region] } : {}) }] : refs;
    if (!selection?.block_id) { normalId = id; normalSentenceId = activeSentenceId; }
    const location = sentenceLocation(), sourceLocation = locationFor(id);
    currentFile = location?.file_id ? manifest.files[location.file_id] : null;
    currentPageId = location?.rects?.[0]?.page_id || sourceLocation?.page_ids?.[0];
    currentPage = manifest.pages[currentPageId];
    $('locator-dialog-title').textContent = '原文定位 · ' + id + (currentPage?.number ? ' · 第 ' + currentPage.number + ' 页' : '');
    const sourceSelect = $('locator-source-select');
    if (![...sourceSelect.options].some(option => option.value === id)) { const option = make('option', id); option.value = id; sourceSelect.append(option); }
    sourceSelect.value = id; sourceSelect.title = id;
    const targets = new Set(activeSentenceId ? $('source-cards').querySelectorAll('.source-sentence-pair[data-sentence-id="' + CSS.escape(activeSentenceId) + '"]') : []);
    for (const pair of $('source-cards').querySelectorAll('.is-locator-selected')) if (!targets.has(pair)) { pair.classList.remove('is-locator-selected'); pair.removeAttribute('aria-current'); }
    for (const pair of targets) if (!pair.classList.contains('is-locator-selected')) { pair.classList.add('is-locator-selected'); pair.setAttribute('aria-current', 'true'); }
    if (previousKey === JSON.stringify([selectedId, activeSentenceId, currentRefs])) { renderSentenceNavigation(); scheduleRecenter(); return; }
    drawPage(); describe(); renderSentenceNavigation(); setMode(mode);
  }
  function update(detail) {
    pending = detail; if (!manifest || !sourcePack) return;
    const wasPreview = !!selection?.block_id;
    if (detail.block_id && !wasPreview) savedView = { id: selectedId, sentenceId: activeSentenceId, top: viewport.scrollTop, left: viewport.scrollLeft };
    selection = detail;
    const ids = [...new Set(detail.refs.map(ref => ref.source_id))].filter(id => sourceFor(id));
    $('locator-source-select').replaceChildren(...ids.map(id => { const option = make('option', id); option.value = id; return option; }));
    const locatable = id => { const value=manifest.sources[id]; return value && (value.page_ids?.length || value.file_ids?.length); };
    const preferred = ids.find(locatable) || ids[0];
    const next = detail.block_id ? preferred : ids.includes(normalId) ? normalId : preferred;
    if (!next) { setStatus('当前内容没有可定位的原材料'); return; }
    selectSource(next, refsFor(next), detail.block_id ? null : normalSentenceId);
    if (detail.block_id) revealSentence();
    if (wasPreview && !detail.block_id && savedView && ids.includes(savedView.id)) {
      const restore = savedView; savedView = null; selectSource(restore.id, refsFor(restore.id), restore.sentenceId);
      requestAnimationFrame(() => viewport.scrollTo({ top: restore.top, left: restore.left, behavior: 'instant' }));
    }
  }
  async function documentReady(detail) {
    if (!detail?.sourcePack || !detail.ready) return;
    const generation = ++documentGeneration; sourcePack = detail.sourcePack; manifest = null;
    navigationKey = ''; domHighlights = null; domFit = null; domSize = null; savedDOMView = null;
    const identity = sourcePack.material_run + '\n' + sourcePack.material_path;
    if (identity !== materialIdentity) { iframe.removeAttribute('src'); domLoaded = false; materialIdentity = identity; }
    selectedId = null; activeSentenceId = null; currentSource = null; currentPage = null; currentFile = null; selection = null;
    image.hidden = true; image.removeAttribute('src'); $('locator-highlights').replaceChildren(); $('locator-source-select').replaceChildren();
    pending = detail.selection; setMode('page'); setStatus('正在读取当前材料的原件位置');
    try {
      const response = await fetch('/05_writing/source-location/index.json', { cache: 'no-store' });
      if (!response.ok) throw new Error('positions unavailable');
      const index = await response.json();
      const version = index.versions.find(item => item.material_run === sourcePack.material_run && item.material_path === sourcePack.material_path);
      if (!version) throw new Error('material version unavailable');
      const locationResponse = await fetch(version.manifest, { cache: 'no-store' });
      if (!locationResponse.ok) throw new Error('positions unavailable');
      const value = await locationResponse.json();
      if (generation !== documentGeneration) return;
      if (value.material_run !== sourcePack.material_run || value.material_path !== sourcePack.material_path) throw new Error('material version mismatch');
      manifest = value; if (pending) update(pending);
    } catch (error) {
      if (generation === documentGeneration) { $('locator-highlights').replaceChildren(); setStatus('当前材料版本的原件位置尚未准备，原句与译句仍可对照'); }
    }
  }
  document.addEventListener('reading:document-ready', event => documentReady(event.detail));
  document.addEventListener('reading:source-selection', event => update(event.detail));
  document.addEventListener('reading:source-focus', event => selectSource(event.detail.source_id));
  function selectPair(pair) {
    const card = pair?.closest('[data-source-id]'); if (!card || !manifest) return;
    // 图组里的图注与图片标签按它们自己的句子编号找回来源
    const source = sourcePack.sources.find(source => source.sentences?.some(sentence => sentence.id === pair.dataset.sentenceId)) || sourceFor(card.dataset.sourceId);
    const sentence = source?.sentences?.find(sentence => sentence.id === pair.dataset.sentenceId); if (!sentence) return;
    selectSource(source.id, refsFor(source.id).length ? refsFor(source.id) : [{ source_id: source.id }], sentence.id);
  }
  $('source-cards').addEventListener('click', event => {
    clearTimeout(hoverTimer); const pair = event.target.closest('[data-sentence-id]');
    if (pair) selectPair(pair); else { const card = event.target.closest('[data-source-id]'); if (card) selectSource(card.dataset.sourceId); }
  });
  $('source-cards').addEventListener('pointerover', event => {
    if (event.pointerType !== 'mouse' || event.buttons) return;
    const pair = event.target.closest('[data-sentence-id]'); if (!pair || pair.contains(event.relatedTarget)) return;
    clearTimeout(hoverTimer); hoverTimer = setTimeout(() => { if (pair.matches(':hover')) selectPair(pair); }, 140);
  });
  $('source-cards').addEventListener('pointerout', event => { const pair = event.target.closest('[data-sentence-id]'); if (pair && !pair.contains(event.relatedTarget)) clearTimeout(hoverTimer); });
  $('source-cards').addEventListener('focusin', event => { const pair = event.target.closest('[data-sentence-id]'); if (pair?.matches(':focus-visible')) selectPair(pair); });
  function stepSentence(amount) {
    const index = eligibleSentences.findIndex(sentence => sentence.id === activeSentenceId), next = eligibleSentences[index + amount];
    if (!next) return; selectSource(selectedId, refsFor(selectedId), next.id); revealSentence();
  }
  $('locator-previous-sentence').onclick = () => stepSentence(-1); $('locator-next-sentence').onclick = () => stepSentence(1);
  $('locator-sentence-select').onchange = event => { selectSource(selectedId, refsFor(selectedId), event.target.value); revealSentence(); };
  $('locator-source-select').onchange = event => { selectSource(event.target.value); revealSentence(); };
  const pageNavigation = make('div', null, 'locator-sentence-navigation'); pageNavigation.id = 'locator-page-navigation'; pageNavigation.hidden = true;
  for (const [id, label, amount] of [['locator-previous-page', '上一页', -1], ['locator-page-label', '', 0], ['locator-next-page', '下一页', 1]]) {
    const element = make(amount ? 'button' : 'span', label, amount ? 'text-action' : ''); element.id = id;
    if (amount) element.onclick = () => {
      const ids = [...new Set((sentenceLocation()?.rects || []).map(rect => rect.page_id))], next = ids[ids.indexOf(currentPageId) + amount];
      if (!next) return; currentPageId = next; currentPage = manifest.pages[next]; drawPage(); describe(); renderSentenceNavigation();
    };
    pageNavigation.append(element);
  }
  surface.before(pageNavigation);
  // 图像与高亮共用同一父元素，缩放时保持原始坐标比例
  function updateZoomUI() {
    const percent = Math.round(zoom[mode] * 100);
    document.querySelectorAll('[data-locator-zoom]').forEach(button => {
      const action = button.dataset.locatorZoom, factor = zoom[mode];
      button.disabled = action === 'out' && factor <= .1 || action === 'in' && factor >= 3;
    });
    document.querySelectorAll('[data-locator-zoom-select]').forEach(select => {
      if (!select.options.length || !select.dataset.ready) {
        const values = [...new Set([...Array.from({length:30},(_,index)=>(index+1)*10),25,75,125,175])].sort((a,b)=>a-b);
        select.replaceChildren(...values.map(value => { const option = make('option', value + '%'); option.value = value; return option; }));
        select.dataset.ready = 'true';
      }
      select.querySelectorAll('[data-custom]').forEach(option => { if (Number(option.value) !== percent) option.remove(); });
      if (![...select.options].some(option => Number(option.value) === percent)) { const option = make('option', percent + '%'); option.value = percent; option.dataset.custom = 'true'; select.append(option); }
      select.value = percent;
    });
    document.querySelectorAll('[data-locator-fit]').forEach(button => button.disabled = mode === 'dom' || currentFile ? !domLoaded : !currentPage);
  }
  document.querySelectorAll('[data-locator-zoom]').forEach(button => button.addEventListener('click', () => {
    const action = button.dataset.locatorZoom;
    setZoom(zoom[mode] * 100 + (action === 'in' ? 10 : -10));
  }));
  document.querySelectorAll('[data-locator-zoom-select]').forEach(select => select.onchange = event => setZoom(event.target.value));
  document.querySelectorAll('[data-locator-fit]').forEach(button => button.onclick = () => scheduleRecenter(true, true));
  $('locator-view-select').onchange = event => { fit = event.target.value === 'page' ? 'page' : 'highlight'; setMode(event.target.value === 'dom' ? 'dom' : 'page'); };
  $('locator-recenter').onclick = () => scheduleRecenter(true);
  function installPan(target, read, write) {
    let drag = null;
    target.style.touchAction = 'none'; target.style.cursor = 'grab';
    target.addEventListener('dragstart', event => event.preventDefault());
    target.addEventListener('pointerdown', event => {
      if (event.button !== 0 || event.target.closest('a,button,input,textarea,select,[contenteditable=true]')) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, ...read() };
      target.setPointerCapture(event.pointerId); target.style.cursor = 'grabbing'; target.style.userSelect = 'none'; event.preventDefault();
    });
    target.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      write(drag.left + drag.x - event.clientX, drag.top + drag.y - event.clientY); event.preventDefault();
    });
    const finish = () => { drag = null; target.style.cursor = 'grab'; target.style.userSelect = ''; };
    target.addEventListener('pointerup', finish); target.addEventListener('pointercancel', finish); target.addEventListener('lostpointercapture', finish);
  }
  image.draggable = false;
  installPan(viewport, () => ({ left: viewport.scrollLeft, top: viewport.scrollTop }), (left, top) => viewport.scrollTo(left, top));
  iframe.addEventListener('load', () => {
    domLoaded = true;
    const doc = iframe.contentDocument;
    if (doc?.documentElement && !panDocuments.has(doc)) {
      panDocuments.add(doc);
      installPan(doc.documentElement, () => ({ left: iframe.contentWindow.scrollX, top: iframe.contentWindow.scrollY }), (left, top) => iframe.contentWindow.scrollTo(left, top));
    }
    const restore = savedDOMView; savedDOMView = null;
    if (restore && restore.source === selectedId && restore.sentence === activeSentenceId && restore.path === iframe.getAttribute('src')) scheduleRecenter(false, false, restore.anchor);
    else scheduleRecenter(true);
    updateZoomUI(); iframe.style.visibility = 'visible';
  });
  new ResizeObserver(() => scheduleRecenter(false)).observe(surface);
  document.addEventListener('reading:source-view-change', () => { scheduleRecenter(false); requestAnimationFrame(revealSentence); });
  const dialog = $('locator-dialog'), home = surface.parentNode;
  function prepareDOMMove() { if (iframe.getAttribute('src')) { savedDOMView = { source: selectedId, sentence: activeSentenceId, path: iframe.getAttribute('src'), anchor: captureView() }; domLoaded = false; iframe.style.visibility = 'hidden'; } }
  document.addEventListener('reading:source-view-changing', prepareDOMMove);
  $('locator-expand').onclick = () => { prepareDOMMove(); $('locator-dialog-content').append(surface); dialog.showModal(); scheduleRecenter(false); };
  $('locator-dialog-close').onclick = () => dialog.close();
  dialog.addEventListener('close', () => { prepareDOMMove(); home.insertBefore(surface, $('locator-status')); scheduleRecenter(false); $('locator-expand').focus({ preventScroll: true }); });
  updateZoomUI();
  window.ReaderSourceLocator = {
    state: () => ({ selectedId, sentenceId: activeSentenceId, mode, fit, free: true, zoom: { ...zoom }, blockId: selection?.block_id,
      materialRun: sourcePack?.material_run, materialPath: sourcePack?.material_path, sourceIds: [...new Set(selection?.refs.map(ref => ref.source_id) || [])],
      positions, currentPage, currentFile, status: sentenceLocation()?.status, domLoaded }),
    select: (sourceId, sentenceId) => selectSource(sourceId, refsFor(sourceId), sentenceId)
  };
  const initial = window.ReaderSourceBridge?.getState(); if (initial?.ready) documentReady(initial);
})();


// 材料模式与上下比例分别保存，切换时沿用当前材料、句子和缩放
(() => {
  const pane=document.getElementById('demo-original'),content=document.querySelector('.source-content');
  const text=document.getElementById('source-text-scroll'),locator=document.getElementById('source-locator'),bar=document.getElementById('source-splitter');
  const toggle=document.getElementById('source-view-toggle'),languages=document.getElementById('source-language-tools');
  if(!pane||!content||!text||!locator||!bar||!toggle)return;
  const viewKey='aialra:source-view:v1';
  let view='page-translation',ratio=.58,drag=null;
  const defaultRatio=()=>view==='page-translation'?.58:.5;
  const ratioKey=()=>view==='page-translation'?'aialra:source-split:page-translation:v1':'aialra:source-split:v1';
  const topPane=()=>view==='page-translation'?locator:text;
  const bottomPane=()=>view==='page-translation'?text:locator;
  try{if(localStorage.getItem(viewKey)==='text-original')view='text-original';}catch{}
  function loadRatio(){ratio=defaultRatio();try{const stored=Number(localStorage.getItem(ratioKey()));if(stored>=.1&&stored<=.9)ratio=stored;}catch{}}
  function apply(){content.style.setProperty('--source-upper-fr',(ratio/(1-ratio))+'fr');requestAnimationFrame(updateAria);}
  function limits(){
    const top=topPane(),bottom=bottomPane(),total=top.getBoundingClientRect().height+bottom.getBoundingClientRect().height;
    const minTop=Number.parseFloat(getComputedStyle(top).minHeight)||80,minBottom=Number.parseFloat(getComputedStyle(bottom).minHeight)||80;
    return {total,min:minTop/total,max:Math.max(minTop/total,1-minBottom/total)};
  }
  function updateAria(){
    const bounds=limits();if(!Number.isFinite(bounds.total)||bounds.total<=0)return;
    const actual=topPane().getBoundingClientRect().height/bounds.total;
    bar.setAttribute('aria-valuemin',Math.round(bounds.min*100));bar.setAttribute('aria-valuemax',Math.round(bounds.max*100));bar.setAttribute('aria-valuenow',Math.round(actual*100));
    bar.setAttribute('aria-valuetext',view==='page-translation'?'原页 '+Math.round(actual*100)+'%，中文译文 '+Math.round((1-actual)*100)+'%':'原文与译文 '+Math.round(actual*100)+'%，原文定位 '+Math.round((1-actual)*100)+'%');
  }
  function save(){try{localStorage.setItem(viewKey,view);localStorage.setItem(ratioKey(),String(ratio));}catch{document.getElementById('ui-status').textContent='材料模式和上下比例保留在本次会话中，浏览器存储写入失败';}}
  function setView(next,persist=true){
    if(drag)finish(true);
    view=next==='text-original'?'text-original':'page-translation';
    pane.dataset.sourceView=view;
    const pageFirst=view==='page-translation';
    document.getElementById('demo-original-title').textContent=pageFirst?'原页与译文':'原文与译文';
    toggle.textContent=pageFirst?'原文对照':'原页＋译文';
    toggle.setAttribute('aria-pressed',String(pageFirst));
    toggle.setAttribute('aria-label',pageFirst?'切换到原文与译文对照模式':'切换到原页与译文模式');
    if(languages)languages.hidden=pageFirst;
    bar.setAttribute('aria-label',pageFirst?'调整上方原页与下方译文的比例':'调整上方原文译文与下方原文定位的比例');
    // 按视觉顺序移动现有区域，保留句子节点和事件，让键盘阅读顺序同步改变
    document.dispatchEvent(new CustomEvent('reading:source-view-changing'));
    content.insertBefore(topPane(),bar);content.append(bottomPane());
    loadRatio();apply();if(persist)save();
    document.dispatchEvent(new CustomEvent('reading:source-view-change',{detail:{view}}));
  }
  function move(next){const bounds=limits();ratio=Math.max(bounds.min,Math.min(bounds.max,next));apply();}
  function finish(cancel){if(!drag)return;const start=drag.ratio;drag=null;document.body.classList.remove('is-source-resizing');if(cancel){ratio=start;apply();}else save();}
  toggle.addEventListener('click',()=>setView(view==='page-translation'?'text-original':'page-translation'));
  bar.addEventListener('pointerdown',event=>{
    if(event.button!==0)return;const bounds=limits();if(!bounds.total)return;
    drag={ratio,y:event.clientY,height:topPane().getBoundingClientRect().height,total:bounds.total};bar.setPointerCapture(event.pointerId);document.body.classList.add('is-source-resizing');event.preventDefault();
  });
  bar.addEventListener('pointermove',event=>{if(drag)move((drag.height+event.clientY-drag.y)/drag.total);});
  bar.addEventListener('pointerup',()=>finish(false));bar.addEventListener('pointercancel',()=>finish(true));
  window.addEventListener('keydown',event=>{if(event.key==='Escape'&&drag){finish(true);event.preventDefault();event.stopImmediatePropagation();}},true);
  bar.addEventListener('keydown',event=>{
    if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
    event.preventDefault();const bounds=limits(),actual=topPane().getBoundingClientRect().height/bounds.total;
    const step=(event.shiftKey?32:16)/bounds.total;
    move(event.key==='Home'?bounds.min:event.key==='End'?bounds.max:actual+(event.key==='ArrowDown'?step:-step));save();
  });
  bar.addEventListener('dblclick',()=>{ratio=defaultRatio();apply();save();});
  document.getElementById('reset-layout').addEventListener('click',()=>{setView('page-translation',false);ratio=defaultRatio();apply();save();});
  new ResizeObserver(updateAria).observe(content);new ResizeObserver(updateAria).observe(text);
  window.prototypeSourceSplit=()=>({ratio,actual:Number(bar.getAttribute('aria-valuenow')),dragging:!!drag,view});
  setView(view,false);
})();

  listen(root,'reading:source-selection',event=>options.onSourceSelection?.(event.detail));
  const bound=new WeakSet();
  const connectNotes=()=>root.querySelectorAll('.writing-note').forEach(box=>{
    if(bound.has(box))return;const state=owned.ReaderSourceBridge?.getState();if(!state?.doc)return;
    bound.add(box);const input=box.querySelector('textarea'),button=box.querySelector('button');
    const key=state.doc.section_id+':'+box.dataset.noteId;
    Promise.resolve(options.loadNote?.(key)).then(value=>{if(!disposed&&!input.value&&value)input.value=value});
    listen(button,'click',async()=>{await options.saveNote?.(key,input.value);const status=box.querySelector('.help');if(status)status.textContent='已保存到个人笔记'});
  });
  const observer=new MutationObserver(connectNotes);observer.observe(root,{childList:true,subtree:true});connectNotes();
  return {root, getState:()=>owned.ReaderSourceBridge?.getState(),
    focusNotes:()=>root.querySelector('.writing-note textarea')?.focus(),
    toggleGlossary:()=>root.querySelector('[data-toggle-pane="glossary"]')?.click(),
    unmount(){disposed=true;abort.abort();for(const item of [...observers])item.disconnect();for(const id of timers){native.clearTimeout(id);native.clearInterval(id)}for(const id of frames)native.cancelAnimationFrame(id);shadow.replaceChildren();}
  };
}
