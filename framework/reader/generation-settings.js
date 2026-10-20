/* 选择只影响此项目的后续任务，已有正文与历史调用记录保持原样 */
(() => {
  const form = document.getElementById('agent-settings');
  if (!form) return;
  const status = document.getElementById('agent-settings-status');
  const save = document.getElementById('save-agent-settings');
  const project = window.LESSONWEAVE?.project_id;
  const endpoint = project ? '/api/projects/' + encodeURIComponent(project) + '/generation-settings' : null;
  const labels = {off:'非推理',low:'低',medium:'中',high:'高',xhigh:'很高',max:'最高'};
  let models = [];
  function effortOptions(role, selected) {
    const model = document.getElementById(role + '-model').value;
    const input = document.getElementById(role + '-effort');
    input.replaceChildren(...(models.find(item => item.id === model)?.efforts || []).map(value => new Option(labels[value] + ' · ' + value, value)));
    input.value = [...input.options].some(option => option.value === selected) ? selected : model==='deepseek-flash'&&role==='translation' ? 'off' : 'high';
  }
  async function request(options) {
    const response = await fetch(endpoint, options);
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }
  let loaded = false;
  document.getElementById('open-settings').addEventListener('click', async () => {
    if (loaded) return;
    save.disabled = true;
    if (!endpoint) { status.textContent = '请在项目阅读入口设置后续任务'; return; }
    status.textContent = '正在读取项目设置';
    try {
      const result = await request(); models = result.models;
      for (const role of ['generation','translation']) {
        const input = document.getElementById(role + '-model');
        const choices=models.filter(item=>role==='translation'||item.id!=='deepseek-flash');
        input.replaceChildren(...choices.map(item => new Option(item.label + ' · ' + item.id, item.id)));
        // 服务端自定义后端模型继续如实显示，用户仍可改选列表中的模型
        if (!choices.some(item => item.id === result.settings[role].model)) input.add(new Option(result.settings[role].model, result.settings[role].model));
        input.value = result.settings[role].model;
        effortOptions(role, result.settings[role].effort);
        input.onchange = () => { effortOptions(role, document.getElementById(role + '-effort').value); status.textContent = '选择已更改，请保存'; };
        document.getElementById(role + '-effort').onchange = () => status.textContent = '选择已更改，请保存';
      }
      loaded = true; save.disabled = false; status.textContent = '设置用于此项目的后续任务';
    } catch { status.textContent = '项目设置暂时无法读取，请刷新后重试'; }
  });
  save.onclick = async () => {
    save.disabled = true;
    const value = Object.fromEntries(['generation','translation'].map(role => [role, {
      model:document.getElementById(role + '-model').value, effort:document.getElementById(role + '-effort').value
    }]));
    try {
      await request({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(value)});
      status.textContent = '已保存，后续任务按此设置调用';
    } catch { status.textContent = '保存未完成，请重试'; }
    finally { save.disabled = false; }
  };
})();
