"""按项目保存后续任务的模型选择，调用回执继续记录实际使用值"""
import copy
import os
from .storage import read, save

DEFAULTS = {'generation': {'model': 'gpt-6.1-sol', 'effort': 'high'},
            'translation': {'model': 'deepseek-flash', 'effort': 'off'}}
MODELS = [{'id': 'gpt-6.1-sol', 'label': 'Sol', 'efforts': ['low', 'medium', 'high', 'xhigh', 'max']},
          {'id': 'gpt-6-luna', 'label': 'Luna', 'efforts': ['low', 'medium', 'high', 'xhigh', 'max']},
          {'id':'deepseek-flash','label':'Flash','efforts':['off','low','high']}]


def load(root):
    result = copy.deepcopy(DEFAULTS)
    for role, values in result.items():
        prefix = 'LESSONWEAVE_' + role.upper() + '_'
        values['model'] = os.environ.get(prefix + 'MODEL', os.environ.get('LESSONWEAVE_MODEL', values['model']))
        values['effort'] = os.environ.get(prefix + 'EFFORT', os.environ.get('LESSONWEAVE_EFFORT', values['effort']))
        values.update(read(root / 'runtime/generation-settings.json', {}).get(role, {}))
    return result


def update(root, value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError('请分别选择讲解与规划、翻译使用的模型和思考力度')
    choices = {item['id']: item['efforts'] for item in MODELS}
    for settings in value.values():
        if (not isinstance(settings, dict) or set(settings) != {'model', 'effort'}
                or not isinstance(settings['model'], str) or not isinstance(settings['effort'], str)
                or settings['effort'] not in choices.get(settings['model'], [])):
            raise ValueError('请选择当前支持的模型和思考力度')
    save(root / 'runtime/generation-settings.json', value)
    return load(root)


def for_role(root, role):
    return load(root)['translation' if 'translation' in role else 'generation']
